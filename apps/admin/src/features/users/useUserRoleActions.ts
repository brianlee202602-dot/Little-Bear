import {
  createAdminUserRoleBindings,
  revokeAdminUserRoleBinding,
  type AdminRoleBindingData,
} from "@/api/roles";
import type { UseUsersOptions } from "@/features/users/userActionTypes";
import { syncPaginationState } from "@/utils/pagination";

export function useUserRoleActions(options: UseUsersOptions) {
  async function addSelectedUserRoleBinding(): Promise<void> {
    const user = options.selectedAdminUser.value;
    const role = options.selectedRoleForBinding.value;
    if (!user || !role) {
      return;
    }
    if (options.isHighRiskAdminRole(role) && !options.roleBindingForm.confirmedHighRisk) {
      options.feedback.value = {
        tone: "error",
        message: "授予高风险角色前必须勾选确认项。",
      };
      return;
    }
    if (role.scope_type !== "enterprise" && !options.roleBindingForm.scopeId) {
      options.feedback.value = {
        tone: "error",
        message: role.scope_type === "department" ? "请选择部门作用域。" : "请选择知识库作用域。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.updatingRoles = true;
    try {
      const response = await createAdminUserRoleBindings(
        user.id,
        [
          {
            role_id: role.id,
            scope_type: role.scope_type,
            scope_id: role.scope_type === "enterprise" ? null : options.roleBindingForm.scopeId,
          },
        ],
        accessToken,
        options.roleBindingForm.confirmedHighRisk,
      );
      options.selectedUserRoleBindings.value = response.data;
      syncPaginationState(options.selectedUserRoleBindingPagination, response.pagination);
      options.roleBindingForm.confirmedHighRisk = false;
      await options.refreshUserRoleAdminState();
      options.selectNextAvailableRoleBindingTarget();
      options.feedback.value = {
        tone: "success",
        message: "角色已授予。",
      };
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "授予角色失败"),
      };
    } finally {
      options.busy.updatingRoles = false;
    }
  }

  async function revokeSelectedUserRoleBinding(binding: AdminRoleBindingData): Promise<void> {
    const user = options.selectedAdminUser.value;
    if (!user) {
      return;
    }
    if (binding.role_code === "system_admin" && !options.roleBindingForm.confirmedRemoveAdmin) {
      options.feedback.value = {
        tone: "error",
        message: "移除系统管理员角色前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.updatingRoles = true;
    try {
      await revokeAdminUserRoleBinding(
        user.id,
        binding.id,
        accessToken,
        options.roleBindingForm.confirmedRemoveAdmin,
      );
      await options.refreshUserRoleAdminState();
      options.roleBindingForm.roleId = binding.role_id;
      options.roleBindingForm.scopeId = binding.scope_id ?? "";
      options.roleBindingForm.confirmedHighRisk = false;
      options.roleBindingForm.confirmedRemoveAdmin = false;
      options.syncRoleBindingScopeDefault();
      options.feedback.value = {
        tone: "success",
        message: "角色绑定已撤销。",
      };
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "撤销角色绑定失败"),
      };
    } finally {
      options.busy.updatingRoles = false;
    }
  }

  return {
    addSelectedUserRoleBinding,
    revokeSelectedUserRoleBinding,
  };
}
