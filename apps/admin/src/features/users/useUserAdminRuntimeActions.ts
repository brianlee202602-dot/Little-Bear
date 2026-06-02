import type { ComputedRef, Ref } from "vue";

import {
  getAdminUser,
  listAdminUsers,
  type AdminUserData,
  type AdminUserListItemData,
} from "@/api/users";
import type { AdminDepartmentData } from "@/api/departments";
import type {
  PasswordResetForm,
  UserDangerForm,
  UserModalMode,
} from "@/features/users/useUserModals";
import type { UserDepartmentForm } from "@/features/users/useUserDepartmentBindings";
import {
  clearPaginationState,
  syncPaginationState,
  type PaginationState,
} from "@/utils/pagination";
import type { AdminRoleBindingData } from "@/api/roles";
import type { RoleBindingForm } from "@/features/users/useUserRoleBindings";

type UseUserAdminRuntimeActionsOptions = {
  adminUsers: Ref<AdminUserListItemData[]>;
  canLoadUserAdmin: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  canReadRoles: ComputedRef<boolean>;
  canReadUsers: ComputedRef<boolean>;
  clearDepartmentOptions: () => void;
  clearKnowledgeBaseOptions: () => void;
  clearUserDepartmentBindingState: () => void;
  clearUserModalState: () => void;
  clearUserRoleBindingState: () => void;
  ensureAccessToken: () => Promise<string | null>;
  ensureDefaultCreateDepartmentSelection: () => void;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  openUserDepartmentsModalBase: (
    user: AdminUserListItemData,
    selectUser: (userId: string) => Promise<void>,
  ) => Promise<void>;
  openUserRolesModalBase: (
    user: AdminUserListItemData,
    selectUser: (userId: string) => Promise<void>,
  ) => Promise<void>;
  passwordResetForm: PasswordResetForm;
  refreshAssignableRoleOptions: (existingAccessToken?: string) => Promise<void>;
  refreshDepartmentOptions: (existingAccessToken?: string) => Promise<void>;
  refreshKnowledgeBaseOptions: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedUserDepartments: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedUserRoleBindings: (existingAccessToken?: string) => Promise<void>;
  resetCreateUserForm: () => void;
  roleBindingForm: RoleBindingForm;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedAdminUserDetail: Ref<AdminUserData | null>;
  selectedAdminUserId: Ref<string>;
  selectedRoleBindingKey: ComputedRef<string>;
  selectedUserDepartmentPagination: PaginationState;
  selectedUserDepartments: Ref<AdminDepartmentData[]>;
  selectedUserRoleBindingKeys: ComputedRef<Set<string>>;
  selectedUserRoleBindingPagination: PaginationState;
  selectedUserRoleBindings: Ref<AdminRoleBindingData[]>;
  selectNextAvailableRoleBindingTarget: () => void;
  syncRoleBindingScopeDefault: () => void;
  syncSelectedUserDepartmentForm: () => void;
  syncUserEditForm: () => void;
  userAdminBusy: {
    loading: boolean;
  };
  userAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  userDangerForm: UserDangerForm;
  userDepartmentForm: UserDepartmentForm;
  userModalMode: Ref<UserModalMode>;
  userPagination: PaginationState;
  userSearchForm: {
    keyword: string;
    status: string;
  };
};

