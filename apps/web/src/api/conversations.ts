import { requestJson, requestVoid } from "./http";
import type { QueryConversationListResponse, QueryConversationResponse } from "./types";

export type { QueryConversationData, QueryConversationListResponse, QueryConversationResponse, QueryMessageData } from "./types";

export async function listQueryConversations(
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<QueryConversationListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  return requestJson<QueryConversationListResponse>(
    `/internal/v1/query-conversations?${params.toString()}`,
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function createQueryConversation(
  payload: { title?: string | null; kb_ids?: string[] },
  accessToken: string,
): Promise<QueryConversationResponse> {
  return requestJson<QueryConversationResponse>(
    "/internal/v1/query-conversations",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function getQueryConversation(
  conversationId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<QueryConversationResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  return requestJson<QueryConversationResponse>(
    `/internal/v1/query-conversations/${encodeURIComponent(conversationId)}?${params.toString()}`,
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function deleteQueryConversation(
  conversationId: string,
  accessToken: string,
): Promise<void> {
  await requestVoid(
    `/internal/v1/query-conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "DELETE",
    },
    accessToken,
  );
}
