<script setup lang="ts">
import { computed } from "vue";

import type { CurrentUserDepartment } from "@/api/auth";
import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminAssignableRoleOptionData } from "@/api/roles";
import type { AdminUserData } from "@/api/users";
import UserCreateFormContent from "@/features/users/UserCreateFormContent.vue";
import UserDeleteFormContent from "@/features/users/UserDeleteFormContent.vue";
import UserEditFormContent from "@/features/users/UserEditFormContent.vue";
import type {
  Feedback,
  UserBusyState,
  UserCreateForm,
  UserDangerForm,
  UserEditForm,
} from "@/features/users/userActionTypes";
import type { UserModalMode } from "@/features/users/useUserModals";

type DepartmentSelectorItem = AdminDepartmentOptionData | CurrentUserDepartment | AdminDepartmentData;

const props = defineProps<{
  mode: UserModalMode;
  selectedUser: AdminUserData | null;
  createForm: UserCreateForm;
  editForm: UserEditForm;
  dangerForm: UserDangerForm;
  departmentKeyword: string;
  roleKeyword: string;
  createDepartmentOptions: DepartmentSelectorItem[];
  initialAssignableRoles: AdminAssignableRoleOptionData[];
  canReadRoles: boolean;
  showHighRiskConfirm: boolean;
  selectedUserIsSystemAdmin: boolean;
  busy: Pick<UserBusyState, "creating" | "updating">;
  feedback: Feedback | null;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  formatDepartmentLabel: (department: DepartmentSelectorItem | null | undefined) => string;
  formatRoleLabel: (role: AdminAssignableRoleOptionData | null | undefined) => string;
  formatRoleList: (roles: AdminUserData["roles"]) => string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "create"): void;
  (event: "update"): void;
  (event: "delete"): void;
  (event: "searchDepartments"): void;
  (event: "searchRoles"): void;
  (event: "toggleDepartment", departmentId: string, checked: boolean): void;
  (event: "toggleRole", roleId: string, checked: boolean): void;
  (event: "update:createUsername", value: string): void;
  (event: "update:createName", value: string): void;
  (event: "update:initialPassword", value: string): void;
  (event: "update:passwordConfirm", value: string): void;
  (event: "update:createConfirmedHighRisk", value: boolean): void;
  (event: "update:editName", value: string): void;
  (event: "update:editStatus", value: "active" | "disabled" | "locked"): void;
  (event: "update:confirmedDisableAdmin", value: boolean): void;
  (event: "update:confirmedDelete", value: boolean): void;
  (event: "update:departmentKeyword", value: string): void;
  (event: "update:roleKeyword", value: string): void;
}>();

const isOpen = computed(() => props.mode === "create" || props.mode === "edit" || props.mode === "delete");
const title = computed(() => {
  if (props.mode === "create") {
    return "新增用户";
  }
  if (props.mode === "edit") {
    return "编辑用户";
  }
  return "删除用户";
});
</script>

<template>
  <div v-if="isOpen" class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="user-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">用户管理</p>
          <h3 id="user-modal-title">{{ title }}</h3>
        </div>
        <button class="button button--secondary button--small" type="button" @click="emit('close')">
          关闭
        </button>
      </header>

      <UserCreateFormContent
        v-if="props.mode === 'create'"
        :busy="props.busy"
        :can-create="props.canCreate"
        :can-read-roles="props.canReadRoles"
        :create-department-options="props.createDepartmentOptions"
        :create-form="props.createForm"
        :department-keyword="props.departmentKeyword"
        :feedback="props.feedback"
        :format-department-label="props.formatDepartmentLabel"
        :format-role-label="props.formatRoleLabel"
        :initial-assignable-roles="props.initialAssignableRoles"
        :role-keyword="props.roleKeyword"
        :show-high-risk-confirm="props.showHighRiskConfirm"
        @close="emit('close')"
        @create="emit('create')"
        @search-departments="emit('searchDepartments')"
        @search-roles="emit('searchRoles')"
        @toggle-department="(departmentId, checked) => emit('toggleDepartment', departmentId, checked)"
        @toggle-role="(roleId, checked) => emit('toggleRole', roleId, checked)"
        @update:create-username="(value) => emit('update:createUsername', value)"
        @update:create-name="(value) => emit('update:createName', value)"
        @update:initial-password="(value) => emit('update:initialPassword', value)"
        @update:password-confirm="(value) => emit('update:passwordConfirm', value)"
        @update:create-confirmed-high-risk="(value) => emit('update:createConfirmedHighRisk', value)"
        @update:department-keyword="(value) => emit('update:departmentKeyword', value)"
        @update:role-keyword="(value) => emit('update:roleKeyword', value)"
      />

      <UserEditFormContent
        v-else-if="props.mode === 'edit' && props.selectedUser"
        :busy="props.busy"
        :can-update="props.canUpdate"
        :edit-form="props.editForm"
        :feedback="props.feedback"
        :format-role-list="props.formatRoleList"
        :selected-user="props.selectedUser"
        :selected-user-is-system-admin="props.selectedUserIsSystemAdmin"
        @close="emit('close')"
        @update="emit('update')"
        @update:edit-name="(value) => emit('update:editName', value)"
        @update:edit-status="(value) => emit('update:editStatus', value)"
        @update:confirmed-disable-admin="(value) => emit('update:confirmedDisableAdmin', value)"
      />

      <UserDeleteFormContent
        v-else-if="props.mode === 'delete' && props.selectedUser"
        :busy="props.busy"
        :can-delete="props.canDelete"
        :danger-form="props.dangerForm"
        :feedback="props.feedback"
        :selected-user="props.selectedUser"
        @close="emit('close')"
        @delete="emit('delete')"
        @update:confirmed-delete="(value) => emit('update:confirmedDelete', value)"
      />
    </section>
  </div>
</template>
