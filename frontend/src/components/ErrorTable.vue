<script setup>
defineProps({ errors: { type: Array, required: true } })
</script>

<template>
  <section>
    <h2>오류상세 <span class="count-pill">{{ errors.length }}</span></h2>
    <div class="table-scroll">
      <table>
        <thead>
          <tr><th>오류유형</th><th>사업자명</th><th>상품코드</th><th>상세내용</th></tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in errors" :key="idx" class="issue-row">
            <td>{{ row["오류유형"] }}</td>
            <td>{{ row["사업자명"] }}</td>
            <td>{{ row["상품코드"] }}</td>
            <td>{{ row["상세내용"] }}</td>
          </tr>
          <tr v-if="errors.length === 0">
            <td colspan="4">이슈 없음</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
