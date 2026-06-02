import { requestJson } from "./http";
import type { AcceptedResponse } from "./commonTypes";
import type {
  AdminKnowledgeBaseCreateRequest,
  AdminKnowledgeBaseListResponse,
  AdminKnowledgeBaseOptionListResponse,
  AdminKnowledgeBasePatchRequest,
  AdminKnowledgeBaseResponse,
  KnowledgeBasePermissionPolicyResponse,
  KnowledgeBasePermissionPutRequest,
} from "./knowledgeBaseTypes";

export type { AcceptedResponse } from "./commonTypes";
export type {
  AdminKnowledgeBaseCreateRequest,
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseListResponse,
  AdminKnowledgeBaseOptionData,
  AdminKnowledgeBaseOptionListResponse,
  AdminKnowledgeBasePatchRequest,
  AdminKnowledgeBaseResponse,
  KnowledgeBaseAccessRuleData,
  KnowledgeBasePermissionPolicyResponse,
  KnowledgeBasePermissionPutRequest,
} from "./knowledgeBaseTypes";

export async function listAdminKnowledgeBases(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminKnowledgeBaseListResponse> {
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
  return requestJson<AdminKnowledgeBaseListResponse>(
    `/internal/v1/admin/knowledge-bases?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminKnowledgeBaseOptions(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminKnowledgeBaseOptionListResponse> {
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
  return requestJson<AdminKnowledgeBaseOptionListResponse>(
    `/internal/v1/admin/knowledge-base-options?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getAdminKnowledgeBase(
  kbId: string,
  accessToken: string,
): Promise<AdminKnowledgeBaseResponse> {
  return requestJson<AdminKnowledgeBaseResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminKnowledgeBase(
  payload: AdminKnowledgeBaseCreateRequest,
  accessToken: string,
  confirmedEnterpriseVisibility: boolean,
): Promise<AdminKnowledgeBaseResponse> {
  return requestJson<AdminKnowledgeBaseResponse>(
    "/internal/v1/admin/knowledge-bases",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmedEnterpriseVisibility
        ? { "x-knowledge-base-confirm": "enterprise-visible" }
        : undefined,
    },
    accessToken,
  );
}

export async function patchAdminKnowledgeBase(
  kbId: string,
  payload: AdminKnowledgeBasePatchRequest,
  accessToken: string,
  confirmedVisibilityExpand: boolean,
): Promise<AdminKnowledgeBaseResponse> {
  return requestJson<AdminKnowledgeBaseResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: confirmedVisibilityExpand
        ? { "x-knowledge-base-confirm": "visibility-expand" }
        : undefined,
    },
    accessToken,
  );
}

export async function deleteAdminKnowledgeBase(
  kbId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-knowledge-base-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}

export async function putKnowledgeBasePermissions(
  kbId: string,
  payload: KnowledgeBasePermissionPutRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<KnowledgeBasePermissionPolicyResponse> {
  return requestJson<KnowledgeBasePermissionPolicyResponse>(
    `/internal/v1/knowledge-bases/${encodeURIComponent(kbId)}/permissions`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-permission-confirm": "replace" } : undefined,
    },
    accessToken,
  );
}
