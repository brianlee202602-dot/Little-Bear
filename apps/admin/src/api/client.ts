const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

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

async function requestJson<T>(
  path: string,
  init: RequestInit,
  setupToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (setupToken) {
    headers.set("authorization", `Bearer ${setupToken}`);
  }

  const response = await fetch(buildUrl(path), { ...init, headers });
  const text = await response.text();
  const payload = parseJson(text);

  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      isApiErrorPayload(payload) ? payload : null,
      `request failed with status ${response.status}`,
    );
  }
  return payload as T;
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
