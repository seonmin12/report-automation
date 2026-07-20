"""
조회/다운로드 전용 FastAPI 대시보드.

CLI(main.py)가 만드는 것과 동일한 검증 파이프라인을 웹에서 바로 확인할 수 있게 한다.
실제 이메일 발송이나 원본 데이터 변경은 하지 않는 읽기 전용 서비스다.
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

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

app = FastAPI(title="MVNO 실적 검증 대시보드")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# 서버리스 환경에서는 요청마다 새 프로세스가 뜰 수 있으므로, 같은 프로세스 안에서만
# 재사용하는 단순 인메모리 캐시. 더미데이터는 RANDOM_SEED로 고정되어 있어 재계산해도
# 항상 같은 결과가 나온다.
_cache: dict = {}

_DOWNLOAD_FILES = {
    "xlsx": (
        "xlsx_path",
        "validation_report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "png": ("png_path", "summary.png", "image/png"),
    "eml": ("eml_path", "email_draft.eml", "message/rfc822"),
}


def _build_pipeline_result() -> dict:
    """더미데이터 생성부터 리포트 산출물까지 한 번 계산해서 캐시에 담아둔다."""
    if "result" in _cache:
        return _cache["result"]

    as_of_date = config.DEFAULT_AS_OF_DATE

    mapping_df = generate_dummy_data.generate_product_mapping()
    raw_df = generate_dummy_data.generate_raw_transactions(mapping_df)
    portal_df = generate_dummy_data.generate_portal_performance(raw_df)

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

    tmp_dir = Path(tempfile.mkdtemp(prefix="mvno_dashboard_"))
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

    result = {
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
    _cache["result"] = result
    return result


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    result = _build_pipeline_result()
    compare_df = result["compare_df"]
    error_detail_df = result["error_detail_df"]
    operator_summary_df = result["operator_summary_df"]

    compare_total = len(compare_df)
    compare_issue_count = (
        int(compare_df[compare.COL_ISSUE_FLAG].sum()) if not compare_df.empty else 0
    )
    issue_type_counts = (
        list(error_detail_df[validate.COL_ISSUE_TYPE].value_counts().items())
        if not error_detail_df.empty
        else []
    )

    context = {
        "as_of_date": result["as_of_date"].strftime("%Y-%m-%d"),
        "compare_total": compare_total,
        "compare_normal_count": compare_total - compare_issue_count,
        "compare_issue_count": compare_issue_count,
        "issue_type_counts": issue_type_counts,
        "total_issue_count": len(error_detail_df),
        "operators": operator_summary_df.to_dict(orient="records"),
        "error_rows": error_detail_df.to_dict(orient="records"),
        "col_operator_code": config.COL_OPERATOR_CODE,
        "col_operator_name": config.COL_OPERATOR_NAME,
        "col_new_count": config.COL_NEW_COUNT,
        "col_churn_count": config.COL_CHURN_COUNT,
        "col_cumulative_count": aggregate.COL_CUMULATIVE_COUNT,
        "col_validation_status": config.COL_VALIDATION_STATUS,
        "status_needs_review": config.STATUS_NEEDS_REVIEW,
        "col_issue_type": validate.COL_ISSUE_TYPE,
        "col_issue_detail": validate.COL_ISSUE_DETAIL,
        "col_product_code": config.COL_PRODUCT_CODE,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@app.get("/api/summary")
def api_summary():
    result = _build_pipeline_result()
    compare_df = result["compare_df"]
    compare_total = len(compare_df)
    compare_issue_count = (
        int(compare_df[compare.COL_ISSUE_FLAG].sum()) if not compare_df.empty else 0
    )

    return JSONResponse(
        {
            "as_of_date": result["as_of_date"].isoformat(),
            "compare_total": compare_total,
            "compare_issue_count": compare_issue_count,
            "total_issue_count": len(result["error_detail_df"]),
            "operators": result["operator_summary_df"].to_dict(orient="records"),
        }
    )


@app.get("/download/{file_type}")
def download(file_type: str):
    if file_type not in _DOWNLOAD_FILES:
        raise HTTPException(status_code=404, detail="알 수 없는 파일 종류입니다.")

    result = _build_pipeline_result()
    key, filename, media_type = _DOWNLOAD_FILES[file_type]
    return FileResponse(result[key], media_type=media_type, filename=filename)
