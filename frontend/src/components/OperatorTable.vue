<script setup>
defineProps({ operators: { type: Array, required: true } })

const STATUS_NEEDS_REVIEW = "확인필요"
</script>

<template>
  <section>
    <h2>사업자별 누적가입자 <span class="count-pill">{{ operators.length }}</span></h2>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>사업자코드</th><th>사업자명</th><th>신규건수</th><th>해지건수</th>
            <th>누적가입자수</th><th>검증상태</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="op in operators" :key="op['사업자코드']">
            <td>{{ op["사업자코드"] }}</td>
            <td>{{ op["사업자명"] }}</td>
            <td>{{ op["신규건수"] }}</td>
            <td>{{ op["해지건수"] }}</td>
            <td>{{ op["누적가입자수"] }}</td>
            <td>
              <span
                class="status-badge"
                :class="op['검증상태'] === STATUS_NEEDS_REVIEW ? 'warn' : 'ok'"
              >
                {{ op["검증상태"] }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
