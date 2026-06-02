<script setup lang="ts">
import { computed } from "vue";

import type { AdminUserListItemData } from "@/api/users";
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

type UserSearchForm = {
  keyword: string;
  status: string;
};

const props = defineProps<{
  canLoadUserAdmin: boolean;
  canManageUsers: boolean;
  canManageRoles: boolean;
  canReadUsers: boolean;
  canReadRoles: boolean;
  canReadDepartments: boolean;
  busy: BusyState;
  feedback: Feedback | null;
  searchForm: UserSearchForm;
  users: AdminUserListItemData[];
  pagination: PaginationState;
  pageSizeOptions: number[];
}>();

const emit = defineEmits<{
  (event: "refresh"): void;
  (event: "create"): void;
  (event: "edit", user: AdminUserListItemData): void;
  (event: "departments", user: AdminUserListItemData): void;
  (event: "roles", user: AdminUserListItemData): void;
  (event: "password", user: AdminUserListItemData): void;
  (event: "delete", user: AdminUserListItemData): void;
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
  if (props.canManageUsers && props.canManageRoles) {
    return "可管理用户、部门归属和角色绑定";
  }
  if (props.canReadUsers || props.canReadRoles) {
    return "可读取用户信息";
  }
  return "缺少用户或角色权限";
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
        <h3>用户管理</h3>
        <p :class="toneClass(props.canLoadUserAdmin)">
          {{ permissionMessage }}
        </p>
      </div>
      <div class="panel__actions">
        <button
          class="button button--secondary"
          type="button"
          :disabled="props.busy.loading || !props.canLoadUserAdmin"
          @click="emit('refresh')"
        >
          {{ props.busy.loading ? "刷新中" : "刷新用户" }}
        </button>
        <button class="button" type="button" :disabled="!props.canManageUsers" @click="emit('create')">
          新增用户
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
          <p class="field__hint">按登录名或显示名过滤用户。</p>
          <input v-model.trim="keyword" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">账号状态</span>
          <p class="field__hint">留空时显示全部未删除用户。</p>
          <select v-model="status" class="control">
            <option value="">全部</option>
            <option value="active">{{ formatStatusOption("active") }}</option>
            <option value="disabled">{{ formatStatusOption("disabled") }}</option>
            <option value="locked">{{ formatStatusOption("locked") }}</option>
          </select>
        </label>
      </ListFilter>

      <div v-if="props.users.length" class="entity-table entity-table--users">
        <div class="entity-table__row entity-table__row--header">
          <span>用户</span>
          <span>状态</span>
          <span>部门</span>
          <span>角色</span>
          <span>操作</span>
        </div>
        <article v-for="user in props.users" :key="user.id" class="entity-table__row">
          <div class="entity-main">
            <strong>{{ user.name || user.username }}</strong>
            <span>{{ user.username }}</span>
          </div>
          <div class="entity-cell">
            <StatusBadge
              :label="formatStatusText(user.status)"
              :tone="user.status === 'active' ? 'success' : user.status === 'locked' ? 'warning' : 'neutral'"
            />
          </div>
          <div class="badge-list">
            <span v-for="departmentName in user.department_names" :key="departmentName" class="badge">
              {{ departmentName }}
            </span>
            <span v-if="!user.department_names.length" class="empty-inline">-</span>
          </div>
          <div class="badge-list">
            <span v-for="roleName in user.role_names" :key="roleName" class="badge">
              {{ roleName }}
            </span>
            <span v-if="!user.role_names.length" class="empty-inline">-</span>
          </div>
          <div class="row-actions row-actions--dense row-actions--knowledge">
            <button
              class="button button--secondary button--small"
              type="button"
              :disabled="!props.canManageUsers"
              @click="emit('edit', user)"
            >
              编辑
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              :disabled="!props.canReadDepartments"
              @click="emit('departments', user)"
            >
              部门
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              :disabled="!props.canReadRoles"
              @click="emit('roles', user)"
            >
              角色
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              :disabled="!props.canManageUsers"
              @click="emit('password', user)"
            >
              密码
            </button>
            <button
              class="button button--danger button--small"
              type="button"
              :disabled="!props.canManageUsers"
              @click="emit('delete', user)"
            >
              删除
            </button>
          </div>
        </article>
      </div>
      <p v-else class="empty-state empty-state--plain">当前尚未读取到用户。</p>

      <PaginationBar
        v-if="props.pagination.total > 0"
        label="用户列表分页"
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
