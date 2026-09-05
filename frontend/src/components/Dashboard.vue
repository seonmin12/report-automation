<script setup>
import { ref, computed, watchEffect } from "vue"
import { getSummary, getErrors, getAiSummary, downloadUrl } from "../api.js"
import SummaryCards from "./SummaryCards.vue"
import OperatorTable from "./OperatorTable.vue"
import ErrorTable from "./ErrorTable.vue"

const props = defineProps({ jobId: { type: String, required: true } })
defineEmits(["reset"])

const summary = ref(null)
const errors = ref([])
const loading = ref(true)
const error = ref("")

// 데모 job 전용. scripts/generate_demo_ai_summary.py로 미리 생성해 둔 결과를 보여줄
// 뿐이라, 버튼을 눌러도 그때 API가 호출되는 게 아니다 (web/app.py의 /api/ai-summary 참고).
const aiSummary = ref(null)
const aiSummaryLoading = ref(false)
const aiSummaryError = ref("")

async function loadAiSummary() {
  aiSummaryLoading.value = true
  aiSummaryError.value = ""
  try {
    aiSummary.value = await getAiSummary(props.jobId)
  } catch (err) {
    aiSummaryError.value = err.message
  } finally {
    aiSummaryLoading.value = false
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

// AI 요약 텍스트에서 상품코드(PRD로 시작)·사업자코드(MVN숫자)·사업자명을 굵게 강조한다.
// 사업자명은 하드코딩하지 않고 summary.operators에서 실제 값을 가져와 패턴을 만든다 —
// 더미 사업자 목록이 바뀌어도 그대로 맞는다.
function highlight(text) {
  if (!text) return ""
  const operatorNames = (summary.value?.operators ?? []).map((op) => op["사업자명"])
  const pattern = new RegExp(`(PRD[A-Z0-9]+|MVN\\d+${operatorNames.length ? "|" + operatorNames.join("|") : ""})`, "g")
  return escapeHtml(text).replace(pattern, "<strong>$1</strong>")
}

const SEVERITY_LABEL = { high: "높음", medium: "보통", low: "낮음" }

// email_writer.py의 제목/인사말/맺음말 문구를 그대로 맞춰서, 메일 앱에서 열었을 때
// 다운로드되는 .eml 초안과 동일한 제목/본문이 보이도록 한다.
const mailtoHref = computed(() => {
  if (!summary.value) return ""
  const [year, month, day] = summary.value.as_of_date.split("-").map(Number)
  const subject = `[MVNO 운영팀] ${month}월 ${day}일 마감 실적 공유드립니다`
  const body =
    `안녕하십니까, MVNO 운영팀입니다.\n\n${summary.value.text_summary}\n\n` +
    `(첨부파일은 자동으로 붙지 않습니다. 위 엑셀 리포트·요약 이미지를 다운로드해 직접 첨부해주세요.)\n\n감사합니다.`
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
})

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

    <section v-if="summary.is_demo" class="ai-summary-section">
      <h2>✨ AI 요약 <span class="count-pill">데모 전용</span></h2>
      <button
        v-if="!aiSummary"
        class="ai-summary-btn"
        :disabled="aiSummaryLoading"
        @click="loadAiSummary"
      >
        {{ aiSummaryLoading ? "불러오는 중..." : "AI 요약 보기" }}
      </button>
      <div v-if="aiSummaryError" class="error">{{ aiSummaryError }}</div>
      <div v-if="aiSummary" class="ai-summary-box">
        <h3 class="ai-summary-title">{{ aiSummary.headline }}</h3>
        <p class="ai-summary-text" v-html="highlight(aiSummary.overview)"></p>

        <div class="ai-risk-list">
          <div
            v-for="(risk, idx) in aiSummary.risks"
            :key="idx"
            class="ai-risk-item"
            :class="`severity-${risk.severity}`"
          >
            <div class="ai-risk-head">
              <span class="ai-risk-severity">{{ SEVERITY_LABEL[risk.severity] || risk.severity }}</span>
              <span class="ai-risk-operator">{{ risk.operator }}</span>
              <span class="ai-risk-issue">{{ risk.issue }}</span>
            </div>
            <p class="ai-risk-detail" v-html="highlight(risk.detail)"></p>
          </div>
        </div>

        <div v-if="aiSummary.recommended_actions?.length" class="ai-summary-action">
          <div class="ai-summary-action-title">📌 다음 확인 사항</div>
          <ul class="ai-summary-action-list">
            <li
              v-for="(action, idx) in aiSummary.recommended_actions"
              :key="idx"
              v-html="highlight(action)"
            ></li>
          </ul>
        </div>

        <div class="ai-summary-meta">
          {{ aiSummary.model }} · {{ aiSummary.generated_at }} 미리 생성됨 (지금 실시간 호출 아님)
        </div>
      </div>
    </section>

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
        <a :href="mailtoHref" class="download-card">
          <span class="dl-icon">📝</span>
          <span class="dl-text">
            <span class="dl-title">메일 작성하기</span>
            <span class="dl-sub">메일 앱으로 열기</span>
          </span>
        </a>
      </div>
      <div class="note">
        메일은 실제로 발송되지 않습니다. "메일 작성하기"는 제목/본문만 채워진 메일 앱 창을 열어주며,
        첨부파일은 자동으로 붙지 않으니 위 엑셀/이미지를 받아 직접 첨부해주세요.
      </div>
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

.ai-summary-btn {
  padding: 9px 16px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 700;
}
.ai-summary-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.ai-summary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.ai-summary-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px 22px;
}
.ai-summary-title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 800;
  color: var(--ink);
}
.ai-summary-text {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--ink);
}
.ai-summary-text:last-of-type {
  margin-bottom: 16px;
}
.ai-summary-text :deep(strong) {
  color: var(--accent);
  font-weight: 700;
}

.ai-risk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.ai-risk-item {
  border: 1px solid var(--border);
  border-left-width: 4px;
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  background: var(--surface-sunken);
}
.ai-risk-item.severity-high {
  border-left-color: var(--red-text);
  background: var(--red-bg);
}
.ai-risk-item.severity-medium {
  border-left-color: var(--amber-text);
  background: var(--amber-bg);
}
.ai-risk-item.severity-low {
  border-left-color: var(--ink-faint);
}
.ai-risk-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}
.ai-risk-severity {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink-soft);
  border: 1px solid var(--border);
}
.severity-high .ai-risk-severity {
  color: var(--red-text);
  border-color: var(--red-border);
}
.severity-medium .ai-risk-severity {
  color: var(--amber-text);
  border-color: var(--amber-border);
}
.ai-risk-operator {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--ink);
}
.ai-risk-issue {
  font-size: 13px;
  color: var(--ink-soft);
}
.ai-risk-detail {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink-soft);
}
.ai-risk-detail :deep(strong) {
  color: var(--ink);
  font-weight: 700;
}

.ai-summary-action {
  background: var(--accent-soft);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  margin-bottom: 14px;
  font-size: 13.5px;
  color: var(--accent-soft-text);
}
.ai-summary-action-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.ai-summary-action-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.7;
}
.ai-summary-action-list :deep(strong) {
  font-weight: 700;
}
.ai-summary-meta {
  font-size: 11.5px;
  color: var(--ink-faint);
}
</style>
