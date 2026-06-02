import type { ComputedRef, Ref } from "vue";

import {
  listAdminAssignableRoleOptions,
  listAdminUserRoleBindings,
  type AdminAssignableRoleOptionData,
  type AdminRoleBindingData,
} from "@/api/roles";
import type { AdminUserData } from "@/api/users";
import type { RoleBindingForm } from "@/features/users/userActionTypes";
import { isHighRiskAdminRole } from "@/features/users/userDisplay";
import {
  clearPaginationState,
  paginationTotalPages,
  syncPaginationState,
  type PaginationState,
} from "@/utils/pagination";
import { uniqueById } from "@/utils/collections";

type UseUserRoleBindingRefreshOptions = {
  adminRoles: Ref<AdminAssignableRoleOptionData[]>;
  assignableRoles: ComputedRef<AdminAssignableRoleOptionData[]>;
  canReadRoles: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  feedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  roleBindingForm: RoleBindingForm;
  roleKeyword: () => string;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedAdminUserId: Ref<string>;
  selectedUserRoleBindingPagination: PaginationState;
  selectedUserRoleBindings: Ref<AdminRoleBindingData[]>;
  selectorPageSize: number;
  syncRoleBindingScopeDefault: () => void;
};

export function useUserRoleBindingRefresh(options: UseUserRoleBindingRefreshOptions) {
  async function refreshAssignableRoleOptions(existingAccessToken?: string): Promise<void> {
    if (!options.canReadRoles.value) {
      options.adminRoles.value = [];
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await listAdminAssignableRoleOptions(accessToken, {
      keyword: options.roleKeyword().trim() || undefined,
      status: "active",
      page_size: options.selectorPageSize,
    });
    options.adminRoles.value = mergeAssignableRoleOptions(response.data);
    if (!options.roleBindingForm.roleId && options.assignableRoles.value.length > 0) {
      options.roleBindingForm.roleId = options.assignableRoles.value[0].id;
    }
    options.syncRoleBindingScopeDefault();
  }

  function refreshAssignableRoleOptionsFromSearch(): void {
    void refreshAssignableRoleOptions();
  }

  function mergeAssignableRoleOptions(
    incomingOptions: AdminAssignableRoleOptionData[],
  ): AdminAssignableRoleOptionData[] {
    const pinned =
      options.selectedAdminUser.value?.roles.map((role) => ({
        id: role.id,
        code: role.code,
        name: role.name,
        scope_type: role.scope_type,
        status: role.status,
        risk_level: isHighRiskAdminRole(role) ? ("high" as const) : ("low" as const),
      })) ?? [];
    return uniqueById([...incomingOptions, ...pinned]);
  }

  async function refreshSelectedUserRoleBindings(existingAccessToken?: string): Promise<void> {
    if (!options.selectedAdminUserId.value || !options.canReadRoles.value) {
      options.selectedUserRoleBindings.value = [];
      clearPaginationState(options.selectedUserRoleBindingPagination);
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }
    try {
      const response = await listAdminUserRoleBindings(
        options.selectedAdminUserId.value,
        accessToken,
        {
          page: options.selectedUserRoleBindingPagination.page,
          page_size: options.selectedUserRoleBindingPagination.pageSize,
        },
      );
      options.selectedUserRoleBindings.value = response.data;
      syncPaginationState(options.selectedUserRoleBindingPagination, response.pagination);
      if (
        options.selectedUserRoleBindings.value.length === 0 &&
        options.selectedUserRoleBindingPagination.total > 0 &&
        options.selectedUserRoleBindingPagination.page > 1
      ) {
        options.selectedUserRoleBindingPagination.page = paginationTotalPages(
          options.selectedUserRoleBindingPagination,
        );
        await refreshSelectedUserRoleBindings(accessToken);
        return;
      }
      options.syncRoleBindingScopeDefault();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取用户角色绑定失败"),
      };
      throw error;
    }
  }

  async function refreshSelectedUserRoleBindingsPage(): Promise<void> {
    await refreshSelectedUserRoleBindings();
  }

  return {
    refreshAssignableRoleOptions,
    refreshAssignableRoleOptionsFromSearch,
    refreshSelectedUserRoleBindings,
    refreshSelectedUserRoleBindingsPage,
  };
}
