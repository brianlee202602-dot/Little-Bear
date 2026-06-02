import { reactive, ref, type ComputedRef, type Ref } from "vue";

import type { AdminDepartmentData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminKnowledgeBaseOptionData } from "@/api/knowledgeBases";
import {
  type AdminAssignableRoleOptionData,
  type AdminRoleBindingData,
} from "@/api/roles";
import type { AdminUserData, AdminUserListItemData } from "@/api/users";
import type {
  Feedback,
  RoleBindingForm,
  UserCreateForm,
} from "@/features/users/userActionTypes";
import { useUserRoleBindingRefresh } from "@/features/users/useUserRoleBindingRefresh";
import {
  useUserRoleBindingSelection,
  type RoleScopeType,
} from "@/features/users/useUserRoleBindingSelection";
import type { UserModalMode } from "@/features/users/useUserModals";
import { clearPaginationState, type PaginationState } from "@/utils/pagination";

export type { RoleBindingForm, RoleScopeType };

export function useUserRoleBindings(options: {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  activeKnowledgeBases: ComputedRef<AdminKnowledgeBaseOptionData[]>;
  busy: { loading: boolean; updatingRoles: boolean };
  canManageRoles: ComputedRef<boolean>;
  canReadRoles: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  feedback: Ref<Feedback | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  roleKeyword: () => string;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedAdminUserId: Ref<string>;
  selectedUserDepartmentsForForm: ComputedRef<AdminDepartmentData[]>;
  selectorPageSize: number;
  userCreateForm: UserCreateForm;
  userModalMode: Ref<UserModalMode>;
}) {
  const adminRoles = ref<AdminAssignableRoleOptionData[]>([]);
  const selectedUserRoleBindings = ref<AdminRoleBindingData[]>([]);
  const selectedUserRoleBindingPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 10,
    total: 0,
  });
  const roleBindingForm = reactive<RoleBindingForm>({
    roleId: "",
    scopeId: "",
    confirmedHighRisk: false,
    confirmedRemoveAdmin: false,
  });
  const selection = useUserRoleBindingSelection({
    activeDepartments: options.activeDepartments,
    activeKnowledgeBases: options.activeKnowledgeBases,
    adminRoles,
    busy: options.busy,
    canManageRoles: options.canManageRoles,
    roleBindingForm,
    selectedAdminUser: options.selectedAdminUser,
    selectedUserDepartmentsForForm: options.selectedUserDepartmentsForForm,
    selectedUserRoleBindings,
    userCreateForm: options.userCreateForm,
  });

  const {
    refreshAssignableRoleOptions,
    refreshAssignableRoleOptionsFromSearch,
    refreshSelectedUserRoleBindings,
    refreshSelectedUserRoleBindingsPage,
  } = useUserRoleBindingRefresh({
    adminRoles,
    assignableRoles: selection.assignableRoles,
    canReadRoles: options.canReadRoles,
    ensureAccessToken: options.ensureAccessToken,
    feedback: options.feedback,
    normalizeErrorMessage: options.normalizeErrorMessage,
    roleBindingForm,
    roleKeyword: options.roleKeyword,
    selectedAdminUser: options.selectedAdminUser,
    selectedAdminUserId: options.selectedAdminUserId,
    selectedUserRoleBindingPagination,
    selectedUserRoleBindings,
    selectorPageSize: options.selectorPageSize,
    syncRoleBindingScopeDefault: selection.syncRoleBindingScopeDefault,
  });

  async function openUserRolesModal(
    user: AdminUserListItemData,
    selectAdminUser: (userId: string) => Promise<void>,
  ): Promise<void> {
    await selectAdminUser(user.id);
    options.userModalMode.value = "roles";
    if (!roleBindingForm.roleId && selection.assignableRoles.value.length > 0) {
      roleBindingForm.roleId = selection.assignableRoles.value[0].id;
    }
    if (
      !roleBindingForm.roleId ||
      selection.selectedUserRoleBindingKeys.value.has(selection.selectedRoleBindingKey.value)
    ) {
      selection.selectNextAvailableRoleBindingTarget();
    } else {
      selection.syncRoleBindingScopeDefault();
    }
  }

  function resetRoleBindingForm(): void {
    roleBindingForm.scopeId = "";
    roleBindingForm.confirmedHighRisk = false;
    roleBindingForm.confirmedRemoveAdmin = false;
  }

  function clearUserRoleBindingState(): void {
    adminRoles.value = [];
    selectedUserRoleBindings.value = [];
    clearPaginationState(selectedUserRoleBindingPagination);
    roleBindingForm.roleId = "";
    resetRoleBindingForm();
  }

  return {
    adminRoles,
    assignableRoles: selection.assignableRoles,
    availableRoleBindingCandidates: selection.availableRoleBindingCandidates,
    canAddSelectedUserRole: selection.canAddSelectedUserRole,
    clearUserRoleBindingState,
    initialAssignableRoles: selection.initialAssignableRoles,
    onRoleBindingRoleChange: selection.onRoleBindingRoleChange,
    openUserRolesModal,
    refreshAssignableRoleOptions,
    refreshAssignableRoleOptionsFromSearch,
    refreshSelectedUserRoleBindings,
    refreshSelectedUserRoleBindingsPage,
    resetRoleBindingForm,
    roleBindingDisabledReason: selection.roleBindingDisabledReason,
    roleBindingForm,
    selectedCreateRoles: selection.selectedCreateRoles,
    selectedRoleBindingKey: selection.selectedRoleBindingKey,
    selectedRoleBindingScopeType: selection.selectedRoleBindingScopeType,
    selectedRoleForBinding: selection.selectedRoleForBinding,
    selectedUserRoleBindingKeys: selection.selectedUserRoleBindingKeys,
    selectedUserRoleBindingPagination,
    selectedUserRoleBindings,
    selectNextAvailableRoleBindingTarget: selection.selectNextAvailableRoleBindingTarget,
    syncRoleBindingScopeDefault: selection.syncRoleBindingScopeDefault,
  };
}
