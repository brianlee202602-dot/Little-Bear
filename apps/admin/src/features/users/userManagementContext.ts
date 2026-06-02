import { computed, type ComputedRef, type Ref } from "vue";

import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminKnowledgeBaseOptionData } from "@/api/knowledgeBases";
import type {
  AdminAssignableRoleOptionData,
  AdminRoleBindingData,
  AdminRoleData,
} from "@/api/roles";
import type { AdminUserData, AdminUserListItemData } from "@/api/users";
import type { UserDepartmentForm } from "@/features/users/useUserDepartmentBindings";
import type {
  DepartmentSelectorItem,
  PasswordResetForm,
  UserCreateForm,
  UserDangerForm,
  UserEditForm,
  UserModalMode,
} from "@/features/users/useUserModals";
import type { RoleBindingForm, RoleScopeType } from "@/features/users/useUserRoleBindings";
import type { PaginationState } from "@/utils/pagination";

type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

interface OptionSearchForm {
  departmentKeyword: string;
  knowledgeBaseKeyword: string;
  roleKeyword: string;
}

interface UserManagementContextDependencies {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  activeKnowledgeBases: ComputedRef<AdminKnowledgeBaseOptionData[]>;
  addSelectedUserRoleBinding: () => Promise<void>;
  adminUsers: Ref<AdminUserListItemData[]>;
  assignableRoles: ComputedRef<AdminAssignableRoleOptionData[]>;
  canAddSelectedUserRole: ComputedRef<boolean>;
  canCreateAdminUser: ComputedRef<boolean>;
  canDeleteSelectedAdminUser: ComputedRef<boolean>;
  canLoadUserAdmin: ComputedRef<boolean>;
  canManageDepartments: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canManageRoles: ComputedRef<boolean>;
  canManageUsers: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  canReadRoles: ComputedRef<boolean>;
  canReadUsers: ComputedRef<boolean>;
  canResetSelectedUserPassword: ComputedRef<boolean>;
  canSaveSelectedUserDepartments: ComputedRef<boolean>;
  canUpdateSelectedAdminUser: ComputedRef<boolean>;
  changePaginationPage: (
    state: PaginationState,
    refresh: () => Promise<void>,
    page: number,
  ) => void;
  changePaginationPageSize: (
    state: PaginationState,
    refresh: () => Promise<void>,
    pageSize?: number,
  ) => void;
  closeUserModal: () => void;
  createUserDepartmentOptions: ComputedRef<DepartmentSelectorItem[]>;
  deleteSelectedAdminUser: () => Promise<void>;
  formatDepartmentLabel: (
    department: { code?: string | null; name?: string | null } | null | undefined,
  ) => string;
  formatDepartmentList: (
    departments: Array<{ code?: string | null; name?: string | null }>,
  ) => string;
  formatKnowledgeBaseLabel: (
    knowledgeBase: { name?: string | null } | null | undefined,
  ) => string;
  formatRoleBindingScope: (
    binding: AdminRoleBindingData,
    lookups: {
      formatDepartmentById: (departmentId: string | null | undefined) => string;
      formatKnowledgeBaseById: (knowledgeBaseId: string | null | undefined) => string;
    },
  ) => string;
  formatRoleCodeLabel: (roleCode: string | null | undefined, fallback?: string) => string;
  formatRoleLabel: (
    role: { code?: string | null; name?: string | null } | null | undefined,
  ) => string;
  formatRoleList: (roles: AdminRoleData[]) => string;
  formatRoleScopeType: (scopeType: string | null | undefined) => string;
  initialAssignableRoles: ComputedRef<AdminAssignableRoleOptionData[]>;
  isHighRiskAdminRole: (role: AdminAssignableRoleOptionData | AdminRoleData) => boolean;
  onRoleBindingRoleChange: (roleId: string) => void;
  openCreateUserModal: () => void;
  openDeleteUserModal: (user: AdminUserListItemData) => Promise<void>;
  openEditUserModal: (user: AdminUserListItemData) => Promise<void>;
  openPasswordResetModal: (user: AdminUserListItemData) => Promise<void>;
  openUserDepartmentsModal: (user: AdminUserListItemData) => Promise<void>;
  openUserRolesModal: (user: AdminUserListItemData) => Promise<void>;
  optionSearchForm: OptionSearchForm;
  pageSizeOptions: number[];
  passwordResetForm: PasswordResetForm;
  refreshAssignableRoleOptionsFromSearch: () => void;
  refreshDepartmentOptionsFromSearch: () => void;
  refreshFirstPage: (state: PaginationState, refresh: () => Promise<void>) => void;
  refreshKnowledgeBaseOptionsFromSearch: () => void;
  refreshSelectedUserDepartmentsPage: () => Promise<void>;
  refreshSelectedUserRoleBindingsPage: () => Promise<void>;
  refreshUserRoleAdminState: () => Promise<void>;
  revokeSelectedUserRoleBinding: (binding: AdminRoleBindingData) => Promise<void>;
  roleBindingDisabledReason: ComputedRef<string>;
  roleBindingForm: RoleBindingForm;
  saveSelectedUserDepartments: () => Promise<void>;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedAdminUserIsSystemAdmin: ComputedRef<boolean>;
  selectedCreateRoles: ComputedRef<AdminAssignableRoleOptionData[]>;
  selectedRoleBindingScopeType: ComputedRef<RoleScopeType>;
  selectedUserDepartmentIds: ComputedRef<Set<string>>;
  selectedUserDepartmentPagination: PaginationState;
  selectedUserDepartmentsForDisplay: ComputedRef<AdminDepartmentData[]>;
  selectedUserPrimaryDepartmentWillChange: ComputedRef<boolean>;
  selectedUserRoleBindingPagination: PaginationState;
  selectedUserRoleBindings: Ref<AdminRoleBindingData[]>;
  submitCreateAdminUser: () => Promise<void>;
  submitPasswordReset: () => Promise<void>;
  submitPatchSelectedAdminUser: () => Promise<void>;
  toggleCreateDepartment: (departmentId: string, checked: boolean) => void;
  toggleCreateRole: (roleId: string, checked: boolean) => void;
  toggleSelectedUserDepartment: (departmentId: string, checked: boolean) => void;
  userAdminBusy: {
    creating: boolean;
    loading: boolean;
    resettingPassword: boolean;
    updating: boolean;
    updatingDepartments: boolean;
    updatingRoles: boolean;
  };
  userAdminFeedback: Ref<Feedback | null>;
  userCreateForm: UserCreateForm;
  userDangerForm: UserDangerForm;
  userDepartmentForm: UserDepartmentForm;
  userEditForm: UserEditForm;
  userModalMode: Ref<UserModalMode>;
  userPagination: PaginationState;
  userSearchForm: {
    keyword: string;
    status: string;
  };
}

