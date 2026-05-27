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
  code?: string | null;
  name: string;
  status: string;
  is_primary: boolean;
  is_default?: boolean;
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

export interface AdminCurrentUserCapabilitiesData extends CurrentUserData {
  departments: CurrentUserDepartment[];
  roles: CurrentUserRole[];
  scopes: string[];
}

export interface AdminCurrentUserCapabilitiesResponse {
  request_id: string;
  data: AdminCurrentUserCapabilitiesData;
}

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

export type ConfigStatus = "draft" | "validating" | "active" | "inactive" | "archived" | "failed";
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
  config: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
  activated_at: string | null;
}

export interface ConfigVersionListItemData {
  version: number;
  status: ConfigStatus;
  risk_level: ConfigRiskLevel;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  activated_at: string | null;
}

export interface ConfigVersionResponse {
  request_id: string;
  data: ConfigVersionData;
}

export interface ConfigVersionListResponse {
  request_id: string;
  data: ConfigVersionListItemData[];
  pagination: PaginationData;
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

export interface AuditLogListItemData {
  id: string;
  event_name: string;
  actor_type: string;
  action: string;
  resource_type: string;
  result: AuditResult;
  risk_level: ConfigRiskLevel;
  config_version: number | null;
  permission_version: number | null;
  error_code: string | null;
  created_at: string | null;
}

export interface AuditLogListResponse {
  request_id: string;
  data: AuditLogListItemData[];
  pagination: PaginationData;
}

export interface AuditLogResponse {
  request_id: string;
  data: AuditLogData;
}

export interface QueryLogData {
  id: string;
  request_id: string;
  trace_id: string;
  user_id: string;
  user_display_name: string | null;
  kb_ids: string[];
  knowledge_base_names: string[];
  query_hash: string;
  status: "success" | "failed" | "denied";
  degraded: boolean;
  degrade_reason: string | null;
  config_version: number;
  permission_version: number;
  permission_filter_hash: string;
  index_version_hash: string | null;
  model_route_hash: string | null;
  latency_ms: number;
  candidate_count: number;
  citation_count: number;
  error_code: string | null;
  created_at: string | null;
}

export interface QueryLogResponse {
  request_id: string;
  data: QueryLogData;
}

export interface QueryLogListItemData {
  id: string;
  user_display_name: string | null;
  knowledge_base_names: string[];
  status: "success" | "failed" | "denied";
  degraded: boolean;
  degrade_reason: string | null;
  latency_ms: number;
  candidate_count: number;
  citation_count: number;
  error_code: string | null;
  created_at: string | null;
}

export interface QueryLogListResponse {
  request_id: string;
  data: QueryLogListItemData[];
  pagination: PaginationData;
}

export interface ModelCallLogData {
  id: string;
  request_id: string | null;
  trace_id: string;
  caller: string;
  model_type: string;
  model_name: string;
  model_version: string | null;
  model_route_hash: string;
  status: "success" | "failed" | "degraded";
  latency_ms: number;
  token_usage_json: Record<string, unknown> | null;
  degraded: boolean;
  config_version: number | null;
  prompt_hash: string | null;
  input_hash: string | null;
  output_hash: string | null;
  error_code: string | null;
  created_at: string | null;
}

export interface ModelCallLogResponse {
  request_id: string;
  data: ModelCallLogData;
}

export interface ModelCallLogListItemData {
  id: string;
  caller: string;
  model_type: string;
  model_name: string;
  model_version: string | null;
  status: "success" | "failed" | "degraded";
  latency_ms: number;
  degraded: boolean;
  error_code: string | null;
  created_at: string | null;
}

export interface ModelCallLogListResponse {
  request_id: string;
  data: ModelCallLogListItemData[];
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

export interface AdminDepartmentListItemData {
  id: string;
  name: string;
  status: string;
  is_primary?: boolean;
  is_default: boolean;
}

export interface AdminDepartmentOptionData {
  id: string;
  name: string;
  status: string;
  is_primary?: boolean;
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
  data: AdminDepartmentListItemData[];
  pagination: PaginationData;
}

export interface AdminDepartmentOptionListResponse {
  request_id: string;
  data: AdminDepartmentOptionData[];
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
  owner_department: AdminDepartmentData | null;
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id: string;
  default_document_owner_department: AdminDepartmentData | null;
  access_rules: KnowledgeBaseAccessRuleData[];
  config_scope_id: string | null;
  policy_version: number;
}

export interface AdminKnowledgeBaseListItemData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
  owner_department_id: string;
  owner_department_name: string | null;
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id: string;
  default_document_owner_department_name: string | null;
}

export interface AdminKnowledgeBaseOptionData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface KnowledgeBaseAccessRuleData {
  subject_type: "department" | "user" | "role";
  subject_id: string;
  permission: "discover" | "query" | "manage";
}

export interface AdminKnowledgeBaseCreateRequest {
  name: string;
  owner_department_id: string;
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id?: string | null;
  access_rules?: KnowledgeBaseAccessRuleData[];
  config_scope_id?: string | null;
}

export interface AdminKnowledgeBasePatchRequest {
  name?: string;
  status?: "active" | "disabled" | "archived";
  kb_visibility?: "enterprise" | "department_acl" | "private";
  default_document_visibility?: "department" | "enterprise";
  default_document_owner_department_id?: string | null;
  config_scope_id?: string | null;
}

export interface AdminKnowledgeBaseListResponse {
  request_id: string;
  data: AdminKnowledgeBaseListItemData[];
  pagination: PaginationData;
}

export interface AdminKnowledgeBaseOptionListResponse {
  request_id: string;
  data: AdminKnowledgeBaseOptionData[];
  pagination: PaginationData;
}

export interface AdminKnowledgeBaseResponse {
  request_id: string;
  data: AdminKnowledgeBaseData;
}

export interface AdminFolderData {
  id: string;
  kb_id: string;
  parent_id: string | null;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface AdminFolderOptionData {
  id: string;
  name: string;
  status: "active" | "disabled" | "archived";
}

export interface AdminFolderCreateRequest {
  name: string;
  parent_id?: string | null;
}

export interface AdminFolderPatchRequest {
  name?: string;
  parent_id?: string | null;
  status?: "active" | "disabled" | "archived";
}

export interface AdminFolderListResponse {
  request_id: string;
  data: AdminFolderData[];
  pagination: PaginationData;
}

export interface AdminFolderOptionListResponse {
  request_id: string;
  data: AdminFolderOptionData[];
  pagination: PaginationData;
}

export interface AdminFolderResponse {
  request_id: string;
  data: AdminFolderData;
}

export interface AdminDocumentData {
  id: string;
  kb_id: string;
  folder_id: string | null;
  title: string;
  lifecycle_status: "draft" | "active" | "archived" | "deleted";
  index_status: "none" | "indexing" | "indexed" | "index_failed" | "blocked";
  owner_department_id: string;
  visibility: "department" | "enterprise";
  current_version_id: string | null;
  current_version_no: number | null;
}

export interface AdminDocumentListResponse {
  request_id: string;
  data: AdminDocumentData[];
  pagination: PaginationData;
}

export interface AdminDocumentResponse {
  request_id: string;
  data: AdminDocumentData;
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

export interface IndexVersionData {
  id: string;
  document_id: string;
  document_version_id: string;
  embedding_model: string;
  model_version: string;
  dimension: number;
  collection_name: string;
  status: "draft" | "ready" | "active" | "archived" | "pending_delete" | "failed";
  chunk_count: number;
  created_at: string | null;
  activated_at: string | null;
}

export interface IndexVersionListResponse {
  request_id: string;
  data: IndexVersionData[];
}

export interface IndexCollectionHealthData {
  collection_name: string;
  expected_dimension: number | null;
  qdrant_reachable: boolean;
  qdrant_exists: boolean | null;
  qdrant_status: string | null;
  qdrant_vector_size: number | null;
  qdrant_points_count: number | null;
  db_index_version_count: number;
  active_index_version_count: number;
  pending_delete_index_version_count: number;
  failed_index_version_count: number;
  active_ref_count: number;
  draft_ref_count: number;
  deleted_ref_count: number;
  pending_delete_ref_count: number;
  active_ref_mismatch_count: number;
  issues: string[];
}

export interface IndexHealthResponse {
  request_id: string;
  data: IndexCollectionHealthData[];
}

export interface IndexCollectionSnapshotData {
  collection_name: string;
  name: string;
  size: number | null;
  creation_time: string | null;
  checksum: string | null;
}

export interface IndexCollectionSnapshotResponse {
  request_id: string;
  data: IndexCollectionSnapshotData;
}

export interface IndexCollectionSnapshotListResponse {
  request_id: string;
  data: IndexCollectionSnapshotData[];
}

export interface IndexCollectionSnapshotRecoverRequest {
  location: string;
  priority?: "Snapshot" | "Replica" | null;
  checksum?: string | null;
}

export interface IndexCollectionOperationData {
  collection_name: string;
  operation: "snapshot_recover";
  accepted: boolean;
  result: boolean | null;
}

export interface IndexCollectionOperationResponse {
  request_id: string;
  data: IndexCollectionOperationData;
}

export interface IndexJobCreateRequest {
  kb_id?: string | null;
  document_ids?: string[];
}

export interface IndexVersionCleanupJobCreateRequest {
  index_version_ids: string[];
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

export interface AdminDocumentPreviewChunkData {
  id: string;
  document_id: string;
  document_version_id: string;
  text: string;
  text_preview: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  ordinal: number;
  heading_path: string | null;
  source_offsets: Record<string, unknown> | null;
  text_status: "object" | "preview_only" | "object_unavailable";
}

export interface AdminDocumentPreviewData {
  doc_id: string;
  title: string;
  chunks: AdminDocumentPreviewChunkData[];
}

export interface AdminDocumentPreviewResponse {
  request_id: string;
  data: AdminDocumentPreviewData;
  pagination: PaginationData;
}

export interface ResourcePermissionPutRequest {
  visibility: "department" | "enterprise";
  owner_department_id?: string | null;
}

export interface KnowledgeBasePermissionPutRequest {
  kb_visibility: "enterprise" | "department_acl" | "private";
  default_document_visibility: "department" | "enterprise";
  default_document_owner_department_id: string;
  access_rules: KnowledgeBaseAccessRuleData[];
}

export interface PermissionPolicyResponse {
  request_id: string;
  data: {
    resource_type: "document";
    resource_id: string;
    visibility: "department" | "enterprise";
    permission_version: number;
  };
}

export interface KnowledgeBasePermissionPolicyResponse {
  request_id: string;
  data: {
    resource_type: "knowledge_base";
    resource_id: string;
    kb_visibility: "enterprise" | "department_acl" | "private";
    default_document_visibility: "department" | "enterprise";
    default_document_owner_department_id: string;
    access_rules: KnowledgeBaseAccessRuleData[];
    permission_version: number;
  };
}

export interface AcceptedResponse {
  request_id: string;
  data: {
    accepted: boolean;
    job_id: string | null;
  };
}

export type ImportJobStatus =
  | "queued"
  | "running"
  | "retrying"
  | "partial_success"
  | "success"
  | "failed"
  | "cancelled";

export type ImportJobStage =
  | "validate"
  | "parse"
  | "clean"
  | "chunk"
  | "embed"
  | "index"
  | "publish"
  | "cleanup"
  | "finished";

export interface ImportJobData {
  id: string;
  kb_id: string | null;
  job_type: string | null;
  status: ImportJobStatus;
  stage: ImportJobStage;
  document_ids: string[];
  error_summary: string | null;
}

export interface ImportJobListItemData {
  id: string;
  kb_id: string | null;
  job_type: string | null;
  status: ImportJobStatus;
  stage: ImportJobStage;
  document_count: number;
  error_summary: string | null;
}

export interface ImportJobResponse {
  request_id: string;
  data: ImportJobData;
}

export interface ImportJobListResponse {
  request_id: string;
  data: ImportJobListItemData[];
  pagination: PaginationData;
}

export interface IndexJobRetryRequest {
  job_ids: string[];
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

export interface AdminRoleListItemData {
  id: string;
  code: string;
  name: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  is_builtin: boolean;
  status: "active" | "disabled" | "archived";
}

export interface AdminAssignableRoleOptionData {
  id: string;
  code: string;
  name: string;
  scope_type: "enterprise" | "department" | "knowledge_base";
  status: "active" | "disabled" | "archived";
  risk_level: "low" | "high";
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

export interface AdminUserListItemData {
  id: string;
  username: string;
  name: string;
  status: AdminUserStatus;
  department_names: string[];
  role_names: string[];
}

export interface AdminUserListResponse {
  request_id: string;
  data: AdminUserListItemData[];
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
  data: AdminRoleListItemData[];
  pagination: PaginationData;
}

export interface AdminAssignableRoleOptionListResponse {
  request_id: string;
  data: AdminAssignableRoleOptionData[];
  pagination: PaginationData;
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

export async function getAdminCurrentUserCapabilities(
  accessToken: string,
): Promise<AdminCurrentUserCapabilitiesResponse> {
  return requestJson<AdminCurrentUserCapabilitiesResponse>(
    "/internal/v1/admin/users/me/capabilities",
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
  filters: { page?: number; page_size?: number } = {},
): Promise<ConfigVersionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  return requestJson<ConfigVersionListResponse>(
    `/internal/v1/admin/config-versions?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getConfigVersion(
  version: number,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    `/internal/v1/admin/config-versions/${version}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createConfigVersion(
  config: Record<string, unknown>,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    "/internal/v1/admin/config-versions",
    {
      method: "POST",
      body: JSON.stringify({ config }),
      headers: { "x-config-confirm": "save-draft" },
    },
    accessToken,
  );
}

export async function updateConfigVersion(
  version: number,
  config: Record<string, unknown>,
  accessToken: string,
): Promise<ConfigVersionResponse> {
  return requestJson<ConfigVersionResponse>(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "PUT",
      body: JSON.stringify({ config }),
      headers: { "x-config-confirm": "save-draft" },
    },
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

export async function archiveConfigVersion(version: number, accessToken: string): Promise<void> {
  await requestVoid(
    `/internal/v1/admin/config-versions/${version}`,
    {
      method: "DELETE",
      headers: { "x-config-confirm": "archive" },
    },
    accessToken,
  );
}

export async function listAuditLogs(
  accessToken: string,
  filters: { page?: number; page_size?: number; resource_type?: string; result?: string; risk_level?: string } = {},
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 20),
  });
  for (const [key, value] of Object.entries(filters)) {
    if (key === "page" || key === "page_size" || value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  return requestJson<AuditLogListResponse>(
    `/internal/v1/admin/audit-logs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getAuditLog(
  auditLogId: string,
  accessToken: string,
): Promise<AuditLogResponse> {
  return requestJson<AuditLogResponse>(
    `/internal/v1/admin/audit-logs/${encodeURIComponent(auditLogId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listQueryLogs(
  accessToken: string,
  filters: {
    page?: number;
    page_size?: number;
    user_id?: string;
    kb_id?: string;
    status?: string;
    degraded?: boolean | null;
    degrade_reason?: string;
    request_id?: string;
    trace_id?: string;
    error_code?: string;
  } = {},
): Promise<QueryLogListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  for (const [key, value] of Object.entries(filters)) {
    if (key === "page" || key === "page_size" || value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  return requestJson<QueryLogListResponse>(
    `/internal/v1/admin/query-logs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getQueryLog(
  queryLogId: string,
  accessToken: string,
): Promise<QueryLogResponse> {
  return requestJson<QueryLogResponse>(
    `/internal/v1/admin/query-logs/${encodeURIComponent(queryLogId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listModelCallLogs(
  accessToken: string,
  filters: {
    page?: number;
    page_size?: number;
    model?: string;
    model_type?: string;
    caller?: string;
    status?: string;
    degraded?: boolean | null;
    request_id?: string;
    trace_id?: string;
    error_code?: string;
  } = {},
): Promise<ModelCallLogListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  });
  for (const [key, value] of Object.entries(filters)) {
    if (key === "page" || key === "page_size" || value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  return requestJson<ModelCallLogListResponse>(
    `/internal/v1/admin/model-call-logs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getModelCallLog(
  modelCallLogId: string,
  accessToken: string,
): Promise<ModelCallLogResponse> {
  return requestJson<ModelCallLogResponse>(
    `/internal/v1/admin/model-call-logs/${encodeURIComponent(modelCallLogId)}`,
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

export async function listAdminDepartmentOptions(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminDepartmentOptionListResponse> {
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
  return requestJson<AdminDepartmentOptionListResponse>(
    `/internal/v1/admin/department-options?${params.toString()}`,
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

export async function getAdminUser(
  userId: string,
  accessToken: string,
): Promise<AdminUserResponse> {
  return requestJson<AdminUserResponse>(
    `/internal/v1/admin/users/${encodeURIComponent(userId)}`,
    { method: "GET" },
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

export async function listAdminRoles(
  accessToken: string,
  filters: {
    keyword?: string;
    status?: string;
    scope_type?: string;
    page?: number;
    page_size?: number;
  } = {},
): Promise<AdminRoleListResponse> {
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
  if (filters.scope_type) {
    params.set("scope_type", filters.scope_type);
  }
  return requestJson<AdminRoleListResponse>(
    `/internal/v1/admin/roles?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminAssignableRoleOptions(
  accessToken: string,
  filters: {
    keyword?: string;
    status?: string;
    scope_type?: string;
    page?: number;
    page_size?: number;
  } = {},
): Promise<AdminAssignableRoleOptionListResponse> {
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
  if (filters.scope_type) {
    params.set("scope_type", filters.scope_type);
  }
  return requestJson<AdminAssignableRoleOptionListResponse>(
    `/internal/v1/admin/assignable-role-options?${params.toString()}`,
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

export async function listAdminKnowledgeBaseOptions(
  accessToken: string,
  filters: { keyword?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<AdminKnowledgeBaseOptionListResponse> {
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
  return requestJson<AdminKnowledgeBaseOptionListResponse>(
    `/internal/v1/admin/knowledge-base-options?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function getAdminKnowledgeBase(
  kbId: string,
  accessToken: string,
): Promise<AdminKnowledgeBaseResponse> {
  return requestJson<AdminKnowledgeBaseResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminKnowledgeBase(
  payload: AdminKnowledgeBaseCreateRequest,
  accessToken: string,
  confirmedEnterpriseVisibility: boolean,
): Promise<AdminKnowledgeBaseResponse> {
  return requestJson<AdminKnowledgeBaseResponse>(
    "/internal/v1/admin/knowledge-bases",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmedEnterpriseVisibility
        ? { "x-knowledge-base-confirm": "enterprise-visible" }
        : undefined,
    },
    accessToken,
  );
}

export async function patchAdminKnowledgeBase(
  kbId: string,
  payload: AdminKnowledgeBasePatchRequest,
  accessToken: string,
  confirmedVisibilityExpand: boolean,
): Promise<AdminKnowledgeBaseResponse> {
  return requestJson<AdminKnowledgeBaseResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: confirmedVisibilityExpand
        ? { "x-knowledge-base-confirm": "visibility-expand" }
        : undefined,
    },
    accessToken,
  );
}

export async function deleteAdminKnowledgeBase(
  kbId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-knowledge-base-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}

export async function listAdminFolders(
  kbId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number } = {},
): Promise<AdminFolderListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 100),
  });
  return requestJson<AdminFolderListResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/folders?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminFolderOptions(
  kbId: string,
  accessToken: string,
  filters: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
): Promise<AdminFolderOptionListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 100),
  });
  for (const [key, value] of Object.entries(filters)) {
    if (key === "page" || key === "page_size" || value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  return requestJson<AdminFolderOptionListResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/folder-options?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminFolder(
  kbId: string,
  payload: AdminFolderCreateRequest,
  accessToken: string,
): Promise<AdminFolderResponse> {
  return requestJson<AdminFolderResponse>(
    `/internal/v1/admin/knowledge-bases/${encodeURIComponent(kbId)}/folders`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function patchAdminFolder(
  folderId: string,
  payload: AdminFolderPatchRequest,
  accessToken: string,
): Promise<AdminFolderResponse> {
  return requestJson<AdminFolderResponse>(
    `/internal/v1/admin/folders/${encodeURIComponent(folderId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function deleteAdminFolder(
  folderId: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/folders/${encodeURIComponent(folderId)}`,
    {
      method: "DELETE",
      headers: confirmed ? { "x-folder-confirm": "delete" } : undefined,
    },
    accessToken,
  );
}

export async function listAdminDocuments(
  kbId: string,
  accessToken: string,
  filters: { status?: string; page?: number; page_size?: number } = {},
): Promise<AdminDocumentListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 100),
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
): Promise<IndexVersionListResponse> {
  return requestJson<IndexVersionListResponse>(
    `/internal/v1/admin/documents/${encodeURIComponent(documentId)}/index-versions`,
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

export async function createAdminIndexJob(
  payload: IndexJobCreateRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    "/internal/v1/admin/index-jobs",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "rebuild" } : undefined,
    },
    accessToken,
  );
}

export async function createAdminIndexVersionCleanupJob(
  payload: IndexVersionCleanupJobCreateRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    "/internal/v1/admin/index-versions/cleanup-jobs",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "cleanup" } : undefined,
    },
    accessToken,
  );
}

export async function getAdminIndexHealth(accessToken: string): Promise<IndexHealthResponse> {
  return requestJson<IndexHealthResponse>(
    "/internal/v1/admin/index-health",
    { method: "GET" },
    accessToken,
  );
}

export async function listAdminIndexCollectionSnapshots(
  collectionName: string,
  accessToken: string,
): Promise<IndexCollectionSnapshotListResponse> {
  return requestJson<IndexCollectionSnapshotListResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/snapshots`,
    { method: "GET" },
    accessToken,
  );
}

export async function createAdminIndexCollectionSnapshot(
  collectionName: string,
  accessToken: string,
  confirmed: boolean,
): Promise<IndexCollectionSnapshotResponse> {
  return requestJson<IndexCollectionSnapshotResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/snapshots`,
    {
      method: "POST",
      headers: confirmed ? { "x-index-confirm": "snapshot" } : undefined,
    },
    accessToken,
  );
}

export async function recoverAdminIndexCollectionSnapshot(
  collectionName: string,
  payload: IndexCollectionSnapshotRecoverRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<IndexCollectionOperationResponse> {
  return requestJson<IndexCollectionOperationResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/snapshot-recoveries`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "restore" } : undefined,
    },
    accessToken,
  );
}

export async function createAdminIndexCollectionRebuildJob(
  collectionName: string,
  accessToken: string,
  confirmed: boolean,
): Promise<AcceptedResponse> {
  return requestJson<AcceptedResponse>(
    `/internal/v1/admin/index-collections/${encodeURIComponent(collectionName)}/rebuild-jobs`,
    {
      method: "POST",
      headers: confirmed ? { "x-index-confirm": "rebuild" } : undefined,
    },
    accessToken,
  );
}

export async function putKnowledgeBasePermissions(
  kbId: string,
  payload: KnowledgeBasePermissionPutRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<KnowledgeBasePermissionPolicyResponse> {
  return requestJson<KnowledgeBasePermissionPolicyResponse>(
    `/internal/v1/knowledge-bases/${encodeURIComponent(kbId)}/permissions`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-permission-confirm": "replace" } : undefined,
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

export async function uploadKnowledgeBaseDocuments(
  kbId: string,
  payload: {
    files: File[];
    visibility?: "department" | "enterprise";
    owner_department_id?: string;
    folder_id?: string;
    idempotency_key?: string;
  },
  accessToken: string,
): Promise<ImportJobResponse> {
  const form = new FormData();
  for (const file of payload.files) {
    form.append("files", file);
  }
  if (payload.visibility) {
    form.append("visibility", payload.visibility);
  }
  if (payload.owner_department_id) {
    form.append("owner_department_id", payload.owner_department_id);
  }
  if (payload.folder_id) {
    form.append("folder_id", payload.folder_id);
  }
  if (payload.idempotency_key) {
    form.append("idempotency_key", payload.idempotency_key);
  }
  return requestJson<ImportJobResponse>(
    `/internal/v1/knowledge-bases/${encodeURIComponent(kbId)}/documents`,
    {
      method: "POST",
      body: form,
    },
    accessToken,
  );
}

export async function listAdminImportJobs(
  accessToken: string,
  filters: {
    page?: number;
    page_size?: number;
    status?: string;
    stage?: string;
    kb_id?: string;
    job_type?: string;
  } = {},
): Promise<ImportJobListResponse> {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 100),
  });
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.stage) {
    params.set("stage", filters.stage);
  }
  if (filters.kb_id) {
    params.set("kb_id", filters.kb_id);
  }
  if (filters.job_type) {
    params.set("job_type", filters.job_type);
  }
  return requestJson<ImportJobListResponse>(
    `/internal/v1/admin/import-jobs?${params.toString()}`,
    { method: "GET" },
    accessToken,
  );
}

export async function retryAdminIndexJobs(
  payload: IndexJobRetryRequest,
  accessToken: string,
  confirmed: boolean,
): Promise<ImportJobListResponse> {
  return requestJson<ImportJobListResponse>(
    "/internal/v1/admin/index-jobs/retries",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: confirmed ? { "x-index-confirm": "retry" } : undefined,
    },
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
  // 默认写接口发送 JSON；FormData 由浏览器自动设置 multipart boundary。
  if (init.body && !isFormDataBody(init.body) && !headers.has("content-type")) {
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
  if (init.body && !isFormDataBody(init.body) && !headers.has("content-type")) {
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

function isFormDataBody(body: BodyInit): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}
