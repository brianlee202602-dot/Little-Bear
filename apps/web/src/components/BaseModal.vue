<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    size?: "small" | "medium" | "large";
  }>(),
  {
    size: "medium",
  },
);

const emit = defineEmits<{
  (event: "close"): void;
}>();

function close(): void {
  emit("close");
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.open" class="base-modal" role="dialog" aria-modal="true">
      <button class="base-modal__backdrop" type="button" aria-label="关闭弹窗" @click="close" />
      <section class="base-modal__panel" :class="`base-modal__panel--${props.size}`">
        <header class="base-modal__header">
          <h2>{{ props.title }}</h2>
          <button class="base-modal__close" type="button" @click="close">关闭</button>
        </header>
        <div class="base-modal__body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="base-modal__footer">
          <slot name="footer" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.base-modal {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 24px;
}

.base-modal__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgb(15 23 42 / 45%);
}

.base-modal__panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  width: min(100%, 720px);
  max-height: min(86vh, 960px);
  overflow: hidden;
  border: 1px solid #d7e0ea;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 80px rgb(15 23 42 / 22%);
}

.base-modal__panel--small {
  width: min(100%, 480px);
}

.base-modal__panel--large {
  width: min(100%, 1040px);
}

.base-modal__header,
.base-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #e5edf5;
}

.base-modal__footer {
  border-top: 1px solid #e5edf5;
  border-bottom: 0;
}

.base-modal__header h2 {
  margin: 0;
  color: #182230;
  font-size: 18px;
  font-weight: 700;
}

.base-modal__close {
  min-width: 72px;
  min-height: 40px;
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: #fff;
  color: #182230;
  cursor: pointer;
}

.base-modal__body {
  overflow: auto;
  padding: 20px;
}
</style>
