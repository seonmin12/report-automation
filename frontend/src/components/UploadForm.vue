<script setup>
import { ref } from "vue"
import { validateFiles } from "../api.js"

const emit = defineEmits(["validated", "view-demo"])

const portalFile = ref(null)
const rawFile = ref(null)
const mappingFile = ref(null)
const asofDate = ref("2026-07-19")
const loading = ref(false)
const error = ref("")

function onFileChange(target, event) {
  target.value = event.target.files[0] ?? null
}

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
  <div v-if="error" class="error">{{ error }}</div>

  <div class="card">
    <form @submit.prevent="onSubmit">
      <div class="field">
        <label>포털 실적 파일 (.xlsx)</label>
        <input type="file" accept=".xlsx" required @change="onFileChange(portalFile, $event)" />
      </div>
      <div class="field">
        <label>RAW 데이터 파일 (.csv)</label>
        <input type="file" accept=".csv" required @change="onFileChange(rawFile, $event)" />
      </div>
      <div class="field">
        <label>매핑 기준표 (.xlsx)</label>
        <input type="file" accept=".xlsx" required @change="onFileChange(mappingFile, $event)" />
      </div>
      <div class="field">
        <label>검증 기준일 (YYYY-MM-DD)</label>
        <input type="text" v-model="asofDate" />
      </div>
      <button type="submit" class="submit-btn" :disabled="loading">
        {{ loading ? "검증 실행 중..." : "검증 실행" }}
      </button>
    </form>
  </div>

  <div class="demo-link">
    올릴 파일이 없다면
    <a href="#" @click.prevent="emit('view-demo')">더미데이터로 바로 체험하기</a>
  </div>

  <p class="note">
    각 파일의 필수 컬럼과 의미는 <code>docs/data_dictionary.md</code>,
    검증 판단 기준은 <code>docs/validation_rules.md</code>를 참고하세요.
  </p>
</template>

<style scoped>
.card {
  max-width: 480px;
  padding: 24px;
}
.field {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}
.field input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.submit-btn {
  width: 100%;
  padding: 12px;
  background: var(--blue);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 700;
  margin-top: 8px;
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  max-width: 480px;
  background: #ffe9ea;
  color: var(--red-text);
  border: 1px solid #f3b8bb;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  white-space: pre-wrap;
}
.demo-link {
  max-width: 480px;
  text-align: center;
  margin-top: 18px;
  font-size: 13px;
}
.demo-link a {
  font-weight: 600;
  text-decoration: none;
}
.note {
  max-width: 480px;
  font-size: 12px;
  color: #888;
  margin-top: 20px;
  line-height: 1.6;
}
</style>
