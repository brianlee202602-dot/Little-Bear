<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    page: number;
    pageSize: number;
    total: number;
    disabled?: boolean;
    label?: string;
    pageSizeOptions?: number[];
  }>(),
  {
    disabled: false,
    label: "分页",
    pageSizeOptions: () => [10, 20, 50, 100],
  },
);

const emit = defineEmits<{
  (event: "update:page", value: number): void;
  (event: "update:pageSize", value: number): void;
}>();

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
const start = computed(() => (props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1));
const end = computed(() => Math.min(props.total, props.page * props.pageSize));

function changePage(value: number): void {
  emit("update:page", Math.min(Math.max(1, value), totalPages.value));
}

function changePageSize(event: Event): void {
  const target = event.target as HTMLSelectElement;
  emit("update:pageSize", Number(target.value));
}
</script>

<template>
  <nav class="pagination-bar" :aria-label="props.label">
    <p class="pagination-bar__summary">
      {{ start }}-{{ end }} / {{ props.total }} 条
    </p>
    <div class="pagination-bar__controls">
      <select
        :value="props.pageSize"
        aria-label="每页数量"
        :disabled="props.disabled"
        @change="changePageSize"
      >
        <option v-for="option in props.pageSizeOptions" :key="option" :value="option">
          {{ option }} 条/页
        </option>
      </select>
      <button type="button" :disabled="props.disabled || props.page <= 1" @click="changePage(props.page - 1)">
        上一页
      </button>
      <span>{{ props.page }} / {{ totalPages }}</span>
      <button type="button" :disabled="props.disabled || props.page >= totalPages" @click="changePage(props.page + 1)">
        下一页
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 0;
  color: #667085;
}

.pagination-bar__summary {
  margin: 0;
}

.pagination-bar__controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pagination-bar select,
.pagination-bar button {
  min-height: 38px;
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: #fff;
  color: #182230;
}

.pagination-bar select {
  padding: 0 32px 0 12px;
}

.pagination-bar button {
  min-width: 76px;
  padding: 0 12px;
  cursor: pointer;
}

.pagination-bar button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.pagination-bar select:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

@media (max-width: 720px) {
  .pagination-bar,
  .pagination-bar__controls {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