export function useUserAdminRuntimeActions(options: UseUserAdminRuntimeActionsOptions) {
  async function refreshUserRoleAdminState(): Promise<void> {
    if (!options.canLoadUserAdmin.value) {
      clearUserAdminState();
      options.clearDepartmentOptions();
      options.clearKnowledgeBaseOptions();
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.userAdminBusy.loading = true;
    try {
      if (options.canReadRoles.value) {
        await options.refreshAssignableRoleOptions(accessToken);
      } else {
        options.clearUserRoleBindingState();
      }
      if (options.canReadDepartments.value) {
        await options.refreshDepartmentOptions(accessToken);
      } else {
        options.clearDepartmentOptions();
        options.ensureDefaultCreateDepartmentSelection();
      }
      if (options.canManageKnowledgeBases.value) {
        await options.refreshKnowledgeBaseOptions(accessToken);
      } else {
        options.clearKnowledgeBaseOptions();
      }
      if (options.canReadUsers.value) {
        const usersResponse = await listAdminUsers(accessToken, {
          keyword: options.userSearchForm.keyword.trim() || undefined,
          status: options.userSearchForm.status || undefined,
          page: options.userPagination.page,
          page_size: options.userPagination.pageSize,
        });
        options.adminUsers.value = usersResponse.data;
        syncPaginationState(options.userPagination, usersResponse.pagination);
        if (
          !options.selectedAdminUserId.value ||
          !options.adminUsers.value.some(
            (user: AdminUserListItemData) => user.id === options.selectedAdminUserId.value,
          )
        ) {
          options.selectedAdminUserId.value = options.adminUsers.value[0]?.id ?? "";
          options.selectedAdminUserDetail.value = null;
          clearPaginationState(options.selectedUserDepartmentPagination);
          clearPaginationState(options.selectedUserRoleBindingPagination);
        } else if (
          options.selectedAdminUserDetail.value?.id !== options.selectedAdminUserId.value
        ) {
          options.selectedAdminUserDetail.value = null;
        }
      } else {
        options.adminUsers.value = [];
        clearPaginationState(options.userPagination);
        options.selectedAdminUserId.value = "";
        options.selectedAdminUserDetail.value = null;
        options.clearUserDepartmentBindingState();
        options.clearUserRoleBindingState();
      }
      if (options.selectedAdminUserId.value && options.selectedAdminUserDetail.value) {
        await refreshSelectedAdminUserDetail(accessToken);
      }
      await options.refreshSelectedUserDepartments(accessToken);
      await options.refreshSelectedUserRoleBindings(accessToken);
      if (
        !options.roleBindingForm.roleId ||
        options.selectedUserRoleBindingKeys.value.has(options.selectedRoleBindingKey.value)
      ) {
        options.selectNextAvailableRoleBindingTarget();
      } else {
        options.syncRoleBindingScopeDefault();
      }
      options.userAdminFeedback.value = {
        tone: "success",
        message: "用户与角色数据已刷新。",
      };
    } catch (error) {
      options.userAdminFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取用户与角色数据失败"),
      };
    } finally {
      options.userAdminBusy.loading = false;
    }
  }

  async function selectAdminUser(userId: string): Promise<void> {
    options.selectedAdminUserId.value = userId;
    options.selectedAdminUserDetail.value = null;
    clearPaginationState(options.selectedUserDepartmentPagination);
    clearPaginationState(options.selectedUserRoleBindingPagination);
    options.userDangerForm.confirmedDelete = false;
    options.passwordResetForm.newPassword = "";
    options.passwordResetForm.passwordConfirm = "";
    options.passwordResetForm.confirmed = false;
    options.userDepartmentForm.confirmedReplacePrimary = false;
    try {
      await refreshSelectedAdminUserDetail();
      options.selectedUserDepartments.value = options.selectedAdminUser.value?.departments ?? [];
      options.syncSelectedUserDepartmentForm();
      options.roleBindingForm.confirmedRemoveAdmin = false;
      await options.refreshSelectedUserDepartments();
      await options.refreshSelectedUserRoleBindings();
      options.syncUserEditForm();
    } catch (error) {
      options.selectedUserDepartments.value = options.selectedAdminUser.value?.departments ?? [];
      options.selectedUserRoleBindings.value = [];
      options.syncSelectedUserDepartmentForm();
      options.syncUserEditForm();
      options.userAdminFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取用户部门或角色绑定失败"),
      };
    }
  }

  async function refreshSelectedAdminUserDetail(existingAccessToken?: string): Promise<void> {
    if (!options.selectedAdminUserId.value) {
      options.selectedAdminUserDetail.value = null;
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await getAdminUser(options.selectedAdminUserId.value, accessToken);
    options.selectedAdminUserDetail.value = response.data;
  }

  function openCreateUserModal(): void {
    options.resetCreateUserForm();
    options.ensureDefaultCreateDepartmentSelection();
    options.userAdminFeedback.value = null;
    options.userModalMode.value = "create";
  }

  async function openEditUserModal(user: AdminUserListItemData): Promise<void> {
    await selectAdminUser(user.id);
    options.userModalMode.value = "edit";
    options.syncUserEditForm();
  }

  async function openUserDepartmentsModal(user: AdminUserListItemData): Promise<void> {
    await options.openUserDepartmentsModalBase(user, selectAdminUser);
  }

  async function openUserRolesModal(user: AdminUserListItemData): Promise<void> {
    await options.openUserRolesModalBase(user, selectAdminUser);
  }

  async function openPasswordResetModal(user: AdminUserListItemData): Promise<void> {
    await selectAdminUser(user.id);
    options.userModalMode.value = "password";
  }

  async function openDeleteUserModal(user: AdminUserListItemData): Promise<void> {
    options.userDangerForm.confirmedDelete = false;
    await selectAdminUser(user.id);
    options.userModalMode.value = "delete";
  }

  function clearUserAdminState(): void {
    options.adminUsers.value = [];
    clearPaginationState(options.userPagination);
    options.clearUserModalState();
    options.clearUserDepartmentBindingState();
    options.clearUserRoleBindingState();
    options.userSearchForm.keyword = "";
    options.userSearchForm.status = "";
    options.userAdminFeedback.value = null;
  }

  return {
    clearUserAdminState,
    openCreateUserModal,
    openDeleteUserModal,
    openEditUserModal,
    openPasswordResetModal,
    openUserDepartmentsModal,
    openUserRolesModal,
    refreshSelectedAdminUserDetail,
    refreshUserRoleAdminState,
    selectAdminUser,
  };
}
