<script setup lang="ts">
import { computed } from "vue";

import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminUserData } from "@/api/users";
import PaginationBar from "@/components/PaginationBar.vue";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type BusyState = {
  loading: boolean;
  updatingDepartments: boolean;
};

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type UserDepartmentForm = {
  departmentIds: string[];
  confirmedReplacePrimary: boolean;
};

const props = defineProps<{
  open: boolean;
  selectedUser: AdminUserData | null;
  selectedDepartmentsForDisplay: AdminDepartmentData[];
  selectedDepartmentIds: Set<string>;
  departmentKeyword: string;
  activeDepartments: AdminDepartmentOptionData[];
  userDepartmentForm: UserDepartmentForm;
  selectedUserPrimaryDepartmentWillChange: boolean;
  canManageDepartments: boolean;
  canSave: boolean;
  busy: BusyState;
  feedback: Feedback | null;
  pagination: PaginationState;
  pageSizeOptions: number[];
  formatDepartmentLabel: (department: AdminDepartmentData | AdminDepartmentOptionData | null | undefined) => string;
  formatDepartmentList: (departments: AdminDepartmentData[]) => string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "save"): void;
  (event: "searchDepartments"): void;
  (event: "toggleDepartment", departmentId: string, checked: boolean): void;
  (event: "update:departmentKeyword", value: string): void;
  (event: "update:confirmedReplacePrimary", value: boolean): void;
  (event: "update:page", value: number): void;
  (event: "update:pageSize", value: number): void;
}>();

const departmentKeywordModel = computed({
  get: () => props.departmentKeyword,
  set: (value: string) => emit("update:departmentKeyword", value),
});

const confirmedReplacePrimary = computed({
  get: () => props.userDepartmentForm.confirmedReplacePrimary,
  set: (value: boolean) => emit("update:confirmedReplacePrimary", value),
});

const primaryDepartment = computed(
  () =>
    props.selectedDepartmentsForDisplay.find((department) => department.is_primary) ??
    props.selectedDepartmentsForDisplay[0],
);
</script>

<template>
  <div v-if="props.open" class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="user-departments-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">用户管理</p>
          <h3 id="user-departments-modal-title">维护部门归属</h3>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <div v-if="props.selectedUser">
        <div class="modal__body">
          <dl class="summary summary--compact modal-summary">
            <div class="summary__row">
              <dt>用户</dt>
              <dd>{{ props.selectedUser.name || props.selectedUser.username }}</dd>
            </div>
            <div class="summary__row">
              <dt>当前部门</dt>
              <dd>{{ props.formatDepartmentList(props.selectedDepartmentsForDisplay) }}</dd>
            </div>
            <div class="summary__row">
              <dt>主部门</dt>
              <dd>{{ props.formatDepartmentLabel(primaryDepartment) }}</dd>
            </div>
          </dl>
          <PaginationBar
            v-if="props.pagination.total > props.pagination.pageSize"
            class="pagination-bar--compact"
            label="用户当前部门分页"
            :page="props.pagination.page"
            :page-size="props.pagination.pageSize"
            :total="props.pagination.total"
            :page-size-options="props.pageSizeOptions"
            :disabled="props.busy.loading"
            @update:page="(page) => emit('update:page', page)"
            @update:page-size="(pageSize) => emit('update:pageSize', pageSize)"
          />
          <div
            v-if="props.feedback"
            :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]"
          >
            {{ props.feedback.message }}
          </div>
          <div class="option-picker">
            <span class="field__label">调整归属部门</span>
            <p class="field__hint">至少选择一个部门；保存时第一个被选中的部门会作为主部门。</p>
            <div class="selector-search">
              <input
                v-model.trim="departmentKeywordModel"
                class="control control--compact"
                type="search"
                placeholder="搜索部门"
              />
              <button class="button button--secondary button--small" type="button" @click="emit('searchDepartments')">
                查询部门
              </button>
            </div>
            <div class="option-picker__grid">
              <label v-for="department in props.activeDepartments" :key="department.id" class="option-card">
                <input
                  type="checkbox"
                  :checked="props.selectedDepartmentIds.has(department.id)"
                  :disabled="!props.canManageDepartments || props.busy.updatingDepartments"
                  @change="emit('toggleDepartment', department.id, ($event.target as HTMLInputElement).checked)"
                />
                <span>
                  {{ props.formatDepartmentLabel(department) }}
                  <small v-if="props.userDepartmentForm.departmentIds[0] === department.id">主部门</small>
                </span>
              </label>
            </div>
            <p v-if="!props.activeDepartments.length" class="empty-state empty-state--plain">当前没有可用的启用部门。</p>
          </div>
          <label v-if="props.selectedUserPrimaryDepartmentWillChange" class="confirm confirm--inline modal-confirm">
            <input v-model="confirmedReplacePrimary" type="checkbox" />
            <span>确认更换该用户的主部门</span>
          </label>
        </div>
        <footer class="modal__footer">
          <button class="button button--secondary" type="button" @click="emit('close')">
            取消
          </button>
          <button class="button" type="button" :disabled="!props.canSave" @click="emit('save')">
            {{ props.busy.updatingDepartments ? "保存中..." : "保存部门归属" }}
          </button>
        </footer>
      </div>
    </section>
  </div>
</template>