export type UserManagementContext = ReturnType<typeof createUserManagementContext>;

export function createUserManagementContext(options: UserManagementContextDependencies) {
  function formatDepartmentById(departmentId: string | null | undefined): string {
    if (!departmentId) {
      return "-";
    }
    const department =
      options.activeDepartments.value.find((item) => item.id === departmentId) ??
      options.selectedUserDepartmentsForDisplay.value.find((item) => item.id === departmentId);
    return department ? options.formatDepartmentLabel(department) : "未读取到部门";
  }

  function formatKnowledgeBaseById(knowledgeBaseId: string | null | undefined): string {
    if (!knowledgeBaseId) {
      return "-";
    }
    const knowledgeBase = options.activeKnowledgeBases.value.find(
      (item) => item.id === knowledgeBaseId,
    );
    return knowledgeBase ? options.formatKnowledgeBaseLabel(knowledgeBase) : "未读取到知识库";
  }

  return computed(() => ({
    activeDepartments: options.activeDepartments.value,
    activeKnowledgeBases: options.activeKnowledgeBases.value,
    addSelectedUserRoleBinding: options.addSelectedUserRoleBinding,
    assignableRoles: options.assignableRoles.value,
    busy: options.userAdminBusy,
    canAddSelectedUserRole: options.canAddSelectedUserRole.value,
    canCreateAdminUser: options.canCreateAdminUser.value,
    canDeleteSelectedAdminUser: options.canDeleteSelectedAdminUser.value,
    canLoadUserAdmin: options.canLoadUserAdmin.value,
    canManageDepartments: options.canManageDepartments.value,
    canManageKnowledgeBases: options.canManageKnowledgeBases.value,
    canManageRoles: options.canManageRoles.value,
    canManageUsers: options.canManageUsers.value,
    canReadDepartments: options.canReadDepartments.value,
    canReadRoles: options.canReadRoles.value,
    canReadUsers: options.canReadUsers.value,
    canResetSelectedUserPassword: options.canResetSelectedUserPassword.value,
    canSaveSelectedUserDepartments: options.canSaveSelectedUserDepartments.value,
    canUpdateSelectedAdminUser: options.canUpdateSelectedAdminUser.value,
    closeUserModal: options.closeUserModal,
    createUserDepartmentOptions: options.createUserDepartmentOptions.value,
    deleteSelectedAdminUser: options.deleteSelectedAdminUser,
    departmentKeyword: options.optionSearchForm.departmentKeyword,
    feedback: options.userAdminFeedback.value,
    formatDepartmentLabel: options.formatDepartmentLabel,
    formatDepartmentList: options.formatDepartmentList,
    formatKnowledgeBaseLabel: options.formatKnowledgeBaseLabel,
    formatRoleBindingScope: (binding: AdminRoleBindingData) =>
      options.formatRoleBindingScope(binding, {
        formatDepartmentById,
        formatKnowledgeBaseById,
      }),
    formatRoleCodeLabel: options.formatRoleCodeLabel,
    formatRoleLabel: options.formatRoleLabel,
    formatRoleList: options.formatRoleList,
    formatRoleScopeType: options.formatRoleScopeType,
    initialAssignableRoles: options.initialAssignableRoles.value,
    knowledgeBaseKeyword: options.optionSearchForm.knowledgeBaseKeyword,
    onRoleBindingRoleChange: options.onRoleBindingRoleChange,
    openCreateUserModal: options.openCreateUserModal,
    openDeleteUserModal: options.openDeleteUserModal,
    openEditUserModal: options.openEditUserModal,
    openPasswordResetModal: options.openPasswordResetModal,
    openUserDepartmentsModal: options.openUserDepartmentsModal,
    openUserRolesModal: options.openUserRolesModal,
    pageSizeOptions: options.pageSizeOptions,
    pagination: options.userPagination,
    passwordResetForm: options.passwordResetForm,
    refreshAssignableRoleOptionsFromSearch: options.refreshAssignableRoleOptionsFromSearch,
    refreshDepartmentOptionsFromSearch: options.refreshDepartmentOptionsFromSearch,
    refreshKnowledgeBaseOptionsFromSearch: options.refreshKnowledgeBaseOptionsFromSearch,
    refreshUserRoleAdminState: options.refreshUserRoleAdminState,
    revokeSelectedUserRoleBinding: options.revokeSelectedUserRoleBinding,
    roleBindingDisabledReason: options.roleBindingDisabledReason.value,
    roleBindingForm: options.roleBindingForm,
    roleKeyword: options.optionSearchForm.roleKeyword,
    saveSelectedUserDepartments: options.saveSelectedUserDepartments,
    searchForm: options.userSearchForm,
    searchUsers: () =>
      options.refreshFirstPage(options.userPagination, options.refreshUserRoleAdminState),
    selectedAdminUser: options.selectedAdminUser.value,
    selectedAdminUserIsSystemAdmin: options.selectedAdminUserIsSystemAdmin.value,
    selectedRoleBindingScopeType: options.selectedRoleBindingScopeType.value,
    selectedUserDepartmentIds: options.selectedUserDepartmentIds.value,
    selectedUserDepartmentPagination: options.selectedUserDepartmentPagination,
    selectedUserDepartmentsForDisplay: options.selectedUserDepartmentsForDisplay.value,
    selectedUserPrimaryDepartmentWillChange:
      options.selectedUserPrimaryDepartmentWillChange.value,
    selectedUserRoleBindingPagination: options.selectedUserRoleBindingPagination,
    selectedUserRoleBindings: options.selectedUserRoleBindings.value,
    showHighRiskConfirm: options.selectedCreateRoles.value.some(options.isHighRiskAdminRole),
    submitCreateAdminUser: options.submitCreateAdminUser,
    submitPasswordReset: options.submitPasswordReset,
    submitPatchSelectedAdminUser: options.submitPatchSelectedAdminUser,
    toggleCreateDepartment: options.toggleCreateDepartment,
    toggleCreateRole: options.toggleCreateRole,
    toggleSelectedUserDepartment: options.toggleSelectedUserDepartment,
    updateConfirmedDelete: (value: boolean) => {
      options.userDangerForm.confirmedDelete = value;
    },
    updateConfirmedDisableAdmin: (value: boolean) => {
      options.userEditForm.confirmedDisableAdmin = value;
    },
    updateConfirmedReplacePrimary: (value: boolean) => {
      options.userDepartmentForm.confirmedReplacePrimary = value;
    },
    updateCreateConfirmedHighRisk: (value: boolean) => {
      options.userCreateForm.confirmedHighRisk = value;
    },
    updateCreateName: (value: string) => {
      options.userCreateForm.name = value;
    },
    updateCreatePasswordConfirm: (value: string) => {
      options.userCreateForm.passwordConfirm = value;
    },
    updateCreateUsername: (value: string) => {
      options.userCreateForm.username = value;
    },
    updateDepartmentKeyword: (value: string) => {
      options.optionSearchForm.departmentKeyword = value;
    },
    updateEditName: (value: string) => {
      options.userEditForm.name = value;
    },
    updateEditStatus: (value: "active" | "disabled" | "locked") => {
      options.userEditForm.status = value;
    },
    updateForceChangePassword: (value: boolean) => {
      options.passwordResetForm.forceChangePassword = value;
    },
    updateInitialPassword: (value: string) => {
      options.userCreateForm.initialPassword = value;
    },
    updateKeyword: (value: string) => {
      options.userSearchForm.keyword = value;
    },
    updateKnowledgeBaseKeyword: (value: string) => {
      options.optionSearchForm.knowledgeBaseKeyword = value;
    },
    updatePage: (page: number) =>
      options.changePaginationPage(
        options.userPagination,
        options.refreshUserRoleAdminState,
        page,
      ),
    updatePageSize: (pageSize: number) =>
      options.changePaginationPageSize(
        options.userPagination,
        options.refreshUserRoleAdminState,
        pageSize,
      ),
    updatePasswordResetConfirmed: (value: boolean) => {
      options.passwordResetForm.confirmed = value;
    },
    updateResetPassword: (value: string) => {
      options.passwordResetForm.newPassword = value;
    },
    updateResetPasswordConfirm: (value: string) => {
      options.passwordResetForm.passwordConfirm = value;
    },
    updateRoleConfirmedHighRisk: (value: boolean) => {
      options.roleBindingForm.confirmedHighRisk = value;
    },
    updateRoleConfirmedRemoveAdmin: (value: boolean) => {
      options.roleBindingForm.confirmedRemoveAdmin = value;
    },
    updateRoleKeyword: (value: string) => {
      options.optionSearchForm.roleKeyword = value;
    },
    updateRoleScopeId: (value: string) => {
      options.roleBindingForm.scopeId = value;
    },
    updateStatus: (value: string) => {
      options.userSearchForm.status = value;
    },
    updateUserDepartmentPage: (page: number) =>
      options.changePaginationPage(
        options.selectedUserDepartmentPagination,
        options.refreshSelectedUserDepartmentsPage,
        page,
      ),
    updateUserDepartmentPageSize: (pageSize: number) =>
      options.changePaginationPageSize(
        options.selectedUserDepartmentPagination,
        options.refreshSelectedUserDepartmentsPage,
        pageSize,
      ),
    updateUserRoleBindingPage: (page: number) =>
      options.changePaginationPage(
        options.selectedUserRoleBindingPagination,
        options.refreshSelectedUserRoleBindingsPage,
        page,
      ),
    updateUserRoleBindingPageSize: (pageSize: number) =>
      options.changePaginationPageSize(
        options.selectedUserRoleBindingPagination,
        options.refreshSelectedUserRoleBindingsPage,
        pageSize,
      ),
    userCreateForm: options.userCreateForm,
    userDangerForm: options.userDangerForm,
    userDepartmentForm: options.userDepartmentForm,
    userEditForm: options.userEditForm,
    userModalMode: options.userModalMode.value,
    users: options.adminUsers.value,
  }));
}
