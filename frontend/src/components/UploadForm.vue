<script setup>
import { ref } from "vue"
import { validateFiles } from "../api.js"
import FileDropzone from "./FileDropzone.vue"

const emit = defineEmits(["validated", "view-demo"])

const portalFile = ref(null)
const rawFile = ref(null)
const mappingFile = ref(null)
const asofDate = ref("2026-07-19")
const loading = ref(false)
const error = ref("")

async function onSubmit() {
  if (!portalFile.value || !rawFile.value || !mappingFile.value) {
    error.value = "3개 파일을 모두 선택해 주세요."
    return
  }

  loading.value = true
  error.value = ""
  try {
    const result = await validateFiles({
      portalFile: portalFile.value,
      rawFile: rawFile.value,
      mappingFile: mappingFile.value,
      asofDate: asofDate.value,
    })
    emit("validated", result.job_id)
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div v-if="error" class="error upload-error">{{ error }}</div>

  <div class="card upload-card">
    <form @submit.prevent="onSubmit">
      <div class="fields-grid">
        <FileDropzone
          v-model="portalFile"
          label="포털 실적 파일"
          accept=".xlsx"
          hint="xlsx 형식"
        />
        <FileDropzone
          v-model="rawFile"
          label="RAW 데이터 파일"
          accept=".csv"
          hint="csv 형식"
        />
        <FileDropzone
          v-model="mappingFile"
          label="매핑 기준표"
          accept=".xlsx"
          hint="xlsx 형식"
        />
      </div>

      <div class="field date-field">
        <label>검증 기준일</label>
        <input type="text" v-model="asofDate" placeholder="YYYY-MM-DD" />
      </div>

      <button type="submit" class="submit-btn" :disabled="loading">
        <span v-if="loading" class="spinner"></span>
        {{ loading ? "검증 실행 중..." : "검증 실행" }}
      </button>
    </form>
  </div>

  <div class="demo-link">
    올릴 파일이 없다면
    <a href="#" @click.prevent="emit('view-demo')">더미데이터로 바로 체험하기 →</a>
  </div>

  <p class="note">
    각 파일의 필수 컬럼과 의미는 <code>docs/data_dictionary.md</code>,
    검증 판단 기준은 <code>docs/validation_rules.md</code>를 참고하세요.
  </p>

  <details class="format-note">
    <summary>📋 파일 형식 관련 참고사항</summary>
    <div class="format-note-body">
      <p>
        지금은 아래 컬럼명과 <strong>정확히 일치</strong>해야 검증이 실행됩니다. 회사마다
        다른 헤더명을 자동으로 인식/매핑해주는 기능은 아직 없고, 컬럼명이 다르면 업로드 단계에서
        바로 안내해드립니다.
      </p>
      <ul>
        <li><strong>포털 실적 파일</strong>: 사업자코드·사업자명·상품코드·상품명·신규건수·해지건수·순증건수</li>
        <li><strong>RAW 데이터 파일</strong>: 거래ID·처리일자·사업자코드·상품코드·상품명·거래유형</li>
        <li><strong>매핑 기준표</strong>: 상품코드·상품명·사업자코드·사용여부·매핑등록일</li>
      </ul>
      <p>서로 다른 헤더명을 자동으로 매핑해주는 기능은 향후 확장 예정입니다.</p>
    </div>
  </details>
</template>

<style scoped>
.upload-card {
  max-width: 620px;
  padding: 28px;
}
.upload-error {
  max-width: 620px;
  margin-bottom: 16px;
}
.fields-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}
.date-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 220px;
  margin-bottom: 22px;
}
.date-field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
.date-field input {
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  background: var(--surface);
}
.date-field input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.submit-btn {
  width: 100%;
  padding: 13px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.15s ease;
}
.submit-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.demo-link {
  max-width: 620px;
  text-align: center;
  margin-top: 18px;
  font-size: 13px;
}
.demo-link a {
  font-weight: 600;
  text-decoration: none;
}
.note {
  max-width: 620px;
  font-size: 12px;
  color: var(--ink-faint);
  margin-top: 24px;
  line-height: 1.6;
}
.note code {
  background: var(--surface-sunken);
  padding: 1px 5px;
  border-radius: 4px;
}

.format-note {
  max-width: 620px;
  margin-top: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  overflow: hidden;
}
.format-note summary {
  cursor: pointer;
  padding: 10px 14px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-soft);
  list-style: none;
}
.format-note summary::-webkit-details-marker {
  display: none;
}
.format-note[open] summary {
  border-bottom: 1px solid var(--border);
  color: var(--ink);
}
.format-note-body {
  padding: 12px 14px 14px;
  font-size: 12.5px;
  color: var(--ink-soft);
  line-height: 1.7;
}
.format-note-body p {
  margin: 0 0 8px;
}
.format-note-body ul {
  margin: 0 0 8px;
  padding-left: 18px;
}
.format-note-body li {
  margin-bottom: 4px;
}
.format-note-body li strong {
  color: var(--ink);
}
</style>
