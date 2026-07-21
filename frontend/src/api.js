// FastAPI 백엔드(web/app.py) 호출 래퍼.
// 로컬 개발에서는 프론트(:5173)와 백엔드(:8000)가 다른 포트라 절대 URL이 필요하고,
// Vercel 배포에서는 같은 오리진에서 /api/*, /download/*로 라우팅되므로 상대 경로로 충분하다.
const API_BASE = import.meta.env.VITE_API_BASE ?? ""

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function parseErrorDetail(response) {
  try {
    const body = await response.json()
    return body.detail || `요청이 실패했습니다 (${response.status})`
  } catch {
    return `요청이 실패했습니다 (${response.status})`
  }
}

export async function validateFiles({ portalFile, rawFile, mappingFile, asofDate }) {
  const form = new FormData()
  form.append("portal_file", portalFile)
  form.append("raw_file", rawFile)
  form.append("mapping_file", mappingFile)
  form.append("asof_date", asofDate)

  const response = await fetch(`${API_BASE}/api/validate`, { method: "POST", body: form })
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status)
  }
  return response.json()
}

export async function getSummary(jobId) {
  const response = await fetch(`${API_BASE}/api/summary/${jobId}`)
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status)
  }
  return response.json()
}

export async function getErrors(jobId) {
  const response = await fetch(`${API_BASE}/api/errors/${jobId}`)
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status)
  }
  return response.json()
}

export function downloadUrl(jobId, fileType) {
  return `${API_BASE}/download/${jobId}/${fileType}`
}
