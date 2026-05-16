const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export interface ApiErrorPayload {
  request_id?: string;
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

export interface CurrentUserRole {
  id: string;
  code: string;
  name: string;
  scope_type: string;
  is_builtin: boolean;
  status: string;
}

export interface CurrentUserDepartment {
  id: string;
  code: string;
  name: string;
  status: string;
  is_primary: boolean;
}

export interface CurrentUserData {
  id: string;
  username: string;
  name: string;
  status: string;
  departments: CurrentUserDepartment[];
  roles: CurrentUserRole[];
  scopes: string[];
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
  owner_department_id: string;
  default_visibility: "department" | "enterprise";
  config_scope_id: string | null;
  policy_version: number;
}

export interface KnowledgeBaseListResponse {
  request_id: string;
  data: KnowledgeBaseData[];
  pagination: PaginationData;
}

export interface DocumentData {
  id: string;
  kb_id: string;
  folder_id: string | null;
  title: string;
  lifecycle_status: string;
  index_status: string;
  owner_department_id: string;
  visibility: "department" | "enterprise";
  current_version_id: string | null;
}

export interface DocumentListResponse {
  request_id: string;
  data: DocumentData[];
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
}

export interface ChunkListResponse {
  request_id: string;
  data: ChunkData[];
}

export type QueryMode = "answer" | "search";
export type QueryConfidence = "low" | "medium" | "high";

export interface QueryRequest {
  kb_ids: string[];
  query: string;
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
  request_id: string;
  answer: string;
  citations: CitationData[];
  confidence: QueryConfidence;
  degraded: boolean;
  degrade_reason: string | null;
  trace_id: string;
}

export type QueryStreamMetadata = Pick<
  QueryResponse,
  "request_id" | "trace_id" | "confidence" | "degraded" | "degrade_reason"
>;

export interface QueryStreamHandlers {
  onMetadata?: (metadata: QueryStreamMetadata) => void;
  onToken?: (delta: string) => void;
  onCitation?: (citation: CitationData) => void;
  onDone?: (result: Omit<QueryResponse, "answer">) => void;
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

export async function listKnowledgeBases(accessToken: string): Promise<KnowledgeBaseListResponse> {
  return requestJson<KnowledgeBaseListResponse>(
    "/internal/v1/knowledge-bases?page=1&page_size=100",
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function listDocuments(
  kbId: string,
  accessToken: string,
): Promise<DocumentListResponse> {
  return requestJson<DocumentListResponse>(
    `/internal/v1/knowledge-bases/${encodeURIComponent(kbId)}/documents?page=1&page_size=100`,
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function listDocumentChunks(
  documentId: string,
  accessToken: string,
): Promise<ChunkListResponse> {
  return requestJson<ChunkListResponse>(
    `/internal/v1/documents/${encodeURIComponent(documentId)}/chunks`,
    {
      method: "GET",
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
    handlers.onDone?.(data as unknown as Omit<QueryResponse, "answer">);
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
