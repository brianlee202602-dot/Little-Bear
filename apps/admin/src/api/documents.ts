import { requestJson } from "./http";
import type { AcceptedResponse } from "./commonTypes";
import type {
  AdminDocumentListResponse,
  AdminDocumentPreviewResponse,
  AdminDocumentResponse,
  ChunkListResponse,
  DocumentVersionListResponse,
  IndexVersionListResponse,
  PermissionPolicyResponse,
  ResourcePermissionPutRequest,
} from "./documentTypes";

export type { AcceptedResponse } from "./commonTypes";
export type {
  AdminDocumentData,
  AdminDocumentListItemData,
  AdminDocumentListResponse,
  AdminDocumentPreviewChunkData,
  AdminDocumentPreviewData,
  AdminDocumentPreviewResponse,
  AdminDocumentResponse,
  ChunkData,
  ChunkListResponse,
  DocumentVersionData,
  DocumentVersionListResponse,
  IndexVersionData,
  IndexVersionListResponse,
  PermissionPolicyResponse,
  ResourcePermissionPutRequest,
} from "./documentTypes";

export async function listAdminDocuments(
  kbId: string,
  accessToken: string,
  filters: { status?: string; page?: number; page_size?: number } = {},
): Promise<AdminDocumentListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  if (filters.status) {
    params.set("status", filters.status);
  }
  return requestJson<AdminDocumentListResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/documents?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getAdminDocument(
  documentId: string,
  accessToken: string,
): Promise<AdminDocumentResponse> {
  return requestJson<AdminDocumentResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminDocumentVersions(
  documentId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<DocumentVersionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  return requestJson<DocumentVersionListResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}/versions?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminDocumentChunks(
  documentId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
): Promise<ChunkListResponse> {
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
  return requestJson<ChunkListResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}/chunks?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getAdminDocumentPreview(
  documentId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<AdminDocumentPreviewResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<AdminDocumentPreviewResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}/preview?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminDocumentIndexVersions(
  documentId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<IndexVersionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  return requestJson<IndexVersionListResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}/index-versions?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminDocumentIndexJob(
  documentId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}/index-jobs`,
    {
      method: "POST",
      headers: confirmed ? { "x-index-confirm": "rebuild" } : undefined,
    },
    accessToken,
  );
}

export async function putDocumentPermissions(
  documentId: string,
  payload: ResourcePermissionPutRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<PermissionPolicyResponse> {
  return requestJson<PermissionPolicyResponse>(
    `/internal/v1/documents/${encodeURIComponent(documentId)}/permissions`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-permission-confirm": "replace" } : undefined,
    },
    accessToken,
  );
}
