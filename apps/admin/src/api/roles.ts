import { requestJson, requestVoid } from "./http";
import type {
  AdminAssignableRoleOptionListResponse,
  AdminRoleBindingInputData,
  AdminRoleBindingListResponse,
  AdminRoleListResponse,
} from "./roleTypes";

export type {
  AdminAssignableRoleOptionData,
  AdminAssignableRoleOptionListResponse,
  AdminRoleBindingData,
  AdminRoleBindingInputData,
  AdminRoleBindingListResponse,
  AdminRoleData,
  AdminRoleListItemData,
  AdminRoleListResponse,
} from "./roleTypes";

export async function listAdminRoles(
  accessToken: string,
  filters: {
    keyword?: string;
    status?: string;
    scope_type?: string;
    page?: number;
    page_size?: number;
  } = {},
): Promise<AdminRoleListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 100),
  });
  if (filters.keyword) {
    params.set("keyword", filters.keyword);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.scope_type) {
    params.set("scope_type", filters.scope_type);
  }
  return requestJson<AdminRoleListResponse>(
    `/internal/v1/admin/roles?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminAssignableRoleOptions(
  accessToken: string,
  filters: {
    keyword?: string;
    status?: string;
    scope_type?: string;
    page?: number;
    page_size?: number;
  } = {},
): Promise<AdminAssignableRoleOptionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  if (filters.keyword) {
    params.set("keyword", filters.keyword);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.scope_type) {
    params.set("scope_type", filters.scope_type);
  }
  return requestJson<AdminAssignableRoleOptionListResponse>(
    `/internal/v1/admin/assignable-role-options?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminUserRoleBindings(
  userId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<AdminRoleBindingListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<AdminRoleBindingListResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/role-bindings?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminUserRoleBindings(
  userId: string,
  bindings: AdminRoleBindingInputData[],
  accessToken: string,
  confirmedHighRisk: boolean,
): Promise<AdminRoleBindingListResponse> {
  return requestJson<AdminRoleBindingListResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/role-bindings`,
    {
      method: "POST",
      body: JSON.stringify({ bindings }),
      headers: confirmedHighRisk ? { "x-role-binding-confirm": "high-risk" } : undefined,
    },
    accessToken,
  );
}

export async function revokeAdminUserRoleBinding(
  userId: string,
  bindingId: string,
  accessToken: string,
  confirmedRemoveAdmin: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/role-bindings/${encodeURIComponent(bindingId)}`,
    {
      method: "DELETE",
      headers: confirmedRemoveAdmin ? { "x-role-binding-confirm": "remove-admin" } : undefined,
    },
    accessToken,
  );
}
