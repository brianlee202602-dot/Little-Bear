const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export interface ApiErrorPayload {
  request_id?: string;
  debug_id?: string;
  error_code?: string;
  message?: string;
  stage?: string;
  retryable?: boolean;
  details?: Record<string, unknown>;
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: ApiErrorPayload | null;

  constructor(status: number, payload: ApiErrorPayload | null, message: string) {
    super(payload?.message ?? message);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
  }
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  expires_in: number;
}

export interface CurrentUserData {
  id: string;
  username: string;
  name: string;
  status: string;
}

export interface CurrentUserResponse {
  request_id: string;
  data: CurrentUserData;
}

export interface PaginationData {
  page: number;
  page_size: number;
  total: number;
}

export interface KnowledgeBaseData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface KnowledgeBaseListResponse {
  request_id: string;
  data: KnowledgeBaseData[];
  pagination: PaginationData;
}

export interface DocumentListResponse {
  request_id: string;
  data: DocumentListItemData[];
  pagination: PaginationData;
}

export interface DocumentListItemData {
  id: string;
  title: string;
  lifecycle_status: string;
  index_status: string;
  updated_at: string | null;
  can_view: boolean;
  can_cite: boolean;
}

export interface DocumentVersionData {
  id: string;
  document_id: string;
  version_no: number;
  status: string;
}

export interface DocumentVersionListResponse {
  request_id: string;
  data: DocumentVersionData[];
  pagination: PaginationData;
}

export interface ChunkData {
  id: string;
  document_id: string;
  document_version_id: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  ordinal: number;
}

export interface ChunkListResponse {
  request_id: string;
  data: ChunkData[];
  pagination: PaginationData;
}

export interface CitationSourceData {
  source_id: string;
  doc_id: string;
  document_version_id: string;
  title: string;
  text: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  ordinal: number;
  heading_path: string | null;
  source_offsets: Record<string, unknown> | null;
  text_status: "object" | "preview_only" | "object_unavailable";
}

export interface CitationSourceResponse {
  request_id: string;
  data: CitationSourceData;
}

export type QueryMode = "answer" | "search";
export type QueryConfidence = "low" | "medium" | "high";

export interface QueryHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface QueryRequest {
  kb_ids: string[];
  query: string;
  conversation_id?: string | null;
  history?: QueryHistoryMessage[];
  mode: QueryMode;
  filters: Record<string, unknown>;
  top_k: number;
  include_sources: boolean;
}

export interface CitationData {
  source_id: string;
  doc_id: string;
  document_version_id: string;
  title: string;
  page_start: number;
  page_end: number;
  score: number;
}

export interface QueryResponse {
  debug_id: string;
  conversation_id: string | null;
  message_id: string | null;
  answer: string;
  citations: CitationData[];
  confidence: QueryConfidence;
  degraded: boolean;
  degrade_reason: string | null;
}

export type QueryStreamMetadata = Pick<
  QueryResponse,
  | "debug_id"
  | "conversation_id"
  | "message_id"
  | "confidence"
  | "degraded"
  | "degrade_reason"
> & {
  streaming?: boolean;
};

export type QueryStreamDone = QueryResponse;

export interface QueryStreamHandlers {
  onMetadata?: (metadata: QueryStreamMetadata) => void;
  onToken?: (delta: string) => void;
  onCitation?: (citation: CitationData) => void;
  onDone?: (result: QueryStreamDone) => void;
}

