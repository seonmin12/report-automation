<script setup>
defineProps({ summary: { type: Object, required: true } })
</script>

<template>
  <div class="cards">
    <div class="card">
      <div class="label">실적 비교 대상</div>
      <div class="value">{{ summary.compare_total }}건</div>
    </div>
    <div class="card">
      <div class="label">실적 비교 - 정상</div>
      <div class="value">{{ summary.compare_normal_count }}건</div>
    </div>
    <div class="card">
      <div class="label">실적 비교 - 확인필요</div>
      <div class="value warn">{{ summary.compare_issue_count }}건</div>
    </div>
    <div class="card">
      <div class="label">전체 오류 건수</div>
      <div class="value warn">{{ summary.total_issue_count }}건</div>
    </div>
  </div>
</template>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}
.value {
  font-size: 24px;
  font-weight: 700;
}
.value.warn {
  color: var(--red-text);
}
</style>
