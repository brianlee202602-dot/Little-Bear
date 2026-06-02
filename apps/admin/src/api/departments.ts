import { requestJson, requestVoid } from "./http";
import type {
  AdminDepartmentCreateRequest,
  AdminDepartmentListResponse,
  AdminDepartmentOptionListResponse,
  AdminDepartmentPatchRequest,
  AdminDepartmentResponse,
} from "./departmentsTypes";

export type {
  AdminDepartmentCreateRequest,
  AdminDepartmentData,
  AdminDepartmentListItemData,
  AdminDepartmentListResponse,
  AdminDepartmentOptionData,
  AdminDepartmentOptionListResponse,
  AdminDepartmentPatchRequest,
  AdminDepartmentResponse,
} from "./departmentsTypes";

export async function listAdminDepartments(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminDepartmentListResponse> {
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
  return requestJson<AdminDepartmentListResponse>(
    `/internal/v1/admin/departments?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminDepartmentOptions(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminDepartmentOptionListResponse> {
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
  return requestJson<AdminDepartmentOptionListResponse>(
    `/internal/v1/admin/department-options?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminDepartment(
  payload: AdminDepartmentCreateRequest,
  accessToken: string,
): Promise<AdminDepartmentResponse> {
  return requestJson<AdminDepartmentResponse>(
    "/internal/v1/admin/departments",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function getAdminDepartment(
  departmentId: string,
  accessToken: string,
): Promise<AdminDepartmentResponse> {
  return requestJson<AdminDepartmentResponse>(
    `/internal/v1/admin/departments/${encodeURIComponent(departmentId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function patchAdminDepartment(
  departmentId: string,
  payload: AdminDepartmentPatchRequest,
  accessToken: string,
): Promise<AdminDepartmentResponse> {
  return requestJson<AdminDepartmentResponse>(
    `/internal/v1/admin/departments/${encodeURIComponent(departmentId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function deleteAdminDepartment(
  departmentId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/departments/${encodeURIComponent(departmentId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-department-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}
