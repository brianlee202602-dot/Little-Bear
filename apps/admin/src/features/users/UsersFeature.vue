<script setup lang="ts">
import { computed, onMounted, reactive } from "vue";

import { useAdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import { useAdminSessionProvider } from "@/app/providers/adminSessionProvider";
import { useDepartmentLookupRuntime } from "@/features/departments/runtime/useDepartmentLookupRuntime";
import { formatDepartmentLabel, formatDepartmentList } from "@/features/departments/departmentDisplay";
import { useKnowledgeBaseLookupRuntime } from "@/features/knowledge/runtime/useKnowledgeBaseLookupRuntime";
import { formatKnowledgeBaseLabel } from "@/features/knowledge/knowledgeDisplay";
import UserManagementPanel from "@/features/users/UserManagementPanel.vue";
import { useUserAdminRuntime } from "@/features/users/useUserAdminRuntime";
import {
  formatRoleBindingScope,
  formatRoleCodeLabel,
  formatRoleLabel,
  formatRoleList,
  formatRoleScopeType,
  isHighRiskAdminRole,
} from "@/features/users/userDisplay";
import { createUserManagementContext } from "@/features/users/userManagementContext";
import { normalizeErrorMessage } from "@/utils/errors";
import {
  changePaginationPage,
  changePaginationPageSize,
  refreshFirstPage,
} from "@/utils/pagination";

const pageSizeOptions = [10, 20, 50, 100, 200];
const selectorPageSize = 20;
const optionSearchForm = reactive({
  departmentKeyword: "",
  roleKeyword: "",
  knowledgeBaseKeyword: "",
});

const capabilities = useAdminCapabilityProvider();
const session = useAdminSessionProvider();
let ensureDefaultCreateDepartmentSelectionFromRuntime = (): void => undefined;
let syncRoleBindingScopeDefaultFromRuntime = (): void => undefined;

const {
  adminDepartmentOptions,
  clearDepartmentOptions,
  refreshDepartmentOptions,
  refreshDepartmentOptionsFromSearch,
} = useDepartmentLookupRuntime({
  canReadDepartments: capabilities.canReadDepartments,
  ensureAccessToken: session.ensureAccessToken,
  getOptionKeyword: () => optionSearchForm.departmentKeyword,
  getPinnedDepartments: () => [
    ...(session.currentUser.value?.departments ?? []),
    ...(runtime.selectedAdminUser.value?.departments ?? []),
    ...runtime.selectedUserDepartments.value,
  ],
  onDepartmentOptionsChanged: () => {
    ensureDefaultCreateDepartmentSelectionFromRuntime();
    syncRoleBindingScopeDefaultFromRuntime();
  },
  selectorPageSize,
});
const activeDepartments = computed(() =>
  adminDepartmentOptions.value.filter((department) => department.status === "active"),
);

const {
  activeKnowledgeBases,
  clearKnowledgeBaseOptions,
  refreshKnowledgeBaseOptions,
  refreshKnowledgeBaseOptionsFromSearch,
} = useKnowledgeBaseLookupRuntime({
  canManageKnowledgeBases: capabilities.canManageKnowledgeBases,
  ensureAccessToken: session.ensureAccessToken,
  getOptionKeyword: () => optionSearchForm.knowledgeBaseKeyword,
  onKnowledgeBaseOptionsChanged: () => syncRoleBindingScopeDefaultFromRuntime(),
  selectorPageSize,
});

const runtime = useUserAdminRuntime({
  activeDepartments,
  activeKnowledgeBases,
  canLoadUserAdmin: capabilities.canLoadUserAdmin,
  canManageDepartments: capabilities.canManageDepartments,
  canManageKnowledgeBases: capabilities.canManageKnowledgeBases,
  canManageRoles: capabilities.canManageRoles,
  canManageUsers: capabilities.canManageUsers,
  canReadDepartments: capabilities.canReadDepartments,
  canReadRoles: capabilities.canReadRoles,
  canReadUsers: capabilities.canReadUsers,
  clearDepartmentOptions,
  clearKnowledgeBaseOptions,
  currentUser: session.currentUser,
  ensureAccessToken: session.ensureAccessToken,
  isHighRiskAdminRole,
  normalizeErrorMessage,
  refreshDepartmentOptions,
  refreshKnowledgeBaseOptions,
  roleKeyword: () => optionSearchForm.roleKeyword,
  selectorPageSize,
});
ensureDefaultCreateDepartmentSelectionFromRuntime =
  runtime.ensureDefaultCreateDepartmentSelection;
syncRoleBindingScopeDefaultFromRuntime = runtime.syncRoleBindingScopeDefault;

const userManagementModel = createUserManagementContext({
  activeDepartments,
  activeKnowledgeBases,
  addSelectedUserRoleBinding: runtime.addSelectedUserRoleBinding,
  adminUsers: runtime.adminUsers,
  assignableRoles: runtime.assignableRoles,
  canAddSelectedUserRole: runtime.canAddSelectedUserRole,
  canCreateAdminUser: runtime.canCreateAdminUser,
  canDeleteSelectedAdminUser: runtime.canDeleteSelectedAdminUser,
  canLoadUserAdmin: capabilities.canLoadUserAdmin,
  canManageDepartments: capabilities.canManageDepartments,
  canManageKnowledgeBases: capabilities.canManageKnowledgeBases,
  canManageRoles: capabilities.canManageRoles,
  canManageUsers: capabilities.canManageUsers,
  canReadDepartments: capabilities.canReadDepartments,
  canReadRoles: capabilities.canReadRoles,
  canReadUsers: capabilities.canReadUsers,
  canResetSelectedUserPassword: runtime.canResetSelectedUserPassword,
  canSaveSelectedUserDepartments: runtime.canSaveSelectedUserDepartments,
  canUpdateSelectedAdminUser: runtime.canUpdateSelectedAdminUser,
  changePaginationPage,
  changePaginationPageSize,
  closeUserModal: runtime.closeUserModal,
  createUserDepartmentOptions: runtime.createUserDepartmentOptions,
  deleteSelectedAdminUser: runtime.deleteSelectedAdminUser,
  formatDepartmentLabel,
  formatDepartmentList,
  formatKnowledgeBaseLabel,
  formatRoleBindingScope,
  formatRoleCodeLabel,
  formatRoleLabel,
  formatRoleList,
  formatRoleScopeType,
  initialAssignableRoles: runtime.initialAssignableRoles,
  isHighRiskAdminRole,
  onRoleBindingRoleChange: runtime.onRoleBindingRoleChange,
  openCreateUserModal: runtime.openCreateUserModal,
  openDeleteUserModal: runtime.openDeleteUserModal,
  openEditUserModal: runtime.openEditUserModal,
  openPasswordResetModal: runtime.openPasswordResetModal,
  openUserDepartmentsModal: runtime.openUserDepartmentsModal,
  openUserRolesModal: runtime.openUserRolesModal,
  optionSearchForm,
  pageSizeOptions,
  passwordResetForm: runtime.passwordResetForm,
  refreshAssignableRoleOptionsFromSearch: runtime.refreshAssignableRoleOptionsFromSearch,
  refreshDepartmentOptionsFromSearch,
  refreshFirstPage,
  refreshKnowledgeBaseOptionsFromSearch,
  refreshSelectedUserDepartmentsPage: runtime.refreshSelectedUserDepartmentsPage,
  refreshSelectedUserRoleBindingsPage: runtime.refreshSelectedUserRoleBindingsPage,
  refreshUserRoleAdminState: runtime.refreshUserRoleAdminState,
  revokeSelectedUserRoleBinding: runtime.revokeSelectedUserRoleBinding,
  roleBindingDisabledReason: runtime.roleBindingDisabledReason,
  roleBindingForm: runtime.roleBindingForm,
  saveSelectedUserDepartments: runtime.saveSelectedUserDepartments,
  selectedAdminUser: runtime.selectedAdminUser,
  selectedAdminUserIsSystemAdmin: runtime.selectedAdminUserIsSystemAdmin,
  selectedCreateRoles: runtime.selectedCreateRoles,
  selectedRoleBindingScopeType: runtime.selectedRoleBindingScopeType,
  selectedUserDepartmentIds: runtime.selectedUserDepartmentIds,
  selectedUserDepartmentPagination: runtime.selectedUserDepartmentPagination,
  selectedUserDepartmentsForDisplay: runtime.selectedUserDepartmentsForDisplay,
  selectedUserPrimaryDepartmentWillChange: runtime.selectedUserPrimaryDepartmentWillChange,
  selectedUserRoleBindingPagination: runtime.selectedUserRoleBindingPagination,
  selectedUserRoleBindings: runtime.selectedUserRoleBindings,
  submitCreateAdminUser: runtime.submitCreateAdminUser,
  submitPasswordReset: runtime.submitPasswordReset,
  submitPatchSelectedAdminUser: runtime.submitPatchSelectedAdminUser,
  toggleCreateDepartment: runtime.toggleCreateDepartment,
  toggleCreateRole: runtime.toggleCreateRole,
  toggleSelectedUserDepartment: runtime.toggleSelectedUserDepartment,
  userAdminBusy: runtime.userAdminBusy,
  userAdminFeedback: runtime.userAdminFeedback,
  userCreateForm: runtime.userCreateForm,
  userDangerForm: runtime.userDangerForm,
  userDepartmentForm: runtime.userDepartmentForm,
  userEditForm: runtime.userEditForm,
  userModalMode: runtime.userModalMode,
  userPagination: runtime.userPagination,
  userSearchForm: runtime.userSearchForm,
});

onMounted(async () => {
  await runtime.refreshUserRoleAdminState();
});
</script>

<template>
  <UserManagementPanel :model="userManagementModel" />
</template>
