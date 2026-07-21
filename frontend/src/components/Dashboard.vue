<script setup>
import { ref, watchEffect } from "vue"
import { getSummary, getErrors, downloadUrl } from "../api.js"
import SummaryCards from "./SummaryCards.vue"
import OperatorTable from "./OperatorTable.vue"
import ErrorTable from "./ErrorTable.vue"

const props = defineProps({ jobId: { type: String, required: true } })
defineEmits(["reset"])

const summary = ref(null)
const errors = ref([])
const loading = ref(true)
const error = ref("")

watchEffect(async () => {
  loading.value = true
  error.value = ""
  try {
    const [summaryBody, errorsBody] = await Promise.all([
      getSummary(props.jobId),
      getErrors(props.jobId),
    ])
    summary.value = summaryBody
    errors.value = errorsBody.errors
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="loading-state">
    <span class="spinner"></span> 불러오는 중...
  </div>
  <div v-else-if="error" class="error">{{ error }}</div>
  <template v-else-if="summary">
    <div class="result-header">
      <div class="result-header-left">
        <div class="source-banner" :class="summary.is_demo ? 'demo' : 'upload'">
          {{ summary.is_demo ? "더미데이터(체험용) 기준 결과" : `업로드한 파일 기준 결과 (job_id: ${summary.job_id})` }}
        </div>
        <div class="asof">검증 기준일 <strong>{{ summary.as_of_date }}</strong></div>
      </div>
      <button class="back-link" @click="$emit('reset')">← 다른 파일 업로드하기</button>
    </div>

    <SummaryCards :summary="summary" />

    <section>
      <h2>오류유형별 건수</h2>
      <div class="table-scroll">
        <table>
          <thead><tr><th>오류유형</th><th>건수</th></tr></thead>
          <tbody>
            <tr v-for="(count, issueType) in summary.issue_type_counts" :key="issueType">
              <td>{{ issueType }}</td>
              <td>{{ count }}건</td>
            </tr>
            <tr v-if="Object.keys(summary.issue_type_counts).length === 0">
              <td colspan="2">이슈 없음</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <OperatorTable :operators="summary.operators" />
    <ErrorTable :errors="errors" />

    <section>
      <h2>다운로드</h2>
      <div class="downloads">
        <a :href="downloadUrl(summary.job_id, 'xlsx')" class="download-card primary">
          <span class="dl-icon">📘</span>
          <span class="dl-text">
            <span class="dl-title">엑셀 리포트</span>
            <span class="dl-sub">.xlsx</span>
          </span>
        </a>
        <a :href="downloadUrl(summary.job_id, 'png')" class="download-card">
          <span class="dl-icon">🖼️</span>
          <span class="dl-text">
            <span class="dl-title">요약 이미지</span>
            <span class="dl-sub">.png</span>
          </span>
        </a>
        <a :href="downloadUrl(summary.job_id, 'eml')" class="download-card">
          <span class="dl-icon">✉️</span>
          <span class="dl-text">
            <span class="dl-title">이메일 초안</span>
            <span class="dl-sub">.eml</span>
          </span>
        </a>
      </div>
      <div class="note">이메일 초안은 실제로 발송되지 않습니다. 다운로드 후 메일 클라이언트에서 직접 발송해야 합니다.</div>
    </section>
  </template>
</template>

<style scoped>
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-soft);
  font-size: 14px;
  padding: 40px 0;
}
.loading-state .spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.result-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 28px;
}
.result-header-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.source-banner {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 999px;
  width: fit-content;
}
.source-banner.demo {
  background: var(--accent-soft);
  color: var(--accent-soft-text);
}
.source-banner.upload {
  background: var(--green-bg);
  color: var(--green-text);
}
.asof {
  font-size: 13px;
  color: var(--ink-soft);
}
.back-link {
  background: none;
  border: 1px solid var(--border);
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
}
.back-link:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.downloads {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.download-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  text-decoration: none;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
  min-width: 180px;
}
.download-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
  border-color: var(--accent);
}
.download-card.primary {
  background: var(--accent);
  border-color: var(--accent);
}
.dl-icon {
  font-size: 20px;
}
.dl-text {
  display: flex;
  flex-direction: column;
}
.dl-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--ink);
}
.dl-sub {
  font-size: 11.5px;
  color: var(--ink-faint);
}
.download-card.primary .dl-title,
.download-card.primary .dl-sub {
  color: #fff;
}
.download-card.primary .dl-sub {
  opacity: 0.8;
}
.note {
  font-size: 12px;
  color: var(--ink-faint);
  margin-top: 10px;
}
</style>
