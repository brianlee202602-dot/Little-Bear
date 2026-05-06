const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

// 初始化阶段只暴露 setup 相关接口；这里集中处理 base url、JWT 和错误载荷解析。
export interface SetupStateData {
  initialized: boolean;
  setup_status: string;
  active_config_version: number | null;
  setup_required: boolean;
  active_config_present: boolean;
  recovery_setup_allowed: boolean;
  recovery_reason: string | null;
  system_token_expires_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface SetupStateResponse {
  request_id: string;
  data: SetupStateData;
}

export interface SetupIssue {
  code?: string;
  error_code?: string;
  path?: string;
  message?: string;
  retryable?: boolean;
  [key: string]: unknown;
}

export interface SetupValidationData {
  valid: boolean;
  errors: SetupIssue[];
  warnings: SetupIssue[];
}

export interface SetupValidationResponse {
  request_id: string;
  data: SetupValidationData;
}

export interface SetupInitializationData {
  initialized: boolean;
  active_config_version: number;
  enterprise_id: string;
  admin_user_id: string;
}

export interface SetupInitializationResponse {
  request_id: string;
  data: SetupInitializationData;
}

export interface LoginRequest {
  username: string;
  password: string;
  enterprise_code?: string;
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

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

export interface ApiErrorPayload {
  request_id?: string;
  error_code?: string;
  message?: string;
  stage?: string;
  retryable?: boolean;
  details?: Record<string, unknown>;
}

export class ApiRequestError extends Error {
  status: number;
  payload: ApiErrorPayload | null;

  constructor(status: number, payload: ApiErrorPayload | null, fallbackMessage: string) {
    super(payload?.message ?? fallbackMessage);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
  }
}

export async function getSetupState(setupToken?: string): Promise<SetupStateResponse> {
  return requestJson<SetupStateResponse>("/internal/v1/setup-state", { method: "GET" }, setupToken);
}

export async function validateSetupConfig(
  payload: unknown,
  setupToken?: string,
): Promise<SetupValidationResponse> {
  return requestJson<SetupValidationResponse>(
    "/internal/v1/setup-config-validations",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    setupToken,
  );
}

export async function initializeSetup(
  payload: unknown,
  setupToken?: string,
): Promise<SetupInitializationResponse> {
  return requestJson<SetupInitializationResponse>(
    "/internal/v1/setup-initialization",
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: {
        "x-setup-confirm": "initialize",
      },
    },
    setupToken,
  );
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

export async function changeCurrentUserPassword(
  payload: PasswordChangeRequest,
  accessToken: string,
): Promise<void> {
  await requestVoid(
    "/internal/v1/users/me/password",
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  bearerToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  // 所有写接口都发送 JSON；调用方显式传入 setup token 或普通 access/refresh token。
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
    // 后端错误统一保留 request_id/details，页面可以据此展示结构化校验和依赖检查结果。
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

function buildUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function parseJson(text: string): unknown {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isApiErrorPayload(payload: unknown): payload is ApiErrorPayload {
  return Boolean(payload) && typeof payload === "object";
}
