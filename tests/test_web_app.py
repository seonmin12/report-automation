"""
web/app.py (FastAPI 대시보드) 테스트.

실제 서버를 띄우지 않고 TestClient로 라우트별 동작을 확인한다.
"""

from fastapi.testclient import TestClient

from web.app import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_renders_summary_and_operator_table():
    response = client.get("/")

    assert response.status_code == 200
    assert "MVNO 실적 검증 대시보드" in response.text
    assert "검증상태" in response.text
    assert "오류상세" in response.text


def test_api_summary_returns_expected_shape():
    response = client.get("/api/summary")

    assert response.status_code == 200
    body = response.json()
    assert "as_of_date" in body
    assert "operators" in body
    assert len(body["operators"]) == 8


def test_download_xlsx_returns_file():
    response = client.get("/download/xlsx")

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 0


def test_download_unknown_type_returns_404():
    response = client.get("/download/pdf")

    assert response.status_code == 404
