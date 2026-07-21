<script setup>
defineProps({ summary: { type: Object, required: true } })
</script>

<template>
  <div class="cards">
    <div class="stat-card">
      <div class="icon">📊</div>
      <div class="label">실적 비교 대상</div>
      <div class="value">{{ summary.compare_total }}<span class="unit">건</span></div>
    </div>
    <div class="stat-card">
      <div class="icon ok">✓</div>
      <div class="label">실적 비교 - 정상</div>
      <div class="value">{{ summary.compare_normal_count }}<span class="unit">건</span></div>
    </div>
    <div class="stat-card warn">
      <div class="icon warn">!</div>
      <div class="label">실적 비교 - 확인필요</div>
      <div class="value warn">{{ summary.compare_issue_count }}<span class="unit">건</span></div>
    </div>
    <div class="stat-card warn">
      <div class="icon warn">⚠</div>
      <div class="label">전체 오류 건수</div>
      <div class="value warn">{{ summary.total_issue_count }}<span class="unit">건</span></div>
    </div>
  </div>
</template>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 32px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 18px 20px;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}
.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.icon {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: var(--accent-soft);
  color: var(--accent-soft-text);
  font-size: 14px;
  margin-bottom: 12px;
}
.icon.ok {
  background: var(--green-bg);
  color: var(--green-text);
}
.icon.warn {
  background: var(--red-bg);
  color: var(--red-text);
}
.label {
  font-size: 13px;
  color: var(--ink-soft);
  margin-bottom: 6px;
  font-weight: 500;
}
.value {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.value .unit {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-faint);
  margin-left: 2px;
}
.value.warn {
  color: var(--red-text);
}
</style>
