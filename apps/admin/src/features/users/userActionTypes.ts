import type { ComputedRef, Ref } from "vue";

import type { AdminDepartmentData } from "@/api/departments";
import type {
  AdminAssignableRoleOptionData,
  AdminRoleBindingData,
  AdminRoleData,
} from "@/api/roles";
import type { AdminUserData } from "@/api/users";
import type { PaginationState } from "@/utils/pagination";

export type Feedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

export type UserBusyState = {
  creating: boolean;
  updating: boolean;
  updatingDepartments: boolean;
  resettingPassword: boolean;
  updatingRoles: boolean;
};

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

export type UserDepartmentForm = {
  departmentIds: string[];
  confirmedReplacePrimary: boolean;
};

export type RoleBindingForm = {
  roleId: string;
  scopeId: string;
  confirmedHighRisk: boolean;
  confirmedRemoveAdmin: boolean;
};

export type UseUsersOptions = {
  busy: UserBusyState;
  closeUserModal: () => void;
  ensureAccessToken: () => Promise<string | null>;
  feedback: Ref<Feedback | null>;
  isHighRiskAdminRole: (role: AdminRoleData | AdminAssignableRoleOptionData) => boolean;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  passwordResetForm: PasswordResetForm;
  refreshSelectedAdminUserDetail: (existingAccessToken?: string) => Promise<void>;
  refreshUserRoleAdminState: () => Promise<void>;
  resetCreateUserForm: () => void;
  roleBindingForm: RoleBindingForm;
  selectNextAvailableRoleBindingTarget: () => void;
  selectedAdminUser: ComputedRef<AdminUserData | null>;
  selectedAdminUserId: Ref<string>;
  selectedAdminUserIsSystemAdmin: ComputedRef<boolean>;
  selectedCreateRoles: ComputedRef<AdminAssignableRoleOptionData[]>;
  selectedRoleForBinding: ComputedRef<AdminAssignableRoleOptionData | null>;
  selectedUserDepartments: Ref<AdminDepartmentData[]>;
  selectedUserDepartmentPagination: PaginationState;
  selectedUserPrimaryDepartmentWillChange: ComputedRef<boolean>;
  selectedUserRoleBindingPagination: PaginationState;
  selectedUserRoleBindings: Ref<AdminRoleBindingData[]>;
  syncRoleBindingScopeDefault: () => void;
  syncSelectedUserDepartmentForm: () => void;
  syncUserEditForm: () => void;
  updateSelectedAdminUserDepartments: (departments: AdminDepartmentData[]) => void;
  userCreateForm: UserCreateForm;
  userDangerForm: UserDangerForm;
  userDepartmentForm: UserDepartmentForm;
  userEditForm: UserEditForm;
};
