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
  <header class="topbar">
    <div class="topbar-inner">
      <a href="#" class="brand" @click.prevent="reset">
        <span class="brand-mark">M</span>
        <span class="brand-name">MVNO 실적 검증</span>
      </a>
      <span class="badge-demo">100% 더미 데이터 · 서버 미저장</span>
    </div>
  </header>

  <main class="page">
    <template v-if="!currentJobId">
      <div class="upload-view">
        <div class="hero">
          <h1>MVNO 실적 검증 대시보드</h1>
          <p class="subtitle">
            포털 실적 · RAW 데이터 · 매핑 기준표를 업로드하면 검증을 바로 실행합니다.
            모든 데이터는 100% 더미(가상)이며, 업로드 파일은 서버 임시 디렉터리에서만 처리되고 DB에 저장하지 않습니다.
          </p>
        </div>
        <UploadForm @validated="showJob" @view-demo="showJob('demo')" />
      </div>
    </template>
    <Dashboard v-else :job-id="currentJobId" @reset="reset" />
  </main>

  <footer class="footer">
    <p>업로드 파일은 검증 처리 후 서버에 남지 않습니다. 문의 사항은 리포지토리 이슈로 남겨주세요.</p>
  </footer>
</template>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}

.topbar-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 14px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--ink);
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-weight: 800;
  font-size: 15px;
}

.brand-name {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
}

.badge-demo {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-soft-text);
  background: var(--accent-soft);
  padding: 5px 12px;
  border-radius: 999px;
  white-space: nowrap;
}

.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 32px 64px;
  min-height: calc(100vh - 200px);
}

.upload-view {
  max-width: 680px;
  margin: 0 auto;
}

.hero {
  margin-bottom: 28px;
}

.hero h1 {
  font-size: 26px;
  margin: 0 0 8px;
}

.hero .subtitle {
  font-size: 14px;
}

.footer {
  border-top: 1px solid var(--border);
  padding: 20px 32px;
  text-align: center;
}

.footer p {
  margin: 0;
  font-size: 12px;
  color: var(--ink-faint);
}

@media (max-width: 640px) {
  .topbar-inner {
    padding: 12px 18px;
  }
  .badge-demo {
    display: none;
  }
  .page {
    padding: 28px 18px 48px;
  }
}
</style>
