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
  <div v-if="loading">불러오는 중...</div>
  <div v-else-if="error" class="error">{{ error }}</div>
  <template v-else-if="summary">
    <div class="subtitle">검증 기준일: {{ summary.as_of_date }}</div>
    <div class="source-banner" :class="summary.is_demo ? 'demo' : 'upload'">
      {{ summary.is_demo ? "더미데이터(체험용) 기준 결과" : `업로드한 파일 기준 결과 (job_id: ${summary.job_id})` }}
    </div>
    <div class="back-link"><a href="#" @click.prevent="$emit('reset')">← 다른 파일 업로드하기</a></div>

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
        <a :href="downloadUrl(summary.job_id, 'xlsx')">엑셀 리포트 (.xlsx)</a>
        <a :href="downloadUrl(summary.job_id, 'png')" class="secondary">요약 이미지 (.png)</a>
        <a :href="downloadUrl(summary.job_id, 'eml')" class="secondary">이메일 초안 (.eml)</a>
      </div>
      <div class="note">이메일 초안은 실제로 발송되지 않습니다. 다운로드 후 메일 클라이언트에서 직접 발송해야 합니다.</div>
    </section>
  </template>
</template>

<style scoped>
.source-banner {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
  margin-bottom: 16px;
}
.source-banner.demo {
  background: #eef1f8;
  color: var(--blue);
}
.source-banner.upload {
  background: var(--green-bg);
  color: var(--green-text);
}
.back-link {
  font-size: 13px;
  margin-bottom: 16px;
}
.back-link a {
  font-weight: 600;
  text-decoration: none;
}
.downloads {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.downloads a {
  display: inline-block;
  padding: 10px 18px;
  background: var(--blue);
  color: #fff;
  text-decoration: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
}
.downloads a.secondary {
  background: #6b7684;
}
.note {
  font-size: 12px;
  color: #888;
  margin-top: 8px;
}
.error {
  background: #ffe9ea;
  color: var(--red-text);
  border: 1px solid #f3b8bb;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
}
</style>
