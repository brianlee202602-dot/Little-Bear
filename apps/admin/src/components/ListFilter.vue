<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    submitLabel?: string;
    resetLabel?: string;
    showReset?: boolean;
    submitDisabled?: boolean;
  }>(),
  {
    submitLabel: "查询",
    resetLabel: "重置",
    showReset: false,
    submitDisabled: false,
  },
);

const emit = defineEmits<{
  (event: "submit"): void;
  (event: "reset"): void;
}>();
</script>

<template>
  <form class="list-filter" @submit.prevent="emit('submit')">
    <div class="list-filter__fields">
      <slot />
    </div>
    <div class="list-filter__actions">
      <button v-if="props.showReset" type="button" class="list-filter__button" @click="emit('reset')">
        {{ props.resetLabel }}
      </button>
      <button type="submit" class="list-filter__button list-filter__button--primary" :disabled="props.submitDisabled">
        {{ props.submitLabel }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.list-filter {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 16px;
  width: 100%;
}

.list-filter__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  align-items: end;
  gap: 16px;
  min-width: 0;
}

.list-filter__actions {
  display: flex;
  align-items: end;
  justify-content: flex-end;
  gap: 10px;
}

.list-filter__button {
  min-width: 96px;
  min-height: 44px;
  padding: 0 18px;
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: #fff;
  color: #182230;
  cursor: pointer;
  white-space: nowrap;
}

.list-filter__button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.list-filter__button--primary {
  background: #fff;
  border-color: #cfd8e3;
  color: #182230;
}

.list-filter :deep(.field) {
  min-width: 0;
}

.list-filter :deep(.control) {
  width: 100%;
}

@media (max-width: 720px) {
  .list-filter {
    grid-template-columns: 1fr;
  }

  .list-filter__actions {
    justify-content: stretch;
  }

  .list-filter__button {
    width: 100%;
  }
}
</style>
