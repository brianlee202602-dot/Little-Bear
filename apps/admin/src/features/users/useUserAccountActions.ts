import {
  createAdminUser,
  deleteAdminUser,
  patchAdminUser,
  resetAdminUserPassword,
  unlockAdminUser,
} from "@/api/users";
import type { UseUsersOptions } from "@/features/users/userActionTypes";

export function useUserAccountActions(options: UseUsersOptions) {
  async function submitCreateAdminUser(): Promise<void> {
    if (options.userCreateForm.initialPassword !== options.userCreateForm.passwordConfirm) {
      options.feedback.value = {
        tone: "error",
        message: "两次输入的初始密码不一致。",
      };
      return;
    }
    if (options.userCreateForm.departmentIds.length === 0) {
      options.feedback.value = {
        tone: "error",
        message: "请至少选择一个归属部门。",
      };
      return;
    }
    const highRisk = options.selectedCreateRoles.value.some(options.isHighRiskAdminRole);
    if (highRisk && !options.userCreateForm.confirmedHighRisk) {
      options.feedback.value = {
        tone: "error",
        message: "授予高风险角色前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.creating = true;
    try {
      const response = await createAdminUser(
        {
          username: options.userCreateForm.username.trim(),
          name: options.userCreateForm.name.trim(),
          initial_password: options.userCreateForm.initialPassword,
          department_ids: options.userCreateForm.departmentIds,
          role_ids: options.userCreateForm.roleIds,
        },
        accessToken,
        options.userCreateForm.confirmedHighRisk,
      );
      options.selectedAdminUserId.value = response.data.id;
      options.resetCreateUserForm();
      await options.refreshUserRoleAdminState();
      options.feedback.value = {
        tone: "success",
        message: "用户已创建。",
      };
      options.closeUserModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "创建用户失败"),
      };
    } finally {
      options.busy.creating = false;
    }
  }

  async function submitPatchSelectedAdminUser(): Promise<void> {
    const user = options.selectedAdminUser.value;
    if (!user) {
      return;
    }
    if (!options.userEditForm.name.trim()) {
      options.feedback.value = {
        tone: "error",
        message: "显示名不能为空。",
      };
      return;
    }
    if (
      options.userEditForm.status === "disabled" &&
      options.selectedAdminUserIsSystemAdmin.value &&
      !options.userEditForm.confirmedDisableAdmin
    ) {
      options.feedback.value = {
        tone: "error",
        message: "禁用系统管理员前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.updating = true;
    try {
      const shouldUnlock = user.status === "locked" && options.userEditForm.status === "active";
      if (shouldUnlock) {
        await unlockAdminUser(user.id, accessToken);
      }
      await patchAdminUser(
        user.id,
        {
          name: options.userEditForm.name.trim(),
          status: shouldUnlock ? undefined : options.userEditForm.status,
        },
        accessToken,
        options.userEditForm.confirmedDisableAdmin,
      );
      await options.refreshUserRoleAdminState();
      options.syncUserEditForm();
      options.feedback.value = {
        tone: "success",
        message: "用户信息已更新。",
      };
      options.closeUserModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "更新用户失败"),
      };
    } finally {
      options.busy.updating = false;
    }
  }

  async function deleteSelectedAdminUser(): Promise<void> {
    const user = options.selectedAdminUser.value;
    if (!user || !options.userDangerForm.confirmedDelete) {
      options.feedback.value = {
        tone: "error",
        message: "删除用户前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.updating = true;
    try {
      await deleteAdminUser(user.id, accessToken, true);
      options.selectedAdminUserId.value = "";
      options.selectedUserRoleBindings.value = [];
      await options.refreshUserRoleAdminState();
      options.feedback.value = {
        tone: "success",
        message: "用户已删除。",
      };
      options.closeUserModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "删除用户失败"),
      };
    } finally {
      options.busy.updating = false;
    }
  }

  async function submitPasswordReset(): Promise<void> {
    const user = options.selectedAdminUser.value;
    if (!user) {
      return;
    }
    if (options.passwordResetForm.newPassword !== options.passwordResetForm.passwordConfirm) {
      options.feedback.value = {
        tone: "error",
        message: "两次输入的新密码不一致。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.resettingPassword = true;
    try {
      await resetAdminUserPassword(
        user.id,
        {
          new_password: options.passwordResetForm.newPassword,
          force_change_password: options.passwordResetForm.forceChangePassword,
        },
        accessToken,
        options.passwordResetForm.confirmed,
      );
      options.passwordResetForm.newPassword = "";
      options.passwordResetForm.passwordConfirm = "";
      options.passwordResetForm.confirmed = false;
      options.feedback.value = {
        tone: "success",
        message: "密码已重置，相关会话已由后端吊销。",
      };
      options.closeUserModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "重置密码失败"),
      };
    } finally {
      options.busy.resettingPassword = false;
    }
  }

  return {
    deleteSelectedAdminUser,
    submitCreateAdminUser,
    submitPasswordReset,
    submitPatchSelectedAdminUser,
  };
}
