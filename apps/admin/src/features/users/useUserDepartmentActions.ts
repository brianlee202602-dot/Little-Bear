import { replaceAdminUserDepartments } from "@/api/users";
import type { UseUsersOptions } from "@/features/users/userActionTypes";
import { syncPaginationState } from "@/utils/pagination";

export function useUserDepartmentActions(options: UseUsersOptions) {
  async function saveSelectedUserDepartments(): Promise<void> {
    const user = options.selectedAdminUser.value;
    if (!user) {
      return;
    }
    if (options.userDepartmentForm.departmentIds.length === 0) {
      options.feedback.value = {
        tone: "error",
        message: "请至少选择一个用户归属部门。",
      };
      return;
    }
    if (
      options.selectedUserPrimaryDepartmentWillChange.value &&
      !options.userDepartmentForm.confirmedReplacePrimary
    ) {
      options.feedback.value = {
        tone: "error",
        message: "更换主部门前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.busy.updatingDepartments = true;
    try {
      const response = await replaceAdminUserDepartments(
        user.id,
        { department_ids: options.userDepartmentForm.departmentIds },
        accessToken,
        options.userDepartmentForm.confirmedReplacePrimary,
      );
      options.selectedUserDepartments.value = response.data;
      syncPaginationState(options.selectedUserDepartmentPagination, response.pagination);
      options.updateSelectedAdminUserDepartments(response.data);
      await options.refreshSelectedAdminUserDetail(accessToken);
      options.syncSelectedUserDepartmentForm();
      options.feedback.value = {
        tone: "success",
        message: "用户部门归属已更新。",
      };
      options.closeUserModal();
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "更新用户部门归属失败"),
      };
    } finally {
      options.busy.updatingDepartments = false;
    }
  }

  return {
    saveSelectedUserDepartments,
  };
}
