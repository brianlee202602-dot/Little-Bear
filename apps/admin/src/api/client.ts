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

export type ConfigStatus = "draft" | "validating" | "active" | "archived" | "failed";
export type ConfigRiskLevel = "low" | "medium" | "high" | "critical";

export interface ConfigItemData {
  key: string;
  value_json: Record<string, unknown>;
  scope_type: string;
  status: ConfigStatus;
  version: number;
}

export interface PaginationData {
  page: number;
  page_size: number;
  total: number;
}

export interface ConfigItemResponse {
  request_id: string;
  data: ConfigItemData;
}

export interface ConfigItemListResponse {
  request_id: string;
  data: ConfigItemData[];
  pagination: PaginationData;
}

export interface ConfigVersionData {
  version: number;
  status: ConfigStatus;
  risk_level: ConfigRiskLevel;
  created_by: string | null;
}

export interface ConfigVersionResponse {
  request_id: string;
  data: ConfigVersionData;
}

export interface ConfigVersionListResponse {
  request_id: string;
  data: ConfigVersionData[];
}

export type AuditResult = "success" | "failure" | "denied";

export interface AuditLogData {
  id: string;
  request_id: string | null;
  trace_id: string | null;
  event_name: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  result: AuditResult;
  risk_level: ConfigRiskLevel;
  config_version: number | null;
  permission_version: number | null;
  index_version_hash: string | null;
  summary_json: Record<string, unknown>;
  error_code: string | null;
  created_at: string | null;
}

export interface AuditLogListResponse {
  request_id: string;
  data: AuditLogData[];
  pagination: PaginationData;
}

export type AdminUserStatus = "active" | "disabled" | "locked" | "deleted";

export interface AdminDepartmentData {
  id: string;
  code: string;
  name: string;
  status: string;
  is_primary: boolean;
  is_default: boolean;
}

export interface AdminDepartmentCreateRequest {
  code: string;
  name: string;
}

export interface AdminDepartmentPatchRequest {
  name?: string;
  status?: "active" | "disabled";
}

export interface AdminDepartmentListResponse {
  request_id: string;
  data: AdminDepartmentData[];
  pagination: PaginationData;
}

export interface AdminDepartmentResponse {
  request_id: string;
  data: AdminDepartmentData;
}

export interface AdminUserDepartmentsResponse {
  request_id: string;
  data: AdminDepartmentData[];
}

export interface AdminUserDepartmentsPutRequest {
  department_ids: string[];
}

export interface AdminKnowledgeBaseData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
  owner_department_id: string;
  default_visibility: "department" | "enterprise";
  config_scope_id: string | null;
}

export interface AdminKnowledgeBaseListResponse {
  request_id: string;
  data: AdminKnowledgeBaseData[];
  pagination: PaginationData;
}

export interface AdminRoleData {
  id: string;
  code: string;
  name: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  is_builtin: boolean;
  status: "active" | "disabled" | "archived";
  scopes: string[];
}

export interface AdminUserData {
  id: string;
  username: string;
  name: string;
  status: AdminUserStatus;
  enterprise_id: string;
  email: string | null;
  phone: string | null;
  departments: AdminDepartmentData[];
  roles: AdminRoleData[];
  scopes: string[];
}

export interface AdminUserListResponse {
  request_id: string;
  data: AdminUserData[];
  pagination: PaginationData;
}

export interface AdminUserResponse {
  request_id: string;
  data: AdminUserData;
}

export interface AdminUserCreateRequest {
  username: string;
  name: string;
  initial_password: string;
  department_ids: string[];
  role_ids: string[];
}

export interface AdminUserPatchRequest {
  name?: string;
  status?: "active" | "disabled" | "locked";
}

export interface AdminPasswordResetRequest {
  new_password: string;
  force_change_password: boolean;
}

export interface AdminRoleListResponse {
  request_id: string;
  data: AdminRoleData[];
}

export interface AdminRoleBindingData {
  id: string;
  role_id: string;
  subject_type: "user" | "department";
  subject_id: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  scope_id: string | null;
  role_code: string | null;
  role_name: string | null;
}

export interface AdminRoleBindingListResponse {
  request_id: string;
  data: AdminRoleBindingData[];
}

