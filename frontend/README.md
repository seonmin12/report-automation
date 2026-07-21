# frontend

MVNO 실적 검증 대시보드의 프론트엔드 (Vue 3 + Vite). 백엔드는 `../web/app.py`
(FastAPI, 순수 JSON API)이며, 이 앱은 그 API만 호출해서 화면을 구성합니다.

## 실행

```bash
npm install
npm run dev      # http://localhost:5173 (백엔드는 http://localhost:8000 에서 별도로 실행)
npm run build    # dist/ 에 정적 빌드 생성 (Vercel 배포용)
```

API 베이스 URL은 `.env.development`의 `VITE_API_BASE`로 지정합니다. 프로덕션(Vercel)에서는
같은 오리진에서 `/api/*`, `/download/*`로 라우팅되므로 값을 비워 둡니다 (상대 경로 사용).

자세한 프로젝트 설명은 루트 [README.md](../README.md)를 참고하세요.
