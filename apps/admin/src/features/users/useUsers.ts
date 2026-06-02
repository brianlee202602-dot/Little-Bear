import type { UseUsersOptions } from "@/features/users/userActionTypes";
import { useUserAccountActions } from "@/features/users/useUserAccountActions";
import { useUserDepartmentActions } from "@/features/users/useUserDepartmentActions";
import { useUserRoleActions } from "@/features/users/useUserRoleActions";

export function useUsers(options: UseUsersOptions) {
  return {
    ...useUserAccountActions(options),
    ...useUserDepartmentActions(options),
    ...useUserRoleActions(options),
  };
}

export type {
  Feedback,
  PasswordResetForm,
  RoleBindingForm,
  UseUsersOptions,
  UserBusyState,
  UserCreateForm,
  UserDangerForm,
  UserDepartmentForm,
  UserEditForm,
} from "@/features/users/userActionTypes";