export interface AdminRoleBindingInputData {
  role_id: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  scope_id?: string | null;
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

export async function listConfigs(accessToken: string): Promise<ConfigItemListResponse> {
  return requestJson<ConfigItemListResponse>(
    "/internal/v1/admin/configs",
    { method: "GET" },
    accessToken,
  );
}

export async function getConfigItem(
  key: string,
  accessToken: string,
): Promise<ConfigItemResponse> {
  return requestJson<ConfigItemResponse>(
    `/internal/v1/admin/configs/${encodeURIComponent(key)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function saveConfigDraft(
  key: string,
  valueJson: Record<string, unknown>,
  accessToken: string,
): Promise<ConfigItemResponse> {
  return requestJson<ConfigItemResponse>(
    `/internal/v1/admin/configs/${encodeURIComponent(key)}`,
    {
      method: "PUT",
      body: JSON.stringify({ value_json: valueJson }),
      headers: { "x-config-confirm": "save-draft" },
    },
    accessToken,
  );
}

export async function validateAdminConfig(
  config: Record<string, unknown>,
  accessToken: string,
): Promise<SetupValidationResponse> {
  return requestJson<SetupValidationResponse>(
    "/internal/v1/admin/config-validations",
    {
      method: "POST",
      body: JSON.stringify({ config }),
    },
    accessToken,
  );
}

export async function listConfigVersions(
  accessToken: string,
): Promise<ConfigVersionListResponse> {
  return requestJson<ConfigVersionListResponse>(
    "/internal/v1/admin/config-versions",
    { method: "GET" },
    accessToken,
  );
}

export async function publishConfigVersion(
  version: number,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status: "active" }),
      headers: { "x-config-confirm": "publish" },
    },
    accessToken,
  );
}

export async function discardConfigDraft(version: number, accessToken: string): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "DELETE",
      headers: { "x-config-confirm": "discard-draft" },
    },
    accessToken,
  );
}

export async function listAuditLogs(
  accessToken: string,
  filters: { resource_type?: string; result?: string; risk_level?: string } = {},
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams({ page_size: "20" });
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      params.set(key, value);
    }
  }
  return requestJson<AuditLogListResponse>(
    `/internal/v1/admin/audit-logs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminUsers(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminUserListResponse> {
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
  return requestJson<AdminUserListResponse>(
    `/internal/v1/admin/users?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminDepartments(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminDepartmentListResponse> {
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
  return requestJson<AdminDepartmentListResponse>(
    `/internal/v1/admin/departments?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminDepartment(
  payload: AdminDepartmentCreateRequest,
  accessToken: string,
): Promise<AdminDepartmentResponse> {
  return requestJson<AdminDepartmentResponse>(
    "/internal/v1/admin/departments",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function getAdminDepartment(
  departmentId: string,
  accessToken: string,
): Promise<AdminDepartmentResponse> {
  return requestJson<AdminDepartmentResponse>(
    `/internal/v1/admin/departments/${encodeURIComponent(departmentId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function patchAdminDepartment(
  departmentId: string,
  payload: AdminDepartmentPatchRequest,
  accessToken: string,
): Promise<AdminDepartmentResponse> {
  return requestJson<AdminDepartmentResponse>(
    `/internal/v1/admin/departments/${encodeURIComponent(departmentId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function deleteAdminDepartment(
  departmentId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/departments/${encodeURIComponent(departmentId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-department-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}

export async function createAdminUser(
  payload: AdminUserCreateRequest,
  accessToken: string,
  confirmedHighRisk: boolean,
): Promise<AdminUserResponse> {
  return requestJson<AdminUserResponse>(
    "/internal/v1/admin/users",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmedHighRisk ? { "x-user-confirm": "create-admin" } : undefined,
    },
    accessToken,
  );
}

export async function patchAdminUser(
  userId: string,
  payload: AdminUserPatchRequest,
  accessToken: string,
  confirmedDisableAdmin: boolean,
): Promise<AdminUserResponse> {
  return requestJson<AdminUserResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: confirmedDisableAdmin ? { "x-user-confirm": "disable-admin" } : undefined,
    },
    accessToken,
  );
}

export async function deleteAdminUser(
  userId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-user-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}

export async function resetAdminUserPassword(
  userId: string,
  payload: AdminPasswordResetRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/password`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-user-confirm": "reset-password" } : undefined,
    },
    accessToken,
  );
}

export async function unlockAdminUser(userId: string, accessToken: string): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/lock`,
    { method: "DELETE" },
    accessToken,
  );
}

export async function listAdminUserDepartments(
  userId: string,
  accessToken: string,
): Promise<AdminUserDepartmentsResponse> {
  return requestJson<AdminUserDepartmentsResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/departments`,
    { method: "GET" },
    accessToken,
  );
}

export async function replaceAdminUserDepartments(
  userId: string,
  payload: AdminUserDepartmentsPutRequest,
  accessToken: string,
  confirmedReplacePrimary: boolean,
): Promise<AdminUserDepartmentsResponse> {
  return requestJson<AdminUserDepartmentsResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/departments`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmedReplacePrimary
        ? { "x-department-confirm": "replace-primary" }
        : undefined,
    },
    accessToken,
  );
}

export async function listAdminRoles(accessToken: string): Promise<AdminRoleListResponse> {
  return requestJson<AdminRoleListResponse>(
    "/internal/v1/admin/roles",
    { method: "GET" },
    accessToken,
  );
}

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

export async function listAdminUserRoleBindings(
  userId: string,
  accessToken: string,
): Promise<AdminRoleBindingListResponse> {
  return requestJson<AdminRoleBindingListResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/role-bindings`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminUserRoleBindings(
  userId: string,
  bindings: AdminRoleBindingInputData[],
  accessToken: string,
  confirmedHighRisk: boolean,
): Promise<AdminRoleBindingListResponse> {
  return requestJson<AdminRoleBindingListResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/role-bindings`,
    {
      method: "POST",
      body: JSON.stringify({ bindings }),
      headers: confirmedHighRisk ? { "x-role-binding-confirm": "high-risk" } : undefined,
    },
    accessToken,
  );
}

export async function revokeAdminUserRoleBinding(
  userId: string,
  bindingId: string,
  accessToken: string,
  confirmedRemoveAdmin: boolean,
): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}/role-bindings/${encodeURIComponent(bindingId)}`,
    {
      method: "DELETE",
      headers: confirmedRemoveAdmin ? { "x-role-binding-confirm": "remove-admin" } : undefined,
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
