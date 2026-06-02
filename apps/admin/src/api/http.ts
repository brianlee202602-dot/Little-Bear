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

  constructor(status: number, payload: ApiErrorPayload | null, fallbackMessage: string) {
    super(payload?.message ?? fallbackMessage);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
  }
}

export async function requestJson<T>(
  path: string,
  init: RequestInit,
  bearerToken?: string,
): Promise<T> {
  const headers = buildHeaders(init, bearerToken);
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

export async function requestVoid(
  path: string,
  init: RequestInit,
  bearerToken?: string,
): Promise<void> {
  const headers = buildHeaders(init, bearerToken);
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

export function buildUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function parseJson(text: string): unknown {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export function isApiErrorPayload(payload: unknown): payload is ApiErrorPayload {
  return Boolean(payload) && typeof payload === "object";
}

function buildHeaders(init: RequestInit, bearerToken?: string): Headers {
  const headers = new Headers(init.headers);
  if (init.body && !isFormDataBody(init.body) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (bearerToken) {
    headers.set("authorization", `Bearer ${bearerToken}`);
  }
  return headers;
}

function isFormDataBody(body: BodyInit): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}
