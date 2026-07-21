<script setup>
import { ref } from "vue"
import UploadForm from "./components/UploadForm.vue"
import Dashboard from "./components/Dashboard.vue"

// ?job=<id>로 특정 결과를 바로 열람/공유할 수 있게 한다 (예: ?job=demo).
const currentJobId = ref(new URLSearchParams(window.location.search).get("job"))

function showJob(jobId) {
  currentJobId.value = jobId
  const url = new URL(window.location.href)
  url.searchParams.set("job", jobId)
  window.history.replaceState({}, "", url)
}

function reset() {
  currentJobId.value = null
  const url = new URL(window.location.href)
  url.searchParams.delete("job")
  window.history.replaceState({}, "", url)
}
</script>

<template>
  <h1>MVNO 실적 검증 대시보드</h1>
  <p class="subtitle">
    포털 실적 · RAW 데이터 · 매핑 기준표를 업로드하면 검증을 바로 실행합니다.
    모든 데이터는 100% 더미(가상)이며, 업로드 파일은 서버 임시 디렉터리에서만 처리되고 DB에 저장하지 않습니다.
  </p>

  <UploadForm v-if="!currentJobId" @validated="showJob" @view-demo="showJob('demo')" />
  <Dashboard v-else :job-id="currentJobId" @reset="reset" />
</template>
