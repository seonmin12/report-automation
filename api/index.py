"""Vercel 배포용 진입점. web/app.py의 FastAPI 앱을 그대로 재노출한다."""

from web.app import app

__all__ = ["app"]
