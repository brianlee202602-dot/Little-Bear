<script setup lang="ts">
import { computed } from "vue";

import type { AdminDepartmentListItemData } from "@/api/departments";
import ListFilter from "@/components/ListFilter.vue";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { formatStatusText } from "@/utils/display";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type BusyState = {
  loading: boolean;
};

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type DepartmentSearchForm = {
  keyword: string;
  status: string;
};

const props = defineProps<{
  canLoadDepartmentAdmin: boolean;
  canManageDepartments: boolean;
  canReadDepartments: boolean;
  busy: BusyState;
  feedback: Feedback | null;
  searchForm: DepartmentSearchForm;
  departments: AdminDepartmentListItemData[];
  pagination: PaginationState;
  pageSizeOptions: number[];
}>();

const emit = defineEmits<{
  (event: "refresh"): void;
  (event: "create"): void;
  (event: "edit", department: AdminDepartmentListItemData): void;
  (event: "delete", department: AdminDepartmentListItemData): void;
  (event: "search"): void;
  (event: "update:keyword", value: string): void;
  (event: "update:status", value: string): void;
  (event: "update:page", value: number): void;
  (event: "update:pageSize", value: number): void;
}>();

const keyword = computed({
  get: () => props.searchForm.keyword,
  set: (value: string) => emit("update:keyword", value),
});

const status = computed({
  get: () => props.searchForm.status,
  set: (value: string) => emit("update:status", value),
});

const permissionMessage = computed(() => {
  if (props.canManageDepartments) {
    return "可创建、修改和删除部门";
  }
  if (props.canReadDepartments) {
    return "可读取部门";
  }
  return "缺少组织权限";
});

function toneClass(success: boolean): string {
  return success ? "tone-success" : "tone-warning";
}

function formatStatusOption(value: string): string {
  return formatStatusText(value);
}
</script>

<template>
  <section class="panel panel--wide">
    <header class="panel__header">
      <div>
        <h3>部门管理</h3>
        <p :class="toneClass(props.canLoadDepartmentAdmin)">
          {{ permissionMessage }}
        </p>
      </div>
      <div class="panel__actions">
        <button
          class="button button--secondary"
          type="button"
          :disabled="props.busy.loading || !props.canLoadDepartmentAdmin"
          @click="emit('refresh')"
        >
          {{ props.busy.loading ? "刷新中" : "刷新部门" }}
        </button>
        <button
          class="button"
          type="button"
          :disabled="!props.canManageDepartments"
          @click="emit('create')"
        >
          新增部门
        </button>
      </div>
    </header>

    <div class="admin-list-panel">
      <div
        v-if="props.feedback"
        :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]"
      >
        {{ props.feedback.message }}
      </div>

      <ListFilter :submit-disabled="props.busy.loading" @submit="emit('search')">
        <label class="field">
          <span class="field__label">关键词</span>
          <p class="field__hint">按部门名称过滤。</p>
          <input v-model.trim="keyword" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">部门状态</span>
          <p class="field__hint">留空时显示全部未删除部门。</p>
          <select v-model="status" class="control">
            <option value="">全部</option>
            <option value="active">{{ formatStatusOption("active") }}</option>
            <option value="disabled">{{ formatStatusOption("disabled") }}</option>
          </select>
        </label>
      </ListFilter>

      <div v-if="props.departments.length" class="entity-table entity-table--departments">
        <div class="entity-table__row entity-table__row--header">
          <span>部门</span>
          <span>状态</span>
          <span>默认部门</span>
          <span>操作</span>
        </div>
        <article
          v-for="department in props.departments"
          :key="department.id"
          class="entity-table__row"
        >
          <div class="entity-main">
            <strong>{{ department.name }}</strong>
            <span>{{ department.is_default ? "默认组织部门" : "普通部门" }}</span>
          </div>
          <div class="entity-cell">
            <StatusBadge
              :label="formatStatusText(department.status)"
              :tone="department.status === 'active' ? 'success' : 'neutral'"
            />
          </div>
          <div class="entity-cell">{{ department.is_default ? "是" : "否" }}</div>
          <div class="row-actions">
            <button
              class="button button--secondary button--small"
              type="button"
              :disabled="!props.canManageDepartments"
              @click="emit('edit', department)"
            >
              编辑
            </button>
            <button
              class="button button--danger button--small"
              type="button"
              :disabled="!props.canManageDepartments || department.is_default"
              @click="emit('delete', department)"
            >
              删除
            </button>
          </div>
        </article>
      </div>
      <p v-else class="empty-state empty-state--plain">当前尚未读取到部门。</p>

      <PaginationBar
        v-if="props.pagination.total > 0"
        label="部门列表分页"
        :page="props.pagination.page"
        :page-size="props.pagination.pageSize"
        :total="props.pagination.total"
        :page-size-options="props.pageSizeOptions"
        :disabled="props.busy.loading"
        @update:page="(page) => emit('update:page', page)"
        @update:page-size="(pageSize) => emit('update:pageSize', pageSize)"
      />
    </div>
  </section>
</template>
