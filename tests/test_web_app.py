"""
web/app.py (FastAPI 파일 업로드 검증 JSON API) 테스트.

실제 서버를 띄우지 않고 TestClient로 라우트별 동작을 확인한다.
프론트엔드(frontend/, Vue)는 별도이므로 여기서는 API 응답만 검증한다.
"""

from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from config import (
    COL_CHURN_COUNT,
    COL_MAPPING_DATE,
    COL_NET_COUNT,
    COL_NEW_COUNT,
    COL_OPERATOR_CODE,
    COL_OPERATOR_NAME,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_TXN_DATE,
    COL_TXN_ID,
    COL_TXN_TYPE,
    COL_USE_YN,
    TXN_TYPE_NEW,
    USE_YN_ACTIVE,
)
from web.app import app

client = TestClient(app)


def _make_valid_upload_files():
    """검증 파이프라인이 요구하는 최소 컬럼을 갖춘 작은 더미 업로드 파일 3종을 만든다."""
    mapping_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001"],
            COL_PRODUCT_NAME: ["상품A"],
            COL_OPERATOR_CODE: ["MVN01"],
            COL_USE_YN: [USE_YN_ACTIVE],
            COL_MAPPING_DATE: ["2026-01-01"],
        }
    )
    raw_df = pd.DataFrame(
        {
            COL_TXN_ID: ["T1"],
            COL_TXN_DATE: ["2026-07-19"],
            COL_OPERATOR_CODE: ["MVN01"],
            COL_PRODUCT_CODE: ["A001"],
            COL_PRODUCT_NAME: ["상품A"],
            COL_TXN_TYPE: [TXN_TYPE_NEW],
        }
    )
    portal_df = pd.DataFrame(
        {
            COL_OPERATOR_CODE: ["MVN01"],
            COL_OPERATOR_NAME: ["A사"],
            COL_PRODUCT_CODE: ["A001"],
            COL_PRODUCT_NAME: ["상품A"],
            COL_NEW_COUNT: [1],
            COL_CHURN_COUNT: [0],
            COL_NET_COUNT: [1],
        }
    )

    mapping_buf = BytesIO()
    mapping_df.to_excel(mapping_buf, index=False)
    mapping_buf.seek(0)

    portal_buf = BytesIO()
    portal_df.to_excel(portal_buf, index=False)
    portal_buf.seek(0)

    raw_buf = BytesIO(raw_df.to_csv(index=False).encode("utf-8-sig"))

    return {
        "portal_file": ("portal.xlsx", portal_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "raw_file": ("raw.csv", raw_buf, "text/csv"),
        "mapping_file": ("mapping.xlsx", mapping_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_summary_unknown_id_returns_404():
    response = client.get("/api/summary/does-not-exist")
    assert response.status_code == 404


def test_api_validate_returns_job_id_and_summary():
    response = client.post(
        "/api/validate", files=_make_valid_upload_files(), data={"asof_date": "2026-07-19"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["compare_total"] == 1
    assert body["is_demo"] is False


def test_api_validate_with_missing_column_returns_400():
    files = _make_valid_upload_files()
    # 매핑 파일에서 필수 컬럼(사용여부 등)이 빠진 것처럼 깨진 파일로 교체
    broken_mapping_df = pd.DataFrame({COL_PRODUCT_CODE: ["A001"], COL_PRODUCT_NAME: ["상품A"]})
    buf = BytesIO()
    broken_mapping_df.to_excel(buf, index=False)
    buf.seek(0)
    files["mapping_file"] = ("mapping.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    response = client.post("/api/validate", files=files, data={"asof_date": "2026-07-19"})

    assert response.status_code == 400
    assert "필수 컬럼이 없습니다" in response.json()["detail"]


def test_api_summary_and_errors_for_demo_job():
    summary = client.get("/api/summary/demo")
    assert summary.status_code == 200
    body = summary.json()
    assert body["is_demo"] is True
    assert len(body["operators"]) == 8
    assert "issue_type_counts" in body

    errors = client.get("/api/errors/demo")
    assert errors.status_code == 200
    assert "errors" in errors.json()


def test_download_demo_xlsx_returns_file():
    response = client.get("/download/demo/xlsx")

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 0


def test_download_unknown_type_returns_404():
    response = client.get("/download/demo/pdf")
    assert response.status_code == 404
