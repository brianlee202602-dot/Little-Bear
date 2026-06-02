import { requestJson } from "./http";
import type { AcceptedResponse } from "./commonTypes";
import type {
  AdminFolderCreateRequest,
  AdminFolderListResponse,
  AdminFolderOptionListResponse,
  AdminFolderPatchRequest,
  AdminFolderResponse,
} from "./folderTypes";

export type { AcceptedResponse } from "./commonTypes";
export type {
  AdminFolderCreateRequest,
  AdminFolderData,
  AdminFolderListResponse,
  AdminFolderOptionData,
  AdminFolderOptionListResponse,
  AdminFolderPatchRequest,
  AdminFolderResponse,
} from "./folderTypes";

export async function listAdminFolders(
  kbId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<AdminFolderListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 100),
  });
  return requestJson<AdminFolderListResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/folders?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminFolderOptions(
  kbId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
): Promise<AdminFolderOptionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  for (const [key, value] of Object.entries(filters)) {
    if (key === "page" || key === "page_size" || value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  return requestJson<AdminFolderOptionListResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/folder-options?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminFolder(
  kbId: string,
  payload: AdminFolderCreateRequest,
  accessToken: string,
): Promise<AdminFolderResponse> {
  return requestJson<AdminFolderResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/folders`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function patchAdminFolder(
  folderId: string,
  payload: AdminFolderPatchRequest,
  accessToken: string,
): Promise<AdminFolderResponse> {
  return requestJson<AdminFolderResponse>(
    `/internal/v1/admin/folders/${encodeURIComponent(folderId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function deleteAdminFolder(
  folderId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/folders/${encodeURIComponent(folderId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-folder-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}
