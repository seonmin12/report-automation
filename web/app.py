"""
파일 업로드 기반 검증 실행 API.

CLI(main.py)가 만드는 것과 동일한 검증 파이프라인을 웹에서 실행할 수 있게 하는 순수 JSON API다.
프론트엔드(frontend/, Vue 3 + Vite)가 이 API를 호출해서 화면을 그린다.
사용자가 포털 실적/RAW/매핑 기준표 3개 파일을 업로드하면 서버 임시 디렉터리에서만
처리하고(DB 저장 없음), 검증 결과를 JSON으로 반환하고 xlsx/png/eml을 다운로드할 수 있게 한다.
실제 이메일 발송이나 원본 데이터의 영구 저장은 하지 않는다.
"""

import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import config
from src import (
    aggregate,
    compare,
    email_writer,
    generate_dummy_data,
    image_builder,
    report_builder,
    summary_writer,
    validate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 데모 job은 더미데이터 생성기가 공유하는 시드 고정 난수 생성기(random.Random)를 쓰는데,
    # 요청이 들어올 때 지연 계산하면 동시에 두 요청(예: summary+errors 병렬 호출)이 동시에
    # "아직 없으니 생성"을 시도해 스레드 안전하지 않은 난수 생성기를 함께 건드리는 경합이
    # 생길 수 있다. 서버가 요청을 받기 전에 한 번만 미리 계산해 두면 이 경합을 원천 차단한다.
    _get_or_create_demo_job()
    yield


app = FastAPI(title="MVNO 실적 검증 API", lifespan=lifespan)

# 프론트(Vue, Vite 개발 서버는 기본적으로 다른 포트)에서 호출하므로 CORS를 열어 둔다.
# 인증/쿠키를 쓰지 않는 데모 API라 오리진을 넓게 허용해도 리스크가 낮다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서버리스 환경에서는 요청마다 새 프로세스가 뜰 수 있으므로, 같은 프로세스 안에서만
# 유지되는 단순 인메모리 job 저장소. DB는 의도적으로 쓰지 않는다 (docs/validation_rules.md 참고).
DEMO_JOB_ID = "demo"
_jobs: dict = {}

_DOWNLOAD_FILES = {
    "xlsx": (
        "xlsx_path",
        "validation_report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "png": ("png_path", "summary.png", "image/png"),
    "eml": ("eml_path", "email_draft.eml", "message/rfc822"),
}

# docs/data_dictionary.md와 동일하게 유지한다. 여기 없는 컬럼이 빠지면 파이프라인 실행 중
# KeyError로 죽는 대신, 업로드 단계에서 미리 400으로 막기 위한 목록이다.
REQUIRED_COLUMNS = {
    "portal": [
        config.COL_OPERATOR_CODE,
        config.COL_OPERATOR_NAME,
        config.COL_PRODUCT_CODE,
        config.COL_PRODUCT_NAME,
        config.COL_NEW_COUNT,
        config.COL_CHURN_COUNT,
        config.COL_NET_COUNT,
    ],
    "raw": [
        config.COL_TXN_ID,
        config.COL_TXN_DATE,
        config.COL_OPERATOR_CODE,
        config.COL_PRODUCT_CODE,
        config.COL_PRODUCT_NAME,
        config.COL_TXN_TYPE,
    ],
    "mapping": [
        config.COL_PRODUCT_CODE,
        config.COL_PRODUCT_NAME,
        config.COL_OPERATOR_CODE,
        config.COL_USE_YN,
        config.COL_MAPPING_DATE,
    ],
}

_FILE_LABELS = {"portal": "포털 실적 파일", "raw": "RAW 데이터 파일", "mapping": "매핑 기준표"}


def _check_required_columns(df: pd.DataFrame, key: str) -> None:
    missing = [col for col in REQUIRED_COLUMNS[key] if col not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{_FILE_LABELS[key]}에 필수 컬럼이 없습니다: {', '.join(missing)} "
                "(docs/data_dictionary.md 참고)"
            ),
        )


def _run_pipeline(
    as_of_date: date, mapping_df: pd.DataFrame, raw_df: pd.DataFrame, portal_df: pd.DataFrame
) -> dict:
    """더미데이터든 업로드 파일이든 동일하게 통과시키는 검증 파이프라인."""
    monthly_df = aggregate.filter_current_month(raw_df, as_of_date)
    operator_product_df = aggregate.aggregate_by_operator_product(monthly_df)
    operator_summary_df = aggregate.aggregate_by_operator(monthly_df)

    compare_df = compare.compare_portal_vs_raw(portal_df, operator_product_df)
    validation_results = validate.run_all_validations(raw_df, portal_df, mapping_df)
    operator_summary_df = aggregate.attach_validation_status(
        operator_summary_df, compare_df, validation_results
    )

    error_detail_df = report_builder.build_error_detail_df(compare_df, validation_results)
    text_summary = summary_writer.build_text_summary(
        as_of_date, compare_df, validation_results, operator_summary_df
    )

    tmp_dir = Path(tempfile.mkdtemp(prefix="mvno_job_"))
    xlsx_path = tmp_dir / "validation_report.xlsx"
    png_path = tmp_dir / "summary.png"
    eml_path = tmp_dir / "email_draft.eml"

    report_builder.build_excel_report(
        as_of_date, compare_df, validation_results, operator_summary_df, xlsx_path
    )
    image_builder.build_summary_image(
        operator_summary_df, png_path, title=f"사업자별 누적가입자 요약 ({as_of_date:%Y%m%d})"
    )
    email_draft = email_writer.build_email_draft(
        as_of_date, text_summary, attachment_paths=[xlsx_path, png_path]
    )
    email_writer.save_email_draft(email_draft, eml_path)

    return {
        "as_of_date": as_of_date,
        "compare_df": compare_df,
        "validation_results": validation_results,
        "operator_summary_df": operator_summary_df,
        "error_detail_df": error_detail_df,
        "text_summary": text_summary,
        "xlsx_path": xlsx_path,
        "png_path": png_path,
        "eml_path": eml_path,
    }


def _get_or_create_demo_job() -> dict:
    if DEMO_JOB_ID not in _jobs:
        as_of_date = config.DEFAULT_AS_OF_DATE
        mapping_df = generate_dummy_data.generate_product_mapping()
        raw_df = generate_dummy_data.generate_raw_transactions(mapping_df)
        portal_df = generate_dummy_data.generate_portal_performance(raw_df)
        _jobs[DEMO_JOB_ID] = _run_pipeline(as_of_date, mapping_df, raw_df, portal_df)
    return _jobs[DEMO_JOB_ID]


def _get_job(job_id: str) -> dict:
    if job_id == DEMO_JOB_ID:
        return _get_or_create_demo_job()
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")
    return _jobs[job_id]


def _process_upload(
    portal_file: UploadFile, raw_file: UploadFile, mapping_file: UploadFile, asof_date: str
) -> tuple[str, dict]:
    try:
        as_of_date = datetime.strptime(asof_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="기준일 형식은 YYYY-MM-DD여야 합니다.")

    try:
        mapping_df = pd.read_excel(mapping_file.file)
        portal_df = pd.read_excel(portal_file.file)
        raw_df = pd.read_csv(raw_file.file, encoding="utf-8-sig")
    except Exception as exc:  # 업로드 파일은 사용자 입력이므로 형식이 깨져 있을 수 있다
        raise HTTPException(status_code=400, detail=f"파일을 읽는 중 오류가 발생했습니다: {exc}")

    _check_required_columns(mapping_df, "mapping")
    _check_required_columns(raw_df, "raw")
    _check_required_columns(portal_df, "portal")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = _run_pipeline(as_of_date, mapping_df, raw_df, portal_df)
    return job_id, _jobs[job_id]


def _summary_payload(job_id: str, result: dict) -> dict:
    compare_df = result["compare_df"]
    error_detail_df = result["error_detail_df"]

    compare_total = len(compare_df)
    compare_issue_count = (
        int(compare_df[compare.COL_ISSUE_FLAG].sum()) if not compare_df.empty else 0
    )
    issue_type_counts = (
        error_detail_df[validate.COL_ISSUE_TYPE].value_counts().to_dict()
        if not error_detail_df.empty
        else {}
    )

    return {
        "job_id": job_id,
        "is_demo": job_id == DEMO_JOB_ID,
        "as_of_date": result["as_of_date"].isoformat(),
        "compare_total": compare_total,
        "compare_normal_count": compare_total - compare_issue_count,
        "compare_issue_count": compare_issue_count,
        "total_issue_count": len(error_detail_df),
        "issue_type_counts": issue_type_counts,
        "operators": result["operator_summary_df"].to_dict(orient="records"),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/validate")
def api_validate(
    portal_file: UploadFile = File(...),
    raw_file: UploadFile = File(...),
    mapping_file: UploadFile = File(...),
    asof_date: str = Form(default=str(config.DEFAULT_AS_OF_DATE)),
):
    job_id, result = _process_upload(portal_file, raw_file, mapping_file, asof_date)
    return JSONResponse(_summary_payload(job_id, result))


@app.get("/api/summary/{job_id}")
def api_summary(job_id: str):
    result = _get_job(job_id)
    return JSONResponse(_summary_payload(job_id, result))


@app.get("/api/errors/{job_id}")
def api_errors(job_id: str):
    result = _get_job(job_id)
    return JSONResponse(
        {"job_id": job_id, "errors": result["error_detail_df"].to_dict(orient="records")}
    )


@app.get("/download/{job_id}/{file_type}")
def download(job_id: str, file_type: str):
    if file_type not in _DOWNLOAD_FILES:
        raise HTTPException(status_code=404, detail="알 수 없는 파일 종류입니다.")

    result = _get_job(job_id)
    key, filename, media_type = _DOWNLOAD_FILES[file_type]
    return FileResponse(result[key], media_type=media_type, filename=filename)
