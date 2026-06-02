import { requestJson } from "./http";
import type { KnowledgeBaseListResponse } from "./types";

export type { KnowledgeBaseData, KnowledgeBaseListResponse } from "./types";

export async function listKnowledgeBases(
  accessToken: string,
  filters: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
): Promise<KnowledgeBaseListResponse> {
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
  return requestJson<KnowledgeBaseListResponse>(
    `/internal/v1/knowledge-bases?${params.toString()}`,
    {
      method: "GET",
    },
    accessToken,
  );
}
