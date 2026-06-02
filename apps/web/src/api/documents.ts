import { requestJson } from "./http";
import type { ChunkListResponse, CitationSourceResponse, DocumentListResponse, DocumentVersionListResponse } from "./types";

export type { ChunkData, ChunkListResponse, CitationSourceData, CitationSourceResponse, DocumentListItemData, DocumentListResponse, DocumentVersionData, DocumentVersionListResponse } from "./types";

export async function listDocuments(
  kbId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
): Promise<DocumentListResponse> {
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
  return requestJson<DocumentListResponse>(
    `/internal/v1/knowledge-bases/${encodeURIComponent(kbId)}/documents?${params.toString()}`,
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function listDocumentVersions(
  documentId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<DocumentVersionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  return requestJson<DocumentVersionListResponse>(
    `/internal/v1/documents/${encodeURIComponent(documentId)}/versions?${params.toString()}`,
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function listDocumentChunks(
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
    `/internal/v1/documents/${encodeURIComponent(documentId)}/chunks?${params.toString()}`,
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function getCitationSource(
  documentId: string,
  sourceId: string,
  accessToken: string,
): Promise<CitationSourceResponse> {
  return requestJson<CitationSourceResponse>(
    `/internal/v1/documents/${encodeURIComponent(documentId)}/sources/${encodeURIComponent(sourceId)}`,
    {
      method: "GET",
    },
    accessToken,
  );
}