export interface QueryConversationData {
  id: string;
  title: string;
  status: "active" | "deleted";
  kb_ids: string[];
  last_message_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface QueryMessageData {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  status: "running" | "done" | "error" | "cancelled";
  citations: CitationData[];
  confidence: QueryConfidence | null;
  degraded: boolean;
  degrade_reason: string | null;
  debug_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface QueryConversationListResponse {
  request_id: string;
  data: QueryConversationData[];
  pagination: PaginationData;
}

export interface QueryConversationResponse {
  request_id: string;
  data: QueryConversationData;
  messages: QueryMessageData[];
  messages_pagination: PaginationData;
}

export async function getLiveStatus(): Promise<unknown> {
  const response = await fetch(buildUrl("/health/live"));
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return response.json();
}

export async function createSession(payload: LoginRequest): Promise<TokenResponse> {
  return requestJson<TokenResponse>("/internal/v1/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function refreshSession(refreshToken: string): Promise<TokenResponse> {
  return requestJson<TokenResponse>(
    "/internal/v1/token-refreshes",
    {
      method: "POST",
    },
    refreshToken,
  );
}

export async function deleteCurrentSession(accessToken: string): Promise<void> {
  await requestVoid(
    "/internal/v1/sessions/current",
    {
      method: "DELETE",
    },
    accessToken,
  );
}

export async function getCurrentUser(accessToken: string): Promise<CurrentUserResponse> {
  return requestJson<CurrentUserResponse>(
    "/internal/v1/users/me",
    {
      method: "GET",
    },
    accessToken,
  );
}

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

export async function createQuery(
  payload: QueryRequest,
  accessToken: string,
): Promise<QueryResponse> {
  return requestJson<QueryResponse>(
    "/internal/v1/queries",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function streamQuery(
  payload: QueryRequest,
  accessToken: string,
  handlers: QueryStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({
    accept: "text/event-stream",
    "content-type": "application/json",
  });
  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }
  const response = await fetch(buildUrl("/internal/v1/query-streams"), {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const payload = parseJson(await response.text());
    throw new ApiRequestError(
      response.status,
      isApiErrorPayload(payload) ? payload : null,
      `请求失败，状态码 ${response.status}`,
    );
  }
  if (!response.body) {
    throw new ApiRequestError(0, null, "浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = dispatchBufferedEvents(buffer, handlers);
  }
  buffer += decoder.decode();
  dispatchBufferedEvents(`${buffer}\n\n`, handlers);
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  bearerToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (bearerToken) {
    headers.set("authorization", `Bearer ${bearerToken}`);
  }

  const response = await fetch(buildUrl(path), { ...init, headers });
  const text = await response.text();
  const payload = parseJson(text);
  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      isApiErrorPayload(payload) ? payload : null,
      `请求失败，状态码 ${response.status}`,
    );
  }
  return payload as T;
}

async function requestVoid(
  path: string,
  init: RequestInit,
  bearerToken?: string,
): Promise<void> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (bearerToken) {
    headers.set("authorization", `Bearer ${bearerToken}`);
  }

  const response = await fetch(buildUrl(path), { ...init, headers });
  if (response.ok) {
    return;
  }
  const payload = parseJson(await response.text());
  throw new ApiRequestError(
    response.status,
    isApiErrorPayload(payload) ? payload : null,
    `请求失败，状态码 ${response.status}`,
  );
}

function dispatchBufferedEvents(buffer: string, handlers: QueryStreamHandlers): string {
  const parts = buffer.split("\n\n");
  const tail = parts.pop() ?? "";
  for (const frame of parts) {
    dispatchEventFrame(frame, handlers);
  }
  return tail;
}

function dispatchEventFrame(frame: string, handlers: QueryStreamHandlers): void {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  const payload = parseJson(dataLines.join("\n"));
  if (!payload || typeof payload !== "object") {
    return;
  }
  const data = payload as Record<string, unknown>;
  if (eventName === "metadata") {
    handlers.onMetadata?.(data as unknown as QueryStreamMetadata);
  } else if (eventName === "token") {
    handlers.onToken?.(typeof data.delta === "string" ? data.delta : "");
  } else if (eventName === "citation") {
    handlers.onCitation?.(data as unknown as CitationData);
  } else if (eventName === "done") {
    handlers.onDone?.(data as unknown as QueryStreamDone);
  } else if (eventName === "error") {
    throw new ApiRequestError(0, data as unknown as ApiErrorPayload, "流式查询失败");
  }
}

function buildUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function parseJson(value: string): unknown {
  if (!value) {
    return null;
  }
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  return Boolean(value && typeof value === "object" && "error_code" in value);
}
