<script setup>
import { ref } from "vue"

const props = defineProps({
  label: { type: String, required: true },
  accept: { type: String, required: true },
  hint: { type: String, default: "" },
})
const model = defineModel({ default: null })

const isDragging = ref(false)
const inputRef = ref(null)

function openPicker() {
  inputRef.value?.click()
}

function onInputChange(event) {
  model.value = event.target.files[0] ?? null
}

function onDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) model.value = file
}
</script>

<template>
  <div class="field">
    <label>{{ label }}</label>
    <div
      class="dropzone"
      :class="{ dragging: isDragging, filled: model }"
      @click="openPicker"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="inputRef"
        type="file"
        :accept="accept"
        class="hidden-input"
        @change="onInputChange"
        @click.stop
      />
      <template v-if="model">
        <span class="dz-icon ok">✓</span>
        <div class="dz-text">
          <span class="dz-filename">{{ model.name }}</span>
          <span class="dz-hint">클릭해서 다른 파일 선택</span>
        </div>
      </template>
      <template v-else>
        <span class="dz-icon">＋</span>
        <div class="dz-text">
          <span class="dz-filename">파일을 끌어다 놓거나 클릭해서 선택</span>
          <span class="dz-hint">{{ hint }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
.dropzone {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1.5px dashed var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-sunken);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.dropzone:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.dropzone.dragging {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.dropzone.filled {
  border-style: solid;
  border-color: var(--green-border);
  background: var(--green-bg);
}
.hidden-input {
  display: none;
}
.dz-icon {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--border);
  color: var(--ink-faint);
  font-size: 15px;
}
.dz-icon.ok {
  color: var(--green-text);
  border-color: var(--green-border);
}
.dz-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}
.dz-filename {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dz-hint {
  font-size: 11.5px;
  color: var(--ink-faint);
}
</style>
