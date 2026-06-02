import { computed, reactive, ref, type ComputedRef, type Ref } from "vue";

import type { CurrentUserDepartment } from "@/api/auth";
import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminUserData, AdminUserListItemData } from "@/api/users";

export type UserModalMode =
  | "create"
  | "edit"
  | "departments"
  | "roles"
  | "password"
  | "delete"
  | null;

export type UserCreateForm = {
  username: string;
  name: string;
  initialPassword: string;
  passwordConfirm: string;
  departmentIds: string[];
  roleIds: string[];
  confirmedHighRisk: boolean;
};

export type UserEditForm = {
  name: string;
  status: "active" | "disabled" | "locked";
  confirmedDisableAdmin: boolean;
};

export type UserDangerForm = {
  confirmedDelete: boolean;
};

export type PasswordResetForm = {
  newPassword: string;
  passwordConfirm: string;
  forceChangePassword: boolean;
  confirmed: boolean;
};

export type DepartmentSelectorItem =
  | AdminDepartmentOptionData
  | CurrentUserDepartment
  | AdminDepartmentData;

type UserBusyState = {
  creating: boolean;
  updating: boolean;
  resettingPassword: boolean;
};

export function useUserModals(options: {
  adminUsers: Ref<AdminUserListItemData[]>;
  busy: UserBusyState;
  canManageUsers: ComputedRef<boolean>;
  createUserDepartmentOptions: ComputedRef<DepartmentSelectorItem[]>;
  selectedAdminUserDetail: Ref<AdminUserData | null>;
}) {
  const selectedAdminUserId = ref("");
  const userModalMode = ref<UserModalMode>(null);
  const userCreateForm = reactive<UserCreateForm>({
    username: "",
    name: "",
    initialPassword: "",
    passwordConfirm: "",
    departmentIds: [],
    roleIds: [],
    confirmedHighRisk: false,
  });
  const userEditForm = reactive<UserEditForm>({
    name: "",
    status: "active",
    confirmedDisableAdmin: false,
  });
  const userDangerForm = reactive<UserDangerForm>({
    confirmedDelete: false,
  });
  const passwordResetForm = reactive<PasswordResetForm>({
    newPassword: "",
    passwordConfirm: "",
    forceChangePassword: true,
    confirmed: false,
  });

  const selectedAdminUser = computed(() =>
    options.selectedAdminUserDetail.value?.id === selectedAdminUserId.value
      ? options.selectedAdminUserDetail.value
      : null,
  );

  const selectedAdminUserIsSystemAdmin = computed(
    () => selectedAdminUser.value?.roles.some((role) => role.code === "system_admin") === true,
  );

  const canCreateAdminUser = computed(
    () =>
      options.canManageUsers.value &&
      userCreateForm.username.trim().length > 0 &&
      userCreateForm.name.trim().length > 0 &&
      userCreateForm.initialPassword.length > 0 &&
      userCreateForm.initialPassword === userCreateForm.passwordConfirm &&
      userCreateForm.departmentIds.length > 0 &&
      userCreateForm.departmentIds.every((id) =>
        options.createUserDepartmentOptions.value.some((department) => department.id === id),
      ) &&
      !options.busy.creating,
  );
  const canUpdateSelectedAdminUser = computed(
    () =>
      Boolean(selectedAdminUser.value) &&
      options.canManageUsers.value &&
      userEditForm.name.trim().length > 0 &&
      (userEditForm.status !== "disabled" ||
        !selectedAdminUserIsSystemAdmin.value ||
        userEditForm.confirmedDisableAdmin) &&
      !options.busy.updating,
  );
  const canDeleteSelectedAdminUser = computed(
    () =>
      Boolean(selectedAdminUser.value) &&
      options.canManageUsers.value &&
      userDangerForm.confirmedDelete &&
      !options.busy.updating,
  );
  const canResetSelectedUserPassword = computed(
    () =>
      Boolean(selectedAdminUser.value) &&
      options.canManageUsers.value &&
      passwordResetForm.newPassword.length > 0 &&
      passwordResetForm.newPassword === passwordResetForm.passwordConfirm &&
      passwordResetForm.confirmed &&
      !options.busy.resettingPassword,
  );

  function toggleCreateRole(roleId: string, checked: boolean): void {
    const next = new Set(userCreateForm.roleIds);
    if (checked) {
      next.add(roleId);
    } else {
      next.delete(roleId);
    }
    userCreateForm.roleIds = Array.from(next);
  }

  function toggleCreateDepartment(departmentId: string, checked: boolean): void {
    const next = new Set(userCreateForm.departmentIds);
    if (checked) {
      next.add(departmentId);
    } else {
      next.delete(departmentId);
    }
    userCreateForm.departmentIds = Array.from(next);
  }

  function ensureDefaultCreateDepartmentSelection(): void {
    const availableIds = new Set(
      options.createUserDepartmentOptions.value.map((department) => department.id),
    );
    userCreateForm.departmentIds = userCreateForm.departmentIds.filter((id) =>
      availableIds.has(id),
    );
    if (userCreateForm.departmentIds.length > 0) {
      return;
    }
    const defaultDepartment =
      options.createUserDepartmentOptions.value.find((department) => department.is_primary) ??
      options.createUserDepartmentOptions.value.find((department) => department.is_default) ??
      options.createUserDepartmentOptions.value[0];
    if (defaultDepartment) {
      userCreateForm.departmentIds = [defaultDepartment.id];
    }
  }

  function syncUserEditForm(): void {
    const user = selectedAdminUser.value;
    userEditForm.name = user?.name ?? "";
    userEditForm.status =
      user?.status === "disabled" || user?.status === "locked" || user?.status === "active"
        ? user.status
        : "active";
    userEditForm.confirmedDisableAdmin = false;
  }

  function resetCreateUserForm(): void {
    userCreateForm.username = "";
    userCreateForm.name = "";
    userCreateForm.initialPassword = "";
    userCreateForm.passwordConfirm = "";
    userCreateForm.departmentIds = [];
    userCreateForm.roleIds = [];
    userCreateForm.confirmedHighRisk = false;
    ensureDefaultCreateDepartmentSelection();
  }

  function closeUserModal(): void {
    userModalMode.value = null;
    userDangerForm.confirmedDelete = false;
    passwordResetForm.newPassword = "";
    passwordResetForm.passwordConfirm = "";
    passwordResetForm.confirmed = false;
  }

  function clearUserModalState(): void {
    selectedAdminUserId.value = "";
    options.selectedAdminUserDetail.value = null;
    userModalMode.value = null;
    userDangerForm.confirmedDelete = false;
    userEditForm.confirmedDisableAdmin = false;
    passwordResetForm.newPassword = "";
    passwordResetForm.passwordConfirm = "";
    passwordResetForm.forceChangePassword = true;
    passwordResetForm.confirmed = false;
    resetCreateUserForm();
  }

  return {
    canCreateAdminUser,
    canDeleteSelectedAdminUser,
    canResetSelectedUserPassword,
    canUpdateSelectedAdminUser,
    clearUserModalState,
    closeUserModal,
    ensureDefaultCreateDepartmentSelection,
    passwordResetForm,
    resetCreateUserForm,
    selectedAdminUser,
    selectedAdminUserId,
    selectedAdminUserIsSystemAdmin,
    syncUserEditForm,
    toggleCreateDepartment,
    toggleCreateRole,
    userCreateForm,
    userDangerForm,
    userEditForm,
    userModalMode,
  };
}
