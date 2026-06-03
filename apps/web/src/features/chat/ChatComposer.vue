<script setup lang="ts">
const props = defineProps<{
  query: string;
  streaming: boolean;
  includeSources: boolean;
  disabled: boolean;
  busy: boolean;
  canSubmit: boolean;
  hint: string;
}>();

const emit = defineEmits<{
  (event: "update:query", value: string): void;
  (event: "update:streaming", value: boolean): void;
  (event: "update:includeSources", value: boolean): void;
  (event: "submit"): void;
  (event: "cancel"): void;
}>();

function updateQuery(event: Event): void {
  const target = event.target as HTMLTextAreaElement;
  emit("update:query", target.value.trim());
}

function updateStreaming(event: Event): void {
  const target = event.target as HTMLInputElement;
  emit("update:streaming", target.checked);
}

function updateIncludeSources(event: Event): void {
  const target = event.target as HTMLInputElement;
  emit("update:includeSources", target.checked);
}
</script>

<template>
  <form class="composer" @submit.prevent="emit('submit')">
    <p v-if="props.hint" class="submit-hint">{{ props.hint }}</p>
    <div class="composer-box">
      <textarea
        :value="props.query"
        rows="1"
        placeholder="有问题，尽管问"
        :disabled="props.disabled"
        @input="updateQuery"
        @keydown.enter.exact.prevent="emit('submit')"
      />
      <div class="composer-actions">
        <label class="toggle">
          <input type="checkbox" :checked="props.streaming" @change="updateStreaming" />
          <span>流式</span>
        </label>
        <label class="toggle">
          <input type="checkbox" :checked="props.includeSources" @change="updateIncludeSources" />
          <span>来源</span>
        </label>
        <button v-if="props.busy" class="secondary-button" type="button" @click="emit('cancel')">
          取消
        </button>
        <button class="send-button" type="submit" :disabled="!props.canSubmit || props.busy" title="发送">
          ↑
        </button>
      </div>
    </div>
  </form>
</template>

<style scoped>
.composer {
  position: sticky;
  bottom: 0;
  z-index: 20;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), #ffffff 24%);
  padding: 12px clamp(20px, 7vw, 96px) max(24px, env(safe-area-inset-bottom));
}

.submit-hint {
  max-width: 900px;
  margin: 0 auto 8px;
  color: #737373;
  font-size: 12px;
  text-align: center;
}

.composer-box {
  max-width: 900px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  border: 1px solid #d4d4d4;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.08);
  padding: 9px 10px 9px 14px;
}

.composer-box textarea {
  width: 100%;
  min-height: 44px;
  max-height: 180px;
  resize: vertical;
  border: 0;
  border-radius: 8px;
  background: #ffffff;
  color: #171717;
  box-shadow: none;
  font: inherit;
  line-height: 1.5;
  outline: none;
  padding: 10px 0;
}

.composer-box textarea:focus {
  box-shadow: none;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #525252;
  font-size: 12px;
  font-weight: 700;
}

.secondary-button {
  min-height: 40px;
  border: 1px solid #d4d4d4;
  border-radius: 8px;
  background: #ffffff;
  color: #171717;
  cursor: pointer;
  font: inherit;
  font-weight: 800;
  padding: 8px 14px;
}

.send-button {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #111111;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-size: 22px;
  line-height: 1;
}

button:disabled,
textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (max-width: 560px) {
  .composer {
    padding-left: 14px;
    padding-right: 14px;
  }

  .composer-box {
    grid-template-columns: 1fr;
    border-radius: 18px;
  }

  .composer-actions {
    justify-content: space-between;
  }

  .toggle {
    display: none;
  }
}
</style>
