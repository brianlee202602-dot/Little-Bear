import type { PaginationData } from "./commonTypes";
import type { AdminDepartmentData } from "./departmentsTypes";
import type { AdminRoleData } from "./roleTypes";

export type AdminUserStatus = "active" | "disabled" | "locked" | "deleted";

export interface AdminUserData {
  id: string;
  username: string;
  name: string;
  status: AdminUserStatus;
  enterprise_id: string;
  email: string | null;
  phone: string | null;
  departments: AdminDepartmentData[];
  roles: AdminRoleData[];
  scopes: string[];
}

export interface AdminUserListItemData {
  id: string;
  username: string;
  name: string;
  status: AdminUserStatus;
  department_names: string[];
  role_names: string[];
}

export interface AdminUserListResponse {
  request_id: string;
  data: AdminUserListItemData[];
  pagination: PaginationData;
}

export interface AdminUserResponse {
  request_id: string;
  data: AdminUserData;
}

export interface AdminUserCreateRequest {
  username: string;
  name: string;
  initial_password: string;
  department_ids: string[];
  role_ids: string[];
}

export interface AdminUserPatchRequest {
  name?: string;
  status?: "active" | "disabled" | "locked";
}

export interface AdminPasswordResetRequest {
  new_password: string;
  force_change_password: boolean;
}

export interface AdminUserDepartmentsResponse {
  request_id: string;
  data: AdminDepartmentData[];
  pagination: PaginationData;
}

export interface AdminUserDepartmentsPutRequest {
  department_ids: string[];
}
