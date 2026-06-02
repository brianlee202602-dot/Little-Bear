<script setup lang="ts">
import { computed } from "vue";

import type { CurrentUserDepartment } from "@/api/auth";
import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminAssignableRoleOptionData } from "@/api/roles";
import type { Feedback, UserBusyState, UserCreateForm } from "@/features/users/userActionTypes";

type DepartmentSelectorItem = AdminDepartmentOptionData | CurrentUserDepartment | AdminDepartmentData;

const props = defineProps<{
  canCreate: boolean;
  canReadRoles: boolean;
  createDepartmentOptions: DepartmentSelectorItem[];
  createForm: UserCreateForm;
  departmentKeyword: string;
  feedback: Feedback | null;
  formatDepartmentLabel: (department: DepartmentSelectorItem | null | undefined) => string;
  formatRoleLabel: (role: AdminAssignableRoleOptionData | null | undefined) => string;
  initialAssignableRoles: AdminAssignableRoleOptionData[];
  roleKeyword: string;
  showHighRiskConfirm: boolean;
  busy: Pick<UserBusyState, "creating">;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "create"): void;
  (event: "searchDepartments"): void;
  (event: "searchRoles"): void;
  (event: "toggleDepartment", departmentId: string, checked: boolean): void;
  (event: "toggleRole", roleId: string, checked: boolean): void;
  (event: "update:createUsername", value: string): void;
  (event: "update:createName", value: string): void;
  (event: "update:initialPassword", value: string): void;
  (event: "update:passwordConfirm", value: string): void;
  (event: "update:createConfirmedHighRisk", value: boolean): void;
  (event: "update:departmentKeyword", value: string): void;
  (event: "update:roleKeyword", value: string): void;
}>();

const createUsername = computed({
  get: () => props.createForm.username,
  set: (value: string) => emit("update:createUsername", value),
});
const createName = computed({
  get: () => props.createForm.name,
  set: (value: string) => emit("update:createName", value),
});
const initialPassword = computed({
  get: () => props.createForm.initialPassword,
  set: (value: string) => emit("update:initialPassword", value),
});
const createPasswordConfirm = computed({
  get: () => props.createForm.passwordConfirm,
  set: (value: string) => emit("update:passwordConfirm", value),
});
const createConfirmedHighRisk = computed({
  get: () => props.createForm.confirmedHighRisk,
  set: (value: boolean) => emit("update:createConfirmedHighRisk", value),
});
const departmentKeywordModel = computed({
  get: () => props.departmentKeyword,
  set: (value: string) => emit("update:departmentKeyword", value),
});
const roleKeywordModel = computed({
  get: () => props.roleKeyword,
  set: (value: string) => emit("update:roleKeyword", value),
});
</script>

<template>
  <form @submit.prevent="emit('create')">
    <div class="modal__body">
      <div v-if="props.feedback" :class="['feedback feedback--wide', `feedback--${props.feedback.tone}`]">
        {{ props.feedback.message }}
      </div>
      <div class="form-grid form-grid--compact form-grid--modal">
        <label class="field">
          <span class="field__label">登录名</span>
          <p class="field__hint">用户的唯一登录标识。</p>
          <input v-model.trim="createUsername" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">显示名</span>
          <p class="field__hint">用于页面展示和审计摘要。</p>
          <input v-model.trim="createName" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">初始密码</span>
          <p class="field__hint">创建后将强制用户首次登录修改密码。</p>
          <input v-model="initialPassword" class="control" type="password" />
        </label>
        <label class="field">
          <span class="field__label">确认密码</span>
          <p class="field__hint">两次密码必须完全一致。</p>
          <input v-model="createPasswordConfirm" class="control" type="password" />
        </label>
        <div class="option-picker">
          <span class="field__label">归属部门</span>
          <p class="field__hint">至少选择一个部门；第一个选中的部门会作为用户主部门。</p>
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
            <label
              v-for="department in props.createDepartmentOptions"
              :key="department.id"
              class="option-card"
            >
              <input
                type="checkbox"
                :checked="props.createForm.departmentIds.includes(department.id)"
                @change="emit('toggleDepartment', department.id, ($event.target as HTMLInputElement).checked)"
              />
              <span>{{ props.formatDepartmentLabel(department) }}</span>
            </label>
          </div>
          <p v-if="!props.createDepartmentOptions.length" class="empty-state empty-state--plain">
            当前账号没有可用于创建用户的部门。
          </p>
        </div>
        <div v-if="props.canReadRoles" class="role-picker">
          <span class="field__label">初始角色</span>
          <p class="field__hint">未选择时后端会尝试授予普通员工默认角色。</p>
          <div class="selector-search">
            <input
              v-model.trim="roleKeywordModel"
              class="control control--compact"
              type="search"
              placeholder="搜索角色"
            />
            <button class="button button--secondary button--small" type="button" @click="emit('searchRoles')">
              查询角色
            </button>
          </div>
          <div class="option-picker__grid">
            <label v-for="role in props.initialAssignableRoles" :key="role.id" class="option-card">
              <input
                type="checkbox"
                :checked="props.createForm.roleIds.includes(role.id)"
                @change="emit('toggleRole', role.id, ($event.target as HTMLInputElement).checked)"
              />
              <span>{{ props.formatRoleLabel(role) }}</span>
            </label>
          </div>
        </div>
        <label v-if="props.showHighRiskConfirm" class="confirm confirm--inline modal-confirm">
          <input v-model="createConfirmedHighRisk" type="checkbox" />
          <span>确认授予高风险角色</span>
        </label>
      </div>
    </div>
    <footer class="modal__footer">
      <button class="button button--secondary" type="button" @click="emit('close')">
        取消
      </button>
      <button class="button" type="submit" :disabled="!props.canCreate">
        {{ props.busy.creating ? "创建中..." : "创建用户" }}
      </button>
    </footer>
  </form>
</template>
