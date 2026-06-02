import { requestJson, requestVoid } from "./http";
import type {
  AdminPasswordResetRequest,
  AdminUserCreateRequest,
  AdminUserDepartmentsPutRequest,
  AdminUserDepartmentsResponse,
  AdminUserListResponse,
  AdminUserPatchRequest,
  AdminUserResponse,
} from "./userTypes";

export type { AdminDepartmentData, AdminDepartmentOptionData } from "./departmentsTypes";
export type { AdminRoleData } from "./roleTypes";
export type {
  AdminPasswordResetRequest,
  AdminUserCreateRequest,
  AdminUserData,
  AdminUserDepartmentsPutRequest,
  AdminUserDepartmentsResponse,
  AdminUserListItemData,
  AdminUserListResponse,
  AdminUserPatchRequest,
  AdminUserResponse,
  AdminUserStatus,
} from "./userTypes";

export async function listAdminUsers(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminUserListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  if (filters.keyword) {
    params.set("keyword", filters.keyword);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  return requestJson<AdminUserListResponse>(
    `/internal/v1/admin/users?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminUser(
  payload: AdminUserCreateRequest,
  accessToken: string,
  confirmedHighRisk: boolean,
): Promise<AdminUserResponse> {
  return requestJson<AdminUserResponse>(
    "/internal/v1/admin/users",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmedHighRisk ? { "x-user-confirm": "create-admin" } : undefined,
    },
    accessToken,
  );
}

export async function getAdminUser(
  userId: string,
  accessToken: string,
): Promise<AdminUserResponse> {
  return requestJson<AdminUserResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function patchAdminUser(
  userId: string,
  payload: AdminUserPatchRequest,
  accessToken: string,
  confirmedDisableAdmin: boolean,
): Promise<AdminUserResponse> {
  return requestJson<AdminUserResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: confirmedDisableAdmin ? { "x-user-confirm": "disable-admin" } : undefined,
    },
    accessToken,
  );
}

export async function deleteAdminUser(
  userId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-user-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}

export async function resetAdminUserPassword(
  userId: string,
  payload: AdminPasswordResetRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/password`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-user-confirm": "reset-password" } : undefined,
    },
    accessToken,
  );
}

export async function unlockAdminUser(userId: string, accessToken: string): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/lock`,
    { method: "DELETE" },
    accessToken,
  );
}

export async function listAdminUserDepartments(
  userId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<AdminUserDepartmentsResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<AdminUserDepartmentsResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/departments?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function replaceAdminUserDepartments(
  userId: string,
  payload: AdminUserDepartmentsPutRequest,
  accessToken: string,
  confirmedReplacePrimary: boolean,
): Promise<AdminUserDepartmentsResponse> {
  return requestJson<AdminUserDepartmentsResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/departments`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmedReplacePrimary
        ? { "x-department-confirm": "replace-primary" }
        : undefined,
    },
    accessToken,
  );
}
