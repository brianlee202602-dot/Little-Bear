<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiRequestError,
  type ApiErrorPayload,
  type AdminDepartmentData,
  type AdminDepartmentListItemData,
  type AdminDepartmentOptionData,
  type AdminDocumentData,
  type AdminDocumentListItemData,
  type AdminFolderData,
  type AdminFolderOptionData,
  type AdminKnowledgeBaseData,
  type AdminKnowledgeBaseListItemData,
  type AdminKnowledgeBaseOptionData,
  type AdminAssignableRoleOptionData,
  type AdminRoleBindingData,
  type AdminRoleData,
  type ChunkData,
  type CurrentUserDepartment,
  type AdminUserData,
  type AdminUserListItemData,
  createAdminDocumentIndexJob,
  createAdminIndexJob,
  createAdminIndexCollectionRebuildJob,
  createAdminIndexCollectionSnapshot,
  createAdminIndexVersionCleanupJob,
  createConfigVersion,
  createAdminFolder,
  createAdminKnowledgeBase,
  createAdminDepartment,
  createAdminUser,
  createSession,
  createAdminUserRoleBindings,
  archiveConfigVersion,
  deleteAdminFolder,
  deleteAdminKnowledgeBase,
  deleteAdminDepartment,
  deleteAdminUser,
  deleteCurrentSession,
  getAdminCurrentUserCapabilities,
  getAdminDocument,
  getAdminUser,
  getAdminKnowledgeBase,
  getAdminIndexHealth,
  getConfigVersion,
  getModelCallLog,
  getQueryLog,
  getAdminDepartment,
  getSetupState,
  initializeSetup,
  listAdminDocumentChunks,
  listAdminDocumentIndexVersions,
  listAdminIndexCollectionSnapshots,
  listAdminDocuments,
  listAdminDocumentVersions,
  listAdminFolderOptions,
  listAdminFolders,
  listAdminImportJobs,
  listAdminAssignableRoleOptions,
  listAdminDepartmentOptions,
  listAdminDepartments,
  listAdminKnowledgeBaseOptions,
  listAdminKnowledgeBases,
  listAdminUserDepartments,
  listAdminUserRoleBindings,
  listAdminUsers,
  listAuditLogs,
  listModelCallLogs,
  listQueryLogs,
  listConfigVersions,
  patchAdminFolder,
  patchAdminKnowledgeBase,
  patchAdminDepartment,
  patchAdminUser,
  putDocumentPermissions,
  putKnowledgeBasePermissions,
  publishConfigVersion,
  refreshSession,
  recoverAdminIndexCollectionSnapshot,
  replaceAdminUserDepartments,
  resetAdminUserPassword,
  retryAdminIndexJobs,
  revokeAdminUserRoleBinding,
  unlockAdminUser,
  updateConfigVersion,
  uploadKnowledgeBaseDocuments,
  validateAdminConfig,
  validateSetupConfig,
  type AuditLogListItemData,
  type AdminCurrentUserCapabilitiesData,
  type ConfigItemData,
  type ConfigVersionData,
  type ConfigVersionListItemData,
  type DocumentVersionData,
  type IndexCollectionHealthData,
  type IndexCollectionSnapshotData,
  type IndexVersionData,
  type ImportJobData,
  type ImportJobListItemData,
  type ImportJobStage,
  type ImportJobStatus,
  type KnowledgeBaseAccessRuleData,
  type ModelCallLogData,
  type ModelCallLogListItemData,
  type PaginationData,
  type QueryLogData,
  type QueryLogListItemData,
  type SetupInitializationData,
  type SetupIssue,
  type SetupStateData,
  type SetupValidationData,
  type TokenResponse,
} from "@/api/client";
import {
  buildSetupPayload,
  createDefaultSetupForm,
  type SetupFormModel,
} from "@/setup/defaults";

type StringFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends string ? K : never;
}[keyof SetupFormModel];
type NumberFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends number ? K : never;
}[keyof SetupFormModel];
type BooleanFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends boolean ? K : never;
}[keyof SetupFormModel];

type FieldInput = "text" | "email" | "password" | "number" | "select" | "checkbox";

type FieldOption = {
  label: string;
  value: string;
};

type Tone = "success" | "error" | "warning" | "neutral";
type LocalIssueTone = "error" | "warning";
type ActiveView = "loading" | "setup" | "login" | "dashboard";
type ActiveAdminTab = "config" | "departments" | "users" | "knowledge" | "diagnostics";
type ConfigModalMode = "create" | "edit" | null;
type DepartmentModalMode = "create" | "edit" | "delete" | null;
type KnowledgeBaseModalMode =
  | "create"
  | "edit"
  | "delete"
  | "upload"
  | "permissions"
  | "rebuildIndex"
  | null;
type FolderModalMode = "create" | "edit" | "delete" | null;
type DocumentModalMode = "permissions" | "details" | null;
type UserModalMode = "create" | "edit" | "departments" | "roles" | "password" | "delete" | null;
type RoleScopeType = AdminRoleData["scope_type"];
type RoleBindingCandidate = {
  role: AdminAssignableRoleOptionData;
  scopeType: RoleScopeType;
  scopeId: string | null;
};
type AdminTabDefinition = {
  key: ActiveAdminTab;
  label: string;
};
type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type LocalValidationIssue = {
  field?: keyof SetupFormModel;
  section: string;
  tone: LocalIssueTone;
  message: string;
};

type BootstrapCheckIssue = {
  name: string;
  status: string;
  message: string;
  required: boolean;
  latency_ms?: number;
};

type DatabaseErrorIssue = {
  type?: string;
  driver_type?: string;
  message?: string;
  sqlstate?: string;
  constraint?: string;
  table?: string;
  column?: string;
};

type FieldDefinition = {
  key: keyof SetupFormModel;
  label: string;
  input: FieldInput;
  placeholder?: string;
  hint?: string;
  min?: number;
  step?: number;
  span?: "full" | "half";
  group?: string;
  options?: FieldOption[];
  required?: boolean;
};

type FieldSection = {
  title: string;
  fields: FieldDefinition[];
};

type ConfigSectionFormDefinition = {
  key: string;
  label: string;
  description: string;
  fields: FieldDefinition[];
};

type AuthTokenState = {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
};

const AUTH_STORAGE_KEY = "little-bear.admin.auth";
const TOKEN_REFRESH_SKEW_MS = 60_000;

// 页面状态只保存在前端内存中；初始化成功后的可信状态以后端 active_config 为准。
const form = reactive<SetupFormModel>(createDefaultSetupForm());

const busy = reactive({
  refreshing: false,
  validating: false,
  submitting: false,
});
const authBusy = reactive({
  bootstrapping: true,
  loggingIn: false,
  refreshing: false,
  loggingOut: false,
});
const configBusy = reactive({
  loading: false,
  validating: false,
  saving: false,
  publishing: false,
  deleting: false,
});
const userAdminBusy = reactive({
  loading: false,
  creating: false,
  updating: false,
  updatingDepartments: false,
  resettingPassword: false,
  updatingRoles: false,
});
const departmentAdminBusy = reactive({
  loading: false,
  creating: false,
  updating: false,
  deleting: false,
});
const importAdminBusy = reactive({
  loading: false,
  loadingFolders: false,
  loadingDocuments: false,
  loadingDocumentDetails: false,
  loadingDocumentVersions: false,
  creating: false,
  updating: false,
  deleting: false,
  managingFolder: false,
  uploading: false,
  updatingPermissions: false,
  loadingIndexVersions: false,
  rebuildingIndex: false,
  rebuildingBatchIndex: false,
  cleaningIndexVersions: false,
  loadingFailedIndexJobs: false,
  retryingIndexJobs: false,
});
const diagnosticsBusy = reactive({
  loadingQueryLogs: false,
  loadingModelCallLogs: false,
  loadingQueryDetail: false,
  loadingModelCallDetail: false,
  loadingIndexHealth: false,
  loadingIndexSnapshots: false,
  creatingIndexSnapshot: false,
  recoveringIndexSnapshot: false,
  rebuildingIndexCollection: false,
});
const loginForm = reactive({
  username: "",
  password: "",
});
const userSearchForm = reactive({
  keyword: "",
  status: "",
});
const departmentSearchForm = reactive({
  keyword: "",
  status: "",
});
const knowledgeBaseSearchForm = reactive({
  keyword: "",
  status: "",
});
const importSearchForm = reactive({
  kbId: "",
  jobType: "",
  status: "",
  stage: "",
});
const queryLogSearchForm = reactive({
  userId: "",
  kbId: "",
  status: "",
  degraded: "",
  degradeReason: "",
  requestId: "",
  traceId: "",
  errorCode: "",
});
const modelCallSearchForm = reactive({
  model: "",
  modelType: "",
  caller: "",
  status: "",
  degraded: "",
  requestId: "",
  traceId: "",
  errorCode: "",
});
const documentSearchForm = reactive({
  status: "",
});
const optionSearchForm = reactive({
  departmentKeyword: "",
  roleKeyword: "",
  knowledgeBaseKeyword: "",
  folderKeyword: "",
});
const pageSizeOptions = [10, 20, 50, 100, 200];
const selectorPageSize = 20;
const configVersionPagination = reactive<PaginationState>({ page: 1, pageSize: 10, total: 0 });
const departmentPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const userPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const selectedUserDepartmentPagination = reactive<PaginationState>({ page: 1, pageSize: 10, total: 0 });
const selectedUserRoleBindingPagination = reactive<PaginationState>({ page: 1, pageSize: 10, total: 0 });
const knowledgeBasePagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const folderPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const importJobPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const failedIndexJobPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const queryLogPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const modelCallLogPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const auditLogPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const indexHealthPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const indexSnapshotPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const documentPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const documentVersionPagination = reactive<PaginationState>({ page: 1, pageSize: 10, total: 0 });
const documentIndexVersionPagination = reactive<PaginationState>({ page: 1, pageSize: 10, total: 0 });
const documentChunkPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });
const importUploadForm = reactive({
  kbId: "",
  folderId: "",
  visibility: "department" as "department" | "enterprise",
  idempotencyKey: "",
});
const userCreateForm = reactive({
  username: "",
  name: "",
  initialPassword: "",
  passwordConfirm: "",
  departmentIds: [] as string[],
  roleIds: [] as string[],
  confirmedHighRisk: false,
});
const departmentCreateForm = reactive({
  code: "",
  name: "",
});
const departmentEditForm = reactive({
  name: "",
  status: "active" as "active" | "disabled",
});
const knowledgeBaseCreateForm = reactive({
  name: "",
  ownerDepartmentId: "",
  kbVisibility: "enterprise" as "enterprise" | "department_acl" | "private",
  defaultDocumentVisibility: "department" as "department" | "enterprise",
  defaultDocumentOwnerDepartmentId: "",
  accessDepartmentIds: [] as string[],
  configScopeId: "",
  confirmedEnterpriseVisibility: false,
});
const knowledgeBaseEditForm = reactive({
  name: "",
  status: "active" as "active" | "disabled" | "archived",
  kbVisibility: "enterprise" as "enterprise" | "department_acl" | "private",
  defaultDocumentVisibility: "department" as "department" | "enterprise",
  defaultDocumentOwnerDepartmentId: "",
  configScopeId: "",
  confirmedVisibilityExpand: false,
});
const knowledgeBasePermissionForm = reactive({
  kbVisibility: "enterprise" as "enterprise" | "department_acl" | "private",
  defaultDocumentVisibility: "department" as "department" | "enterprise",
  defaultDocumentOwnerDepartmentId: "",
  accessDepartmentIds: [] as string[],
  confirmedReplace: false,
});
const knowledgeBaseIndexForm = reactive({
  confirmedRebuild: false,
});
const folderCreateForm = reactive({
  name: "",
  parentId: "",
});
const folderEditForm = reactive({
  name: "",
  parentId: "",
  status: "active" as "active" | "disabled" | "archived",
});
const documentPermissionForm = reactive({
  visibility: "department" as "department" | "enterprise",
  ownerDepartmentId: "",
  confirmedReplace: false,
});
const documentIndexForm = reactive({
  confirmedRebuild: false,
  confirmedBatchRebuild: false,
  confirmedCleanup: false,
});
const indexRetryForm = reactive({
  confirmedRetry: false,
});
const indexCollectionOpsForm = reactive({
  selectedCollectionName: "",
  snapshotLocation: "",
  snapshotChecksum: "",
  recoverPriority: "Snapshot" as "Snapshot" | "Replica",
  confirmedSnapshot: false,
  confirmedRestore: false,
  confirmedRebuild: false,
});
const userEditForm = reactive({
  name: "",
  status: "active" as "active" | "disabled" | "locked",
  confirmedDisableAdmin: false,
});
const departmentDangerForm = reactive({
  confirmedDelete: false,
});
const knowledgeBaseDangerForm = reactive({
  confirmedDelete: false,
});
const folderDangerForm = reactive({
  confirmedDelete: false,
});
const userDangerForm = reactive({
  confirmedDelete: false,
});
const passwordResetForm = reactive({
  newPassword: "",
  passwordConfirm: "",
  forceChangePassword: true,
  confirmed: false,
});
const configForm = reactive<SetupFormModel>(createDefaultSetupForm());
const userDepartmentForm = reactive({
  departmentIds: [] as string[],
  confirmedReplacePrimary: false,
});
const roleBindingForm = reactive({
  roleId: "",
  scopeId: "",
  confirmedHighRisk: false,
  confirmedRemoveAdmin: false,
});

const setupState = ref<SetupStateData | null>(null);
const validationResult = ref<SetupValidationData | null>(null);
const initializationResult = ref<SetupInitializationData | null>(null);
const feedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const authFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const configFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const auditFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const diagnosticsFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(
  null,
);
const userAdminFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const departmentAdminFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(
  null,
);
const importAdminFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const validationErrorPayload = ref<ApiErrorPayload | null>(null);
const initializationErrorPayload = ref<ApiErrorPayload | null>(null);
const submitConfirmed = ref(false);
const lastValidatedPayload = ref<string | null>(null);
const authTokens = ref<AuthTokenState | null>(loadStoredAuthTokens());
const currentUser = ref<AdminCurrentUserCapabilitiesData | null>(null);
const adminAccessGranted = ref(false);
const configItems = ref<ConfigItemData[]>([]);
const configVersions = ref<ConfigVersionListItemData[]>([]);
const configVersionDetails = ref<Record<number, ConfigVersionData>>({});
const auditLogs = ref<AuditLogListItemData[]>([]);
const queryLogs = ref<QueryLogListItemData[]>([]);
const modelCallLogs = ref<ModelCallLogListItemData[]>([]);
const indexHealth = ref<IndexCollectionHealthData[]>([]);
const indexCollectionSnapshots = ref<IndexCollectionSnapshotData[]>([]);
const selectedQueryLog = ref<QueryLogData | null>(null);
const selectedModelCallLog = ref<ModelCallLogData | null>(null);
const selectedConfigKey = ref<string>("");
const selectedConfigVersionNumber = ref<number | null>(null);
const queryLogDetailModalOpen = ref(false);
const modelCallLogDetailModalOpen = ref(false);
const configEditorText = ref("");
const configJsonText = ref("");
const configValidationResult = ref<SetupValidationData | null>(null);
const selectedDraftVersion = ref<number | null>(null);
const lastConfigValidatedText = ref<string | null>(null);
const selectedAdminTab = ref<ActiveAdminTab>("config");
const configModalMode = ref<ConfigModalMode>(null);
const adminUsers = ref<AdminUserListItemData[]>([]);
const selectedAdminUserDetail = ref<AdminUserData | null>(null);
const adminDepartments = ref<AdminDepartmentListItemData[]>([]);
const adminDepartmentOptions = ref<AdminDepartmentOptionData[]>([]);
const adminKnowledgeBases = ref<AdminKnowledgeBaseListItemData[]>([]);
const adminKnowledgeBaseOptions = ref<AdminKnowledgeBaseOptionData[]>([]);
const selectedKnowledgeBaseDetail = ref<AdminKnowledgeBaseData | null>(null);
const adminFolders = ref<AdminFolderData[]>([]);
const adminFolderOptions = ref<AdminFolderOptionData[]>([]);
const adminDocuments = ref<AdminDocumentListItemData[]>([]);
const selectedAdminDocumentDetail = ref<AdminDocumentData | null>(null);
const selectedDocumentVersions = ref<DocumentVersionData[]>([]);
const selectedDocumentIndexVersions = ref<IndexVersionData[]>([]);
const selectedDocumentChunks = ref<ChunkData[]>([]);
const highlightedDocumentChunkId = ref("");
const adminRoles = ref<AdminAssignableRoleOptionData[]>([]);
const adminImportJobs = ref<ImportJobListItemData[]>([]);
const failedIndexJobs = ref<ImportJobListItemData[]>([]);
const selectedFailedIndexJobIds = ref<string[]>([]);
const selectedBatchDocumentIds = ref<string[]>([]);
const selectedCleanupIndexVersionIds = ref<string[]>([]);
const selectedImportFiles = ref<File[]>([]);
const importFileInputKey = ref(0);
const selectedDepartmentId = ref<string>("");
const selectedKnowledgeBaseId = ref<string>("");
const selectedFolderId = ref<string>("");
const selectedDocumentId = ref<string>("");
const selectedAdminUserId = ref<string>("");
const selectedUserDepartments = ref<AdminDepartmentData[]>([]);
const selectedUserRoleBindings = ref<AdminRoleBindingData[]>([]);
const departmentModalMode = ref<DepartmentModalMode>(null);
const knowledgeBaseModalMode = ref<KnowledgeBaseModalMode>(null);
const documentManagerModalOpen = ref(false);
const folderModalMode = ref<FolderModalMode>(null);
const documentModalMode = ref<DocumentModalMode>(null);
const userModalMode = ref<UserModalMode>(null);

const statusLabels: Record<string, string> = {
  not_initialized: "未初始化",
  setup_required: "等待初始化",
  validating_config: "校验中",
  testing_dependencies: "依赖测试中",
  creating_admin: "创建管理员中",
  publishing_config: "发布配置中",
  initialized: "已初始化",
  validation_failed: "校验失败",
  dependency_test_failed: "依赖测试失败",
  initialization_failed: "初始化失败",
  recovery_required: "需要恢复初始化",
  recovery_validating_config: "恢复校验中",
  recovery_publishing_config: "恢复发布中",
};
const builtinRoleLabels: Record<string, string> = {
  system_admin: "系统管理员",
  security_admin: "安全管理员",
  audit_admin: "审计管理员",
  department_admin: "部门管理员",
  knowledge_base_admin: "知识库管理员",
  employee: "普通员工",
};

// 以下 FieldSection 是“表单元数据”：模板按定义渲染字段，减少重复 DOM 和字段遗漏。
const accessSection: FieldSection = {
  title: "访问凭证",
  fields: [
    {
      key: "setupToken",
      label: "初始化令牌",
      input: "password",
      placeholder: "从后端启动日志复制初始化令牌（JWT）",
      hint: "用于调用初始化校验与初始化提交接口；请使用后端启动日志输出的 setup JWT。",
      span: "full",
      required: true,
    },
  ],
};

const adminSection: FieldSection = {
  title: "首个管理员",
  fields: [
    { key: "adminUsername", label: "登录名", input: "text", hint: "首个系统管理员的唯一登录标识。", required: true },
    { key: "adminDisplayName", label: "显示名", input: "text", hint: "用于管理后台展示、操作记录归属和审计事件摘要。", required: true },
    { key: "adminPassword", label: "初始密码", input: "password", placeholder: "************", hint: "用于创建首个管理员登录凭据；必须满足当前密码策略。", required: true },
    { key: "adminPasswordConfirm", label: "确认密码", input: "password", placeholder: "************", hint: "用于确认初始密码输入无误；两次输入必须完全一致。", required: true },
    { key: "adminEmail", label: "邮箱", input: "email" },
    { key: "adminPhone", label: "手机号", input: "text" },
  ],
};

const organizationSection: FieldSection = {
  title: "组织初始化",
  fields: [
    { key: "enterpriseName", label: "企业名称", input: "text", hint: "初始化流程将创建该企业作为系统的全局业务主体。", required: true },
    { key: "enterpriseCode", label: "企业编码", input: "text", hint: "企业的稳定内部标识；建议使用字母、数字、下划线或连字符。", required: true },
    { key: "departmentName", label: "默认部门名称", input: "text", hint: "初始化流程将创建该部门，并将首个管理员归属到此部门。", required: true },
    { key: "departmentCode", label: "默认部门编码", input: "text", hint: "部门的稳定内部标识；后续组织结构扩展将基于该编码体系。", required: true },
  ],
};

const infraSection: FieldSection = {
  title: "基础设施",
  fields: [
    {
      key: "secretProviderEndpoint",
      label: "密钥服务地址",
      input: "text",
      hint: "Secret Store 的 provider 标识或服务地址；使用 PostgreSQL secrets 表时填写 postgres://local-secrets。",
      span: "full",
      required: true,
    },
    {
      key: "redisUrl",
      label: "Redis 地址",
      input: "text",
      hint: "后端服务访问 Redis 的连接地址；同一 Docker 网络可使用 redis://redis:6379/0，跨主机访问请使用实际内网地址。",
      span: "full",
      required: true,
    },
    {
      key: "minioEndpoint",
      label: "MinIO 地址",
      input: "text",
      hint: "后端服务访问对象存储的 S3-compatible endpoint；同一 Docker 网络可使用 http://minio:9000。",
      required: true,
    },
    { key: "minioBucket", label: "存储桶名称", input: "text", hint: "用于保存导入文件、解析产物和索引相关对象；该 bucket 必须已存在且可读写。", required: true },
    { key: "minioRegion", label: "存储区域", input: "text", hint: "对象存储区域标识；本地环境可使用 local，生产环境应与存储服务配置一致。", required: true },
    { key: "objectKeyPrefix", label: "对象路径前缀", input: "text", hint: "用于隔离系统写入的对象路径；建议以斜杠结尾，例如 p0/。", required: true },
    {
      key: "minioAccessKeyRef",
      label: "MinIO 访问密钥引用",
      input: "text",
      hint: "填写 Secret Store 中的 access key 引用；不得填写 access key 明文。",
      span: "full",
      required: true,
    },
    {
      key: "minioSecretKeyRef",
      label: "MinIO 私有密钥引用",
      input: "text",
      hint: "填写 Secret Store 中的 secret key 引用；不得填写 secret key 明文。",
      span: "full",
      required: true,
    },
    {
      key: "qdrantBaseUrl",
      label: "Qdrant 地址",
      input: "text",
      hint: "后端服务访问向量数据库的 HTTP 地址；同一 Docker 网络可使用 http://qdrant:6333。",
      required: true,
    },
    {
      key: "qdrantApiKeyRef",
      label: "Qdrant API Key 引用",
      input: "text",
      hint: "可选。Qdrant 开启 API Key 鉴权时填写 Secret Store 引用，例如 secret://rag/qdrant/api-key；未开启鉴权时留空。",
      span: "full",
    },
    { key: "collectionPrefix", label: "向量集合前缀", input: "text", hint: "用于生成和识别 Qdrant collection；变更前需评估既有索引兼容性。", required: true },
    {
      key: "vectorDistance",
      label: "向量距离",
      input: "select",
      hint: "用于设置 Qdrant collection 的距离计算方式；应与 embedding 模型归一化策略保持一致。",
      required: true,
      options: [
        { label: "cosine", value: "cosine" },
        { label: "dot", value: "dot" },
        { label: "euclidean", value: "euclidean" },
      ],
    },
  ],
};

const modelSection: FieldSection = {
  title: "模型与检索",
  fields: [
    {
      key: "modelGatewayMode",
      label: "模型服务模式",
      input: "select",
      hint: "模型调用采用外部 provider 模式；系统通过下方 provider 地址访问 embedding、rerank 和 LLM 服务。",
      required: true,
      options: [{ label: "external", value: "external" }],
    },
    {
      key: "embeddingProviderBaseUrl",
      label: "向量模型服务地址",
      input: "text",
      hint: "Embedding provider 的基础 URL；同一 Docker 网络可使用 http://tei-embedding:80，生产环境应指向正式模型服务。",
      span: "full",
      required: true,
    },
    {
      key: "embeddingProviderApiKey",
      label: "向量模型访问密钥",
      input: "password",
      hint: "可选。需要鉴权时填写明文 API Key；仅用于本次初始化提交，后端会加密写入 Secret Store，active config 不保存明文。",
      span: "full",
    },
    {
      key: "rerankProviderBaseUrl",
      label: "重排模型服务地址",
      input: "text",
      hint: "Rerank provider 的基础 URL；同一 Docker 网络可使用 http://tei-rerank:80，生产环境应指向正式模型服务。",
      span: "full",
      required: true,
    },
    {
      key: "rerankProviderApiKey",
      label: "重排模型访问密钥",
      input: "password",
      hint: "可选。需要鉴权时填写明文 API Key；仅用于本次初始化提交，后端会加密写入 Secret Store，active config 不保存明文。",
      span: "full",
    },
    {
      key: "llmProviderBaseUrl",
      label: "大模型服务地址",
      input: "text",
      hint: "OpenAI-compatible LLM provider 的基础 URL；当前部署未内置 LLM 服务，必须填写可访问的正式地址。",
      span: "full",
      required: true,
    },
    {
      key: "llmProviderApiKey",
      label: "大模型访问密钥",
      input: "password",
      hint: "可选。需要鉴权时填写明文 API Key；仅用于本次初始化提交，后端会加密写入 Secret Store，active config 不保存明文。",
      span: "full",
    },
    { key: "embeddingDimension", label: "向量维度", input: "number", hint: "必须与 embedding 模型输出维度及 Qdrant collection 维度保持一致。", min: 1, step: 1, required: true },
    { key: "embeddingModel", label: "向量模型", input: "text", hint: "填写 embedding provider 暴露的模型名称；导入与查询应使用兼容模型。", required: true },
    { key: "rerankModel", label: "重排模型", input: "text", hint: "填写 rerank provider 暴露的模型名称，用于对召回候选进行二次排序。", required: true },
    { key: "llmModel", label: "主大模型", input: "text", hint: "填写 LLM provider 暴露的主模型名称，用于答案生成。", required: true },
    { key: "llmFallbackModel", label: "回退大模型", input: "text", hint: "主模型不可用时使用的备用模型；应与业务质量和成本策略一致。", required: true },
    { key: "keywordLanguage", label: "关键词语言", input: "text", hint: "关键词检索语言配置；中文全文检索默认使用 zh。", required: true },
    { key: "keywordAnalyzer", label: "分词器", input: "text", hint: "PostgreSQL 全文检索使用的分词器名称；中文环境默认使用 zhparser。", required: true },
    { key: "vectorTopK", label: "向量召回数量", input: "number", hint: "向量检索阶段返回的候选片段数量。", min: 1, step: 1 },
    { key: "keywordTopK", label: "关键词召回数量", input: "number", hint: "关键词检索阶段返回的候选片段数量。", min: 1, step: 1 },
    { key: "rerankInputTopK", label: "重排输入数量", input: "number", hint: "进入 rerank 阶段的候选片段数量，应结合模型延迟和召回质量设定。", min: 1, step: 1 },
    { key: "rerankMinScore", label: "重排最低分", input: "number", hint: "重排成功后低于该分数的片段不会进入答案上下文。", min: 0, step: 0.01 },
    { key: "finalContextTopK", label: "最终上下文数量", input: "number", hint: "进入答案生成上下文的最终片段数量。", min: 1, step: 1 },
    { key: "maxContextTokens", label: "最大上下文 Token 数", input: "number", min: 1, step: 1 },
  ],
};

const chunkSection: FieldSection = {
  title: "文档切片策略",
  fields: [
    {
      key: "chunkDefaultSizeTokens",
      label: "切片大小 Token 数",
      input: "number",
      hint: "单个 chunk 的目标 token 数；该配置影响后续导入、重建索引和召回粒度。",
      min: 1,
      step: 1,
      required: true,
    },
    {
      key: "chunkOverlapTokens",
      label: "切片重叠 Token 数",
      input: "number",
      hint: "相邻 chunk 之间保留的重叠 token 数；用于降低语义边界截断带来的召回损失。",
      min: 0,
      step: 1,
      required: true,
    },
    {
      key: "chunkStrategyMode",
      label: "切片策略",
      input: "select",
      hint: "heading_paragraph 优先按标题和段落边界切分；fixed_tokens 按固定 token 窗口切分。",
      required: true,
      options: [
        { label: "heading_paragraph", value: "heading_paragraph" },
        { label: "fixed_tokens", value: "fixed_tokens" },
      ],
    },
    {
      key: "chunkPreserveTables",
      label: "保留表格结构",
      input: "checkbox",
      hint: "启用后切片器应尽量避免拆散同一张表格，提升表格问答的引用完整性。",
      group: "chunk-preserve",
    },
    {
      key: "chunkPreserveCodeBlocks",
      label: "保留代码块结构",
      input: "checkbox",
      hint: "启用后切片器应尽量避免拆散同一个代码块，减少技术文档上下文破碎。",
      group: "chunk-preserve",
    },
    {
      key: "chunkPreserveContractClauses",
      label: "保留合同条款结构",
      input: "checkbox",
      hint: "启用后切片器应尽量保留条款编号和条款正文的完整性。",
      group: "chunk-preserve",
    },
  ],
};

const policySection: FieldSection = {
  title: "认证与运行策略",
  fields: [
    { key: "passwordMinLength", label: "密码最小长度", input: "number", hint: "用于约束本地账号密码强度；生产环境建议不低于 12 位。", min: 8, step: 1, required: true },
    {
      key: "accessTokenTtlMinutes",
      label: "访问令牌有效期（分钟）",
      input: "number",
      hint: "Access token 的有效期；较短有效期可降低令牌泄露后的暴露窗口。",
      min: 1,
      step: 1,
      required: true,
    },
    {
      key: "refreshTokenTtlMinutes",
      label: "刷新令牌有效期（分钟）",
      input: "number",
      hint: "Refresh token 的有效期；应结合组织安全策略和会话体验设定。",
      min: 1,
      step: 1,
      required: true,
    },
    { key: "jwtIssuer", label: "JWT 签发方", input: "text", hint: "用于声明访问令牌签发主体，并参与令牌校验。", required: true },
    { key: "jwtAudience", label: "JWT 受众", input: "text", hint: "用于声明访问令牌适用范围，并参与令牌校验。", required: true },
    { key: "jwtSigningKeyRef", label: "JWT 签名密钥引用", input: "text", hint: "填写 Secret Store 中的签名密钥引用；真实密钥不得写入 active config。", span: "full", required: true },
    { key: "maxFileMb", label: "文件大小上限 MB", input: "number", hint: "单个导入文件允许的最大体积。", min: 1, step: 1 },
    { key: "maxConcurrentJobs", label: "最大并发任务数", input: "number", hint: "系统级导入任务并发上限，用于保护模型服务和索引服务容量。", min: 1, step: 1 },
    { key: "embeddingBatchSize", label: "向量化批大小", input: "number", hint: "单次 embedding 请求处理的片段数量；应结合 provider 吞吐与延迟设定。", min: 1, step: 1 },
    { key: "indexBatchSize", label: "索引写入批大小", input: "number", hint: "单批写入向量索引和关键词索引的片段数量。", min: 1, step: 1 },
    { key: "queryQpsPerUser", label: "单用户查询 QPS", input: "number", hint: "单用户查询限流阈值，用于保护检索链路和模型服务。", min: 1, step: 1 },
    { key: "auditRetentionDays", label: "审计保留天数", input: "number", hint: "审计数据保留周期；应符合组织合规和数据治理要求。", min: 1, step: 1 },
    {
      key: "auditQueryTextMode",
      label: "查询文本记录方式",
      input: "select",
      hint: "控制审计记录中对查询文本的保存方式；生产环境应优先选择 hash 或 none。",
      options: [
        { label: "none", value: "none" },
        { label: "hash", value: "hash" },
        { label: "plain", value: "plain" },
      ],
    },
  ],
};

const cacheSection: FieldSection = {
  title: "缓存开关",
  fields: [
    { key: "queryEmbeddingEnabled", label: "查询向量缓存", input: "checkbox", hint: "启用后可复用相同查询的 embedding 结果，降低重复模型调用成本。", group: "cache-switch" },
    { key: "retrievalResultEnabled", label: "召回结果缓存", input: "checkbox", hint: "启用后缓存检索召回结果；缓存键必须包含权限、配置和索引版本信息。", group: "cache-switch" },
    { key: "finalAnswerEnabled", label: "最终答案缓存", input: "checkbox", hint: "启用后缓存最终答案；涉及权限变更和引用时效时需严格评估风险。", group: "cache-switch" },
    { key: "crossUserFinalAnswerAllowed", label: "允许跨用户最终答案缓存", input: "checkbox", hint: "高风险配置，可能导致不同用户之间复用答案；P0 阶段禁止开启。", group: "cache-switch" },
  ],
};

const advancedConfigSection: FieldSection = {
  title: "高级运行策略",
  fields: [
    { key: "llmTemperature", label: "LLM temperature", input: "number", hint: "控制答案生成随机性；越低越稳定，越高越发散。", min: 0, step: 0.01 },
    { key: "llmMaxTokens", label: "LLM 最大输出 Token", input: "number", hint: "单次答案生成允许输出的最大 token 数。", min: 1, step: 1 },
    { key: "llmFirstTokenTimeoutMs", label: "首 token 超时 ms", input: "number", hint: "模型首 token 等待预算；当前作为配置契约保存，流式链路可逐步接入。", min: 1, step: 1 },
    { key: "llmTotalTimeoutMs", label: "LLM 总超时 ms", input: "number", hint: "答案生成调用的整体超时预算。", min: 1, step: 1 },
    { key: "llmMaxRetries", label: "LLM 最大重试次数", input: "number", hint: "LLM provider 调用失败后的最大重试次数；0 表示不重试。", min: 0, step: 1 },
    { key: "llmRetryBackoffMs", label: "LLM 重试退避 ms", input: "number", hint: "LLM 重试之间的退避时间。", min: 0, step: 1 },
    { key: "llmEnableThinking", label: "启用 thinking 参数", input: "checkbox", hint: "写入 OpenAI-compatible extra body 的 chat_template_kwargs.enable_thinking。", group: "llm-switch" },
    {
      key: "permissionDefaultVisibility",
      label: "默认文档可见性",
      input: "select",
      hint: "新建或导入资源未显式指定权限时使用的默认可见性。",
      options: [
        { label: "部门可见", value: "department" },
        { label: "企业可见", value: "enterprise" },
      ],
    },
    { key: "permissionCacheTtlSeconds", label: "权限缓存 TTL 秒", input: "number", hint: "权限上下文缓存有效期。", min: 1, step: 1 },
    { key: "permissionWriteAccessBlockFirst", label: "收紧权限前先阻断写访问", input: "checkbox", hint: "权限收紧时优先阻断旧写入路径。", group: "permission-tightening" },
    { key: "permissionBlockOldIndexRefs", label: "阻断旧索引引用", input: "checkbox", hint: "权限收紧后阻断旧索引 payload 被继续引用。", group: "permission-tightening" },
    { key: "permissionFailClosed", label: "权限失败时关闭访问", input: "checkbox", hint: "权限计算异常时按拒绝访问处理。", group: "permission-tightening" },
    { key: "securityRequireCitation", label: "强制引用校验", input: "checkbox", hint: "答案必须通过引用来源校验，否则进入降级响应。", group: "security-switch" },
    { key: "securityBlockInternalPromptLeakage", label: "阻断内部提示词泄露", input: "checkbox", hint: "生成后处理阶段阻断内部提示词外泄。", group: "security-switch" },
    { key: "securityBlockSecretRefLeakage", label: "阻断 Secret 引用泄露", input: "checkbox", hint: "生成后处理阶段阻断 secret:// 引用外泄。", group: "security-switch" },
    { key: "securityPiiRedactionEnabled", label: "启用 PII 脱敏", input: "checkbox", hint: "对日志、审计摘要等可观测数据执行敏感信息脱敏。", group: "security-switch" },
    { key: "securityRedactLogs", label: "日志脱敏", input: "checkbox", hint: "写入普通日志前执行脱敏。", group: "security-switch" },
    { key: "securityRedactAuditSummary", label: "审计摘要脱敏", input: "checkbox", hint: "写入审计摘要前执行脱敏。", group: "security-switch" },
    { key: "timeoutQueryTotalMs", label: "查询总超时 ms", input: "number", hint: "一次问答请求的总预算。", min: 1, step: 1 },
    { key: "timeoutAuthPermissionMs", label: "鉴权权限超时 ms", input: "number", hint: "认证和权限上下文计算预算。", min: 1, step: 1 },
    { key: "timeoutRewriteMs", label: "改写超时 ms", input: "number", hint: "查询改写阶段预算。", min: 1, step: 1 },
    { key: "timeoutEmbeddingMs", label: "Embedding 超时 ms", input: "number", hint: "查询向量化调用预算。", min: 1, step: 1 },
    { key: "timeoutVectorSearchMs", label: "向量检索超时 ms", input: "number", hint: "向量库查询预算。", min: 1, step: 1 },
    { key: "timeoutKeywordSearchMs", label: "关键词检索超时 ms", input: "number", hint: "关键词检索预算。", min: 1, step: 1 },
    { key: "timeoutRerankMs", label: "Rerank 超时 ms", input: "number", hint: "重排模型调用预算。", min: 1, step: 1 },
    { key: "timeoutContextMs", label: "上下文构建超时 ms", input: "number", hint: "引用片段组装和裁剪预算。", min: 1, step: 1 },
    { key: "timeoutPostprocessMs", label: "后处理超时 ms", input: "number", hint: "答案清洗、引用校验等后处理预算。", min: 1, step: 1 },
    {
      key: "degradeRewriteTimeout",
      label: "改写超时降级",
      input: "select",
      hint: "查询改写超时时采用的降级动作。",
      options: [
        { label: "使用原始问题", value: "use_original_query" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeEmbeddingTimeout",
      label: "Embedding 超时降级",
      input: "select",
      hint: "查询向量化不可用时采用的降级动作。",
      options: [
        { label: "仅关键词检索", value: "keyword_only" },
        { label: "仅元数据检索", value: "metadata_only" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeVectorUnavailable",
      label: "向量不可用降级",
      input: "select",
      hint: "向量库不可用时采用的降级动作。",
      options: [
        { label: "关键词和元数据", value: "keyword_and_metadata" },
        { label: "仅关键词检索", value: "keyword_only" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeKeywordUnavailable",
      label: "关键词不可用降级",
      input: "select",
      hint: "关键词检索不可用时采用的降级动作。",
      options: [
        { label: "向量和元数据", value: "vector_and_metadata" },
        { label: "仅向量检索", value: "vector_only" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeRerankTimeout",
      label: "Rerank 超时降级",
      input: "select",
      hint: "重排不可用时采用的降级动作。",
      options: [
        { label: "使用融合分数", value: "fusion_score" },
        { label: "跳过重排", value: "skip_rerank" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeLlmTimeout",
      label: "LLM 超时降级",
      input: "select",
      hint: "答案生成不可用时采用的降级动作。",
      options: [
        { label: "返回检索结果与引用", value: "return_retrieval_with_citations" },
        { label: "返回无答案原因", value: "return_no_answer_with_reason" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeModelPoolOverloaded",
      label: "模型池过载降级",
      input: "select",
      hint: "模型服务过载时采用的降级动作。",
      options: [
        { label: "返回可重试降级响应", value: "return_retryable_degraded_response" },
        { label: "进入队列等待", value: "queue_request" },
        { label: "终止查询", value: "fail_query" },
      ],
    },
    {
      key: "degradeImportBacklog",
      label: "导入积压降级",
      input: "select",
      hint: "导入队列积压时采用的降级动作。",
      options: [
        { label: "放慢导入", value: "slow_down_import" },
        { label: "拒绝新导入", value: "reject_new_import" },
        { label: "仅入队等待", value: "queue_only" },
      ],
    },
    { key: "observabilityMetricsEnabled", label: "启用 Metrics", input: "checkbox", hint: "启用指标采集。", group: "observability-switch" },
    { key: "observabilityTraceEnabled", label: "启用 Trace", input: "checkbox", hint: "启用链路追踪。", group: "observability-switch" },
    { key: "alertActiveConfigLoadFailed", label: "配置加载失败阈值", input: "number", hint: "active config 加载失败告警阈值。", min: 0, step: 1 },
    { key: "alertPermissionViolationRate", label: "权限违规率阈值", input: "number", hint: "权限违规率告警阈值。", min: 0, step: 0.01 },
    { key: "alertDraftIndexExposureCount", label: "草稿索引暴露阈值", input: "number", hint: "草稿索引暴露次数告警阈值。", min: 0, step: 1 },
    { key: "alertImportFailureRate", label: "导入失败率阈值", input: "number", hint: "导入失败率告警阈值。", min: 0, step: 0.01 },
    { key: "alertWorkerQueueBacklog", label: "Worker 队列积压阈值", input: "number", hint: "后台任务队列积压告警阈值。", min: 0, step: 1 },
    { key: "alertLlmTimeoutRate", label: "LLM 超时率阈值", input: "number", hint: "LLM 超时率告警阈值。", min: 0, step: 0.01 },
  ],
};

const sections = [
  accessSection,
  adminSection,
  organizationSection,
  infraSection,
  modelSection,
  chunkSection,
  policySection,
  cacheSection,
];

const allConfigFieldSections = [...sections, advancedConfigSection];

const setupFieldByKey = new Map<keyof SetupFormModel, FieldDefinition>(
  allConfigFieldSections.flatMap((section) => section.fields.map((field) => [field.key, field] as const)),
);

const configSectionDefinitions: ConfigSectionFormDefinition[] = [
  {
    key: "secret_provider",
    label: "密钥服务",
    description: "Secret Store provider、地址和 Secret 引用策略。",
    fields: setupFields("secretProviderEndpoint"),
  },
  {
    key: "redis",
    label: "Redis",
    description: "缓存、限流、锁和配置通知使用的 Redis 连接。",
    fields: setupFields("redisUrl"),
  },
  {
    key: "storage",
    label: "对象存储",
    description: "MinIO/S3-compatible 存储地址、bucket 和 Secret 引用。",
    fields: setupFields(
      "minioEndpoint",
      "minioBucket",
      "minioRegion",
      "objectKeyPrefix",
      "minioAccessKeyRef",
      "minioSecretKeyRef",
    ),
  },
  {
    key: "vector_store",
    label: "向量库",
    description: "Qdrant 地址、集合前缀、距离度量和可选 API Key 引用。",
    fields: setupFields("qdrantBaseUrl", "qdrantApiKeyRef", "collectionPrefix", "vectorDistance"),
  },
  {
    key: "keyword_search",
    label: "关键词检索",
    description: "全文检索语言、分词器和词典策略。",
    fields: setupFields("keywordLanguage", "keywordAnalyzer"),
  },
  {
    key: "model_gateway",
    label: "模型网关",
    description: "Embedding、Rerank 和 LLM provider 地址及模型路由。",
    fields: setupFields(
      "modelGatewayMode",
      "embeddingProviderBaseUrl",
      "rerankProviderBaseUrl",
      "llmProviderBaseUrl",
      "embeddingModel",
      "rerankModel",
      "llmModel",
      "llmFallbackModel",
    ),
  },
  {
    key: "model",
    label: "模型参数",
    description: "默认模型名称、向量维度和模型版本相关配置。",
    fields: setupFields("embeddingDimension", "embeddingModel", "rerankModel", "llmModel", "llmFallbackModel"),
  },
  {
    key: "auth",
    label: "认证策略",
    description: "密码策略、Token 有效期和 JWT 签名配置。",
    fields: setupFields(
      "passwordMinLength",
      "accessTokenTtlMinutes",
      "refreshTokenTtlMinutes",
      "jwtIssuer",
      "jwtAudience",
      "jwtSigningKeyRef",
    ),
  },
  {
    key: "retrieval",
    label: "检索策略",
    description: "向量/关键词召回、重排和最终上下文预算。",
    fields: setupFields("vectorTopK", "keywordTopK", "rerankInputTopK", "rerankMinScore", "finalContextTopK", "maxContextTokens"),
  },
  {
    key: "chunk",
    label: "文档切片",
    description: "切片大小、重叠长度和结构保留策略。",
    fields: setupFields(
      "chunkDefaultSizeTokens",
      "chunkOverlapTokens",
      "chunkStrategyMode",
      "chunkPreserveTables",
      "chunkPreserveCodeBlocks",
      "chunkPreserveContractClauses",
    ),
  },
  {
    key: "import",
    label: "导入任务",
    description: "文件大小、并发任务和索引批处理参数。",
    fields: setupFields("maxFileMb", "maxConcurrentJobs", "embeddingBatchSize", "indexBatchSize"),
  },
  {
    key: "cache",
    label: "缓存策略",
    description: "查询向量、召回结果和最终答案缓存开关。",
    fields: setupFields(
      "queryEmbeddingEnabled",
      "retrievalResultEnabled",
      "finalAnswerEnabled",
      "crossUserFinalAnswerAllowed",
    ),
  },
  {
    key: "rate_limit",
    label: "限流策略",
    description: "用户、部门、知识库和模型池限流配置。",
    fields: setupFields("queryQpsPerUser"),
  },
  {
    key: "audit",
    label: "审计策略",
    description: "审计保留周期、查询文本记录方式和脱敏策略。",
    fields: setupFields("auditRetentionDays", "auditQueryTextMode"),
  },
  {
    key: "llm",
    label: "LLM 运行参数",
    description: "temperature、输出 token、超时和重试策略。",
    fields: setupFields(
      "llmTemperature",
      "llmMaxTokens",
      "llmFirstTokenTimeoutMs",
      "llmTotalTimeoutMs",
      "llmMaxRetries",
      "llmRetryBackoffMs",
      "llmEnableThinking",
    ),
  },
  {
    key: "permission",
    label: "权限策略",
    description: "默认角色、默认可见性和权限收紧阻断策略。",
    fields: setupFields(
      "permissionDefaultVisibility",
      "permissionCacheTtlSeconds",
      "permissionWriteAccessBlockFirst",
      "permissionBlockOldIndexRefs",
      "permissionFailClosed",
    ),
  },
  {
    key: "security",
    label: "安全策略",
    description: "引用强制、Prompt 泄露防护和 PII 脱敏策略。",
    fields: setupFields(
      "securityRequireCitation",
      "securityBlockInternalPromptLeakage",
      "securityBlockSecretRefLeakage",
      "securityPiiRedactionEnabled",
      "securityRedactLogs",
      "securityRedactAuditSummary",
    ),
  },
  {
    key: "timeout",
    label: "超时预算",
    description: "查询链路各阶段的超时预算。",
    fields: setupFields(
      "timeoutQueryTotalMs",
      "timeoutAuthPermissionMs",
      "timeoutRewriteMs",
      "timeoutEmbeddingMs",
      "timeoutVectorSearchMs",
      "timeoutKeywordSearchMs",
      "timeoutRerankMs",
      "timeoutContextMs",
      "timeoutPostprocessMs",
    ),
  },
  {
    key: "degrade",
    label: "降级策略",
    description: "模型、检索、导入等链路异常时的降级动作。",
    fields: setupFields(
      "degradeRewriteTimeout",
      "degradeEmbeddingTimeout",
      "degradeVectorUnavailable",
      "degradeKeywordUnavailable",
      "degradeRerankTimeout",
      "degradeLlmTimeout",
      "degradeModelPoolOverloaded",
      "degradeImportBacklog",
    ),
  },
  {
    key: "observability",
    label: "可观测性",
    description: "指标、Trace 和关键告警阈值。",
    fields: setupFields(
      "observabilityMetricsEnabled",
      "observabilityTraceEnabled",
      "alertActiveConfigLoadFailed",
      "alertPermissionViolationRate",
      "alertDraftIndexExposureCount",
      "alertImportFailureRate",
      "alertWorkerQueueBacklog",
      "alertLlmTimeoutRate",
    ),
  },
];

// payload 是真正提交给 setup-config-validations / setup-initialization 的请求体。
const payload = computed(() => buildSetupPayload(form));
const payloadSignature = computed(() => JSON.stringify(payload.value));
// 本地校验用于拦截明显输入错误；后端校验仍是最终准入标准。
const localValidationIssues = computed(() => validateLocalForm(form, setupState.value));
const localBlockingIssues = computed(() =>
  localValidationIssues.value.filter((issue) => issue.tone === "error"),
);
const localWarningIssues = computed(() =>
  localValidationIssues.value.filter((issue) => issue.tone === "warning"),
);
const localChecksPassed = computed(() => localBlockingIssues.value.length === 0);
const backendValidationFresh = computed(
  () => validationResult.value?.valid === true && lastValidatedPayload.value === payloadSignature.value,
);
// 正常初始化完成后写接口应关闭；只有后端显式允许 recovery 时才重新开放。
const setupWritable = computed(
  () => !(setupState.value?.initialized ?? false) || setupState.value?.recovery_setup_allowed === true,
);
const setupModeRequired = computed(() => {
  if (!setupState.value) {
    return false;
  }
  return setupState.value.initialized !== true || setupState.value.recovery_setup_allowed === true;
});
const authenticated = computed(() => Boolean(authTokens.value?.accessToken && currentUser.value));
const activeView = computed<ActiveView>(() => {
  if (authBusy.bootstrapping || !setupState.value) {
    return "loading";
  }
  if (setupModeRequired.value) {
    return "setup";
  }
  if (!authenticated.value) {
    return "login";
  }
  if (!adminAccessGranted.value) {
    return "login";
  }
  return "dashboard";
});
const userDisplayName = computed(() => currentUser.value?.name || currentUser.value?.username || "-");
const userRoleLabels = computed(() => formatRoleList(currentUser.value?.roles ?? []));
const canManageConfig = computed(() => hasScope(currentUser.value?.scopes ?? [], "config:manage"));
const canReadConfig = computed(() => hasScope(currentUser.value?.scopes ?? [], "config:read"));
const canReadAudit = computed(() => hasScope(currentUser.value?.scopes ?? [], "audit:read"));
const canLoadDiagnostics = computed(() => canReadAudit.value);
const canReadUsers = computed(
  () => hasScope(currentUser.value?.scopes ?? [], "user:read") || canManageUsers.value,
);
const canManageUsers = computed(() => hasScope(currentUser.value?.scopes ?? [], "user:manage"));
const canReadDepartments = computed(
  () => hasScope(currentUser.value?.scopes ?? [], "org:read") || canManageDepartments.value,
);
const canManageDepartments = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "org:manage"),
);
const canReadRoles = computed(
  () => hasScope(currentUser.value?.scopes ?? [], "role:read") || canManageRoles.value,
);
const canManageRoles = computed(() => hasScope(currentUser.value?.scopes ?? [], "role:manage"));
const canManageKnowledgeBases = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "knowledge_base:manage"),
);
const canManageDocuments = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "document:manage"),
);
const canIndexDocuments = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "document:index"),
);
const canLoadIndexOps = computed(() => canIndexDocuments.value);
const canManageFolders = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "folder:manage"),
);
const canImportDocuments = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "document:import"),
);
const canManagePermissions = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "permission:manage"),
);
const canReadImportJobs = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "import_job:read"),
);
const canLoadImportAdmin = computed(
  () =>
    canImportDocuments.value ||
    canReadImportJobs.value ||
    canManageKnowledgeBases.value ||
    canManageFolders.value ||
    canManageDocuments.value ||
    canIndexDocuments.value ||
    canManagePermissions.value,
);
const selectedConfigItem = computed(() =>
  configItems.value.find(
    (item) =>
      item.key === selectedConfigKey.value &&
      (selectedDraftVersion.value ? item.version === selectedDraftVersion.value : item.status === "active"),
  ) ??
  configItems.value.find((item) => item.key === selectedConfigKey.value) ??
  null,
);
const activeConfigItems = computed(() => configItems.value.filter((item) => item.status === "active"));
const configDraftItems = computed(() =>
  configVersions.value.filter((item) => item.status !== "active" && item.status !== "archived"),
);
const paginatedConfigVersions = computed(() => configVersions.value);
const activeConfigVersionRecord = computed(
  () => configVersionDetails.value[activeConfigVersion.value] ?? null,
);
const selectedConfigVersionRecord = computed(() =>
  selectedConfigVersionNumber.value === null
    ? null
    : (configVersionDetails.value[selectedConfigVersionNumber.value] ??
      configVersions.value.find((version) => version.version === selectedConfigVersionNumber.value) ??
      null),
);
const editableConfigDefinitions = computed(() =>
  configSectionDefinitions,
);
const selectedConfigDefinition = computed(() => configDefinitionForKey(selectedConfigKey.value));
const selectedConfigFields = computed(() => selectedConfigDefinition.value?.fields ?? []);
const selectedConfigUsesJsonEditor = computed(
  () => Boolean(selectedConfigDefinition.value) && selectedConfigFields.value.length === 0,
);
const selectedAdminUser = computed(
  () =>
    selectedAdminUserDetail.value?.id === selectedAdminUserId.value
      ? selectedAdminUserDetail.value
      : null,
);
type DepartmentSelectorItem = AdminDepartmentOptionData | CurrentUserDepartment | AdminDepartmentData;
type KnowledgeBaseSelectorItem =
  | AdminKnowledgeBaseOptionData
  | AdminKnowledgeBaseListItemData
  | AdminKnowledgeBaseData;

const selectedDepartment = computed(
  () => adminDepartments.value.find((department) => department.id === selectedDepartmentId.value) ?? null,
);
const selectedKnowledgeBase = computed(
  () =>
    selectedKnowledgeBaseDetail.value?.id === selectedKnowledgeBaseId.value
      ? selectedKnowledgeBaseDetail.value
      : (adminKnowledgeBases.value.find(
          (knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId.value,
        ) ?? null),
);
const selectedFolder = computed(
  () => adminFolders.value.find((folder) => folder.id === selectedFolderId.value) ?? null,
);
const selectedAdminDocumentListItem = computed(
  () => adminDocuments.value.find((document) => document.id === selectedDocumentId.value) ?? null,
);
const selectedAdminDocument = computed(() =>
  selectedAdminDocumentDetail.value?.id === selectedDocumentId.value
    ? selectedAdminDocumentDetail.value
    : null,
);
const selectedDocumentForDisplay = computed(
  () => selectedAdminDocument.value ?? selectedAdminDocumentListItem.value,
);
const selectedDocumentParentKnowledgeBase = computed(() => {
  const document = selectedAdminDocument.value;
  if (!document) {
    return selectedKnowledgeBaseDetail.value?.id === selectedKnowledgeBaseId.value
      ? selectedKnowledgeBaseDetail.value
      : null;
  }
  return selectedKnowledgeBaseDetail.value?.id === document.kb_id
    ? selectedKnowledgeBaseDetail.value
    : null;
});
const documentPermissionParentConflict = computed(() => {
  const knowledgeBase = selectedDocumentParentKnowledgeBase.value;
  if (!knowledgeBase || documentPermissionForm.visibility === "enterprise") {
    return "";
  }
  const ownerDepartmentId = documentPermissionForm.ownerDepartmentId.trim();
  if (ownerDepartmentId && !departmentCanQueryKnowledgeBase(knowledgeBase, ownerDepartmentId)) {
    return `${formatDepartmentById(ownerDepartmentId)} 不能查询父知识库；请先在知识库权限中授予该部门查询权限。`;
  }
  return "";
});
const selectedUserDepartmentsForDisplay = computed(() => {
  if (selectedUserDepartments.value.length > 0) {
    return selectedUserDepartments.value;
  }
  return selectedAdminUser.value?.departments ?? [];
});
const selectedUserDepartmentsForForm = computed(
  () => selectedAdminUser.value?.departments ?? selectedUserDepartments.value,
);
const initialAssignableRoles = computed(() =>
  adminRoles.value.filter((role) => role.status === "active" && role.scope_type === "enterprise"),
);
const assignableRoles = computed(() => adminRoles.value.filter((role) => role.status === "active"));
const activeDepartments = computed(() =>
  adminDepartmentOptions.value.filter((department) => department.status === "active"),
);
const currentUserDepartmentIds = computed(
  () => new Set((currentUser.value?.departments ?? []).map((department) => department.id)),
);
const canSelectAnyDepartmentForUserCreate = computed(() =>
  hasScope(currentUser.value?.scopes ?? [], "org:manage"),
);
const createUserDepartmentOptions = computed<DepartmentSelectorItem[]>(() => {
  if (canSelectAnyDepartmentForUserCreate.value) {
    return activeDepartments.value;
  }
  const ownDepartments =
    currentUser.value?.departments
      .filter((department) => department.status === "active")
      .map((department) => ({ ...department, is_default: false })) ?? [];
  if (!activeDepartments.value.length) {
    return ownDepartments;
  }
  return activeDepartments.value.filter((department) =>
    currentUserDepartmentIds.value.has(department.id),
  );
});
const activeKnowledgeBases = computed(() =>
  adminKnowledgeBaseOptions.value.filter((knowledgeBase) => knowledgeBase.status === "active"),
);
const activeFolders = computed(() =>
  adminFolderOptions.value.filter((folder) => folder.status === "active"),
);
const folderParentOptions = computed(() =>
  activeFolders.value.filter((folder) => folder.id !== selectedFolderId.value),
);
const selectedImportKnowledgeBase = computed(
  () =>
    selectedKnowledgeBaseDetail.value?.id === importUploadForm.kbId
      ? selectedKnowledgeBaseDetail.value
      : (adminKnowledgeBases.value.find(
          (knowledgeBase) => knowledgeBase.id === importUploadForm.kbId,
        ) ?? null),
);
const importUploadPermissionParentConflict = computed(() => {
  const knowledgeBase =
    selectedKnowledgeBaseDetail.value?.id === importUploadForm.kbId
      ? selectedKnowledgeBaseDetail.value
      : null;
  if (!knowledgeBase || importUploadForm.visibility === "enterprise") {
    return "";
  }
  const ownerDepartmentId =
    knowledgeBase.default_document_owner_department_id ??
    knowledgeBase.owner_department_id ??
    "";
  if (ownerDepartmentId && !departmentCanQueryKnowledgeBase(knowledgeBase, ownerDepartmentId)) {
    return `${formatDepartmentById(ownerDepartmentId)} 不能查询目标知识库；请先在知识库权限中授予该部门查询权限。`;
  }
  return "";
});
const canUploadImportFiles = computed(
  () =>
    canImportDocuments.value &&
    importUploadForm.kbId.trim().length > 0 &&
    selectedImportFiles.value.length > 0 &&
    !importUploadPermissionParentConflict.value &&
    !importAdminBusy.uploading,
);
const canCreateKnowledgeBase = computed(
  () =>
    canManageKnowledgeBases.value &&
    knowledgeBaseCreateForm.name.trim().length > 0 &&
    knowledgeBaseCreateForm.ownerDepartmentId.trim().length > 0 &&
    knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId.trim().length > 0 &&
    (knowledgeBaseCreateForm.kbVisibility === "enterprise" ||
      knowledgeBaseCreateForm.accessDepartmentIds.length > 0) &&
    (knowledgeBaseCreateForm.kbVisibility !== "enterprise" ||
      knowledgeBaseCreateForm.confirmedEnterpriseVisibility) &&
    !importAdminBusy.creating,
);
const canUpdateSelectedKnowledgeBase = computed(
  () =>
    canManageKnowledgeBases.value &&
    Boolean(selectedKnowledgeBase.value) &&
    knowledgeBaseEditForm.name.trim().length > 0 &&
    knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId.trim().length > 0 &&
    !(
      selectedKnowledgeBase.value?.kb_visibility !== "enterprise" &&
      knowledgeBaseEditForm.kbVisibility === "enterprise" &&
      !knowledgeBaseEditForm.confirmedVisibilityExpand
    ) &&
    !importAdminBusy.updating,
);
const canDeleteSelectedKnowledgeBase = computed(
  () =>
    canManageKnowledgeBases.value &&
    Boolean(selectedKnowledgeBase.value) &&
    knowledgeBaseDangerForm.confirmedDelete &&
    !importAdminBusy.deleting,
);
const canRebuildSelectedKnowledgeBaseIndex = computed(
  () =>
    canIndexDocuments.value &&
    selectedKnowledgeBase.value?.status === "active" &&
    knowledgeBaseIndexForm.confirmedRebuild &&
    !importAdminBusy.rebuildingIndex,
);
const canCreateFolder = computed(
  () =>
    canManageFolders.value &&
    Boolean(selectedKnowledgeBase.value) &&
    folderCreateForm.name.trim().length > 0 &&
    !importAdminBusy.managingFolder,
);
const canUpdateSelectedFolder = computed(
  () =>
    canManageFolders.value &&
    Boolean(selectedFolder.value) &&
    folderEditForm.name.trim().length > 0 &&
    !importAdminBusy.managingFolder,
);
const canDeleteSelectedFolder = computed(
  () =>
    canManageFolders.value &&
    Boolean(selectedFolder.value) &&
    folderDangerForm.confirmedDelete &&
    !importAdminBusy.managingFolder,
);
const canReplaceSelectedKnowledgeBasePermissions = computed(
  () =>
    canManagePermissions.value &&
    Boolean(selectedKnowledgeBase.value) &&
    knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId.trim().length > 0 &&
    (knowledgeBasePermissionForm.kbVisibility === "enterprise" ||
      knowledgeBasePermissionForm.accessDepartmentIds.length > 0) &&
    knowledgeBasePermissionForm.confirmedReplace &&
    !importAdminBusy.updatingPermissions,
);
const canReplaceSelectedDocumentPermissions = computed(
  () =>
    canManagePermissions.value &&
    Boolean(selectedAdminDocument.value) &&
    documentPermissionForm.ownerDepartmentId.trim().length > 0 &&
    !documentPermissionParentConflict.value &&
    documentPermissionForm.confirmedReplace &&
    !importAdminBusy.updatingPermissions,
);
const canRebuildSelectedDocumentIndex = computed(
  () =>
    canIndexDocuments.value &&
    selectedAdminDocument.value?.lifecycle_status === "active" &&
    Boolean(selectedAdminDocument.value?.current_version_id) &&
    documentIndexForm.confirmedRebuild &&
    !importAdminBusy.rebuildingIndex,
);
const batchRebuildEligibleDocuments = computed(() =>
  adminDocuments.value.filter((document) => isDocumentBatchRebuildEligible(document)),
);
const selectedBatchDocumentSet = computed(() => new Set(selectedBatchDocumentIds.value));
const selectedBatchRebuildDocumentIds = computed(() => {
  const eligibleIds = new Set(batchRebuildEligibleDocuments.value.map((document) => document.id));
  return selectedBatchDocumentIds.value.filter((documentId) => eligibleIds.has(documentId));
});
const allBatchRebuildEligibleDocumentsSelected = computed(
  () =>
    batchRebuildEligibleDocuments.value.length > 0 &&
    selectedBatchRebuildDocumentIds.value.length === batchRebuildEligibleDocuments.value.length,
);
const canRebuildSelectedDocumentsIndex = computed(
  () =>
    canIndexDocuments.value &&
    selectedBatchRebuildDocumentIds.value.length > 0 &&
    documentIndexForm.confirmedBatchRebuild &&
    !importAdminBusy.rebuildingBatchIndex,
);
const cleanupEligibleIndexVersions = computed(() =>
  selectedDocumentIndexVersions.value.filter((version) => version.status === "pending_delete"),
);
const selectedCleanupIndexVersionSet = computed(() => new Set(selectedCleanupIndexVersionIds.value));
const selectedCleanupPendingDeleteIndexVersionIds = computed(() => {
  const eligibleIds = new Set(cleanupEligibleIndexVersions.value.map((version) => version.id));
  return selectedCleanupIndexVersionIds.value.filter((indexVersionId) =>
    eligibleIds.has(indexVersionId),
  );
});
const allCleanupEligibleIndexVersionsSelected = computed(
  () =>
    cleanupEligibleIndexVersions.value.length > 0 &&
    selectedCleanupPendingDeleteIndexVersionIds.value.length ===
      cleanupEligibleIndexVersions.value.length,
);
const canCleanupSelectedIndexVersions = computed(
  () =>
    canIndexDocuments.value &&
    selectedCleanupPendingDeleteIndexVersionIds.value.length > 0 &&
    documentIndexForm.confirmedCleanup &&
    !importAdminBusy.cleaningIndexVersions,
);
const selectedFailedIndexJobSet = computed(() => new Set(selectedFailedIndexJobIds.value));
const failedIndexJobStageSummary = computed(() => {
  const counts = new Map<string, number>();
  for (const job of failedIndexJobs.value) {
    counts.set(job.stage, (counts.get(job.stage) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([leftStage], [rightStage]) => leftStage.localeCompare(rightStage))
    .map(([stage, count]) => `${importJobStageLabel(stage as ImportJobStage)} ${count}`);
});
const failedIndexJobDocumentCount = computed(
  () => failedIndexJobs.value.reduce((total, job) => total + job.document_count, 0),
);
const canRetrySelectedFailedIndexJobs = computed(
  () =>
    canIndexDocuments.value &&
    selectedFailedIndexJobIds.value.length > 0 &&
    indexRetryForm.confirmedRetry &&
    !importAdminBusy.retryingIndexJobs,
);
const selectedIndexCollectionHealth = computed(
  () =>
    indexHealth.value.find(
      (item) => item.collection_name === indexCollectionOpsForm.selectedCollectionName,
    ) ?? null,
);
const canCreateIndexCollectionSnapshot = computed(
  () =>
    canLoadIndexOps.value &&
    Boolean(selectedIndexCollectionHealth.value) &&
    indexCollectionOpsForm.confirmedSnapshot &&
    !diagnosticsBusy.creatingIndexSnapshot,
);
const canRecoverIndexCollectionSnapshot = computed(
  () =>
    canLoadIndexOps.value &&
    Boolean(selectedIndexCollectionHealth.value) &&
    indexCollectionOpsForm.snapshotLocation.trim().length > 0 &&
    indexCollectionOpsForm.confirmedRestore &&
    !diagnosticsBusy.recoveringIndexSnapshot,
);
const canRebuildIndexCollection = computed(
  () =>
    canLoadIndexOps.value &&
    Boolean(selectedIndexCollectionHealth.value) &&
    indexCollectionOpsForm.confirmedRebuild &&
    !diagnosticsBusy.rebuildingIndexCollection,
);
const roleBindingCandidates = computed<RoleBindingCandidate[]>(() =>
  assignableRoles.value.flatMap((role): RoleBindingCandidate[] => {
    if (role.scope_type === "enterprise") {
      return [{ role, scopeType: role.scope_type, scopeId: null }];
    }
    if (role.scope_type === "department") {
      return activeDepartments.value.map((department) => ({
        role,
        scopeType: role.scope_type,
        scopeId: department.id,
      }));
    }
    return activeKnowledgeBases.value.map((knowledgeBase) => ({
      role,
      scopeType: role.scope_type,
      scopeId: knowledgeBase.id,
    }));
  }),
);
const selectedUserRoleBindingKeys = computed(() =>
  new Set(selectedUserRoleBindings.value.map(roleBindingKey)),
);
const selectedUserDepartmentIds = computed(() => new Set(userDepartmentForm.departmentIds));
const currentSelectedUserPrimaryDepartmentId = computed(() => {
  const departments = selectedUserDepartmentsForForm.value;
  return departments.find((department) => department.is_primary)?.id ?? departments[0]?.id ?? "";
});
const nextSelectedUserPrimaryDepartmentId = computed(() => userDepartmentForm.departmentIds[0] ?? "");
const selectedUserPrimaryDepartmentWillChange = computed(
  () =>
    Boolean(currentSelectedUserPrimaryDepartmentId.value) &&
    Boolean(nextSelectedUserPrimaryDepartmentId.value) &&
    currentSelectedUserPrimaryDepartmentId.value !== nextSelectedUserPrimaryDepartmentId.value,
);
const selectedRoleForBinding = computed(
  () => adminRoles.value.find((role) => role.id === roleBindingForm.roleId) ?? null,
);
const selectedRoleBindingScopeType = computed(
  () => selectedRoleForBinding.value?.scope_type ?? "enterprise",
);
const selectedRoleBindingScopeReady = computed(() => {
  const role = selectedRoleForBinding.value;
  if (!role) {
    return false;
  }
  return role.scope_type === "enterprise" || Boolean(roleBindingForm.scopeId);
});
const selectedRoleBindingKey = computed(() => {
  const role = selectedRoleForBinding.value;
  if (!role) {
    return "";
  }
  return roleBindingKeyFromParts(
    role.id,
    role.scope_type,
    role.scope_type === "enterprise" ? null : roleBindingForm.scopeId,
  );
});
const availableRoleBindingCandidates = computed(() =>
  roleBindingCandidates.value.filter(
    (candidate) =>
      !selectedUserRoleBindingKeys.value.has(
        roleBindingKeyFromParts(candidate.role.id, candidate.scopeType, candidate.scopeId),
      ),
  ),
);
const selectedCreateRoles = computed(() =>
  adminRoles.value.filter((role) => userCreateForm.roleIds.includes(role.id)),
);
const selectedAdminUserIsSystemAdmin = computed(
  () => selectedAdminUser.value?.roles.some((role) => role.code === "system_admin") === true,
);
const canLoadUserAdmin = computed(
  () => canReadUsers.value || canReadRoles.value,
);
const canLoadDepartmentAdmin = computed(() => canReadDepartments.value || canManageDepartments.value);
const adminTabDefinitions = computed<AdminTabDefinition[]>(() => [
  { key: "config", label: "配置管理" },
  { key: "departments", label: "部门管理" },
  { key: "users", label: "用户管理" },
  { key: "knowledge", label: "知识库管理" },
  { key: "diagnostics", label: "查询诊断" },
]);
const visibleAdminTabs = computed(() =>
  adminTabDefinitions.value.filter((item) => canAccessAdminTab(item.key)),
);
const canCreateDepartment = computed(
  () =>
    canManageDepartments.value &&
    departmentCreateForm.code.trim().length > 0 &&
    departmentCreateForm.name.trim().length > 0 &&
    !departmentAdminBusy.creating,
);
const canUpdateSelectedDepartment = computed(
  () =>
    Boolean(selectedDepartment.value) &&
    canManageDepartments.value &&
    departmentEditForm.name.trim().length > 0 &&
    !departmentAdminBusy.updating,
);
const canDeleteSelectedDepartment = computed(
  () =>
    Boolean(selectedDepartment.value) &&
    canManageDepartments.value &&
    selectedDepartment.value?.is_default !== true &&
    departmentDangerForm.confirmedDelete &&
    !departmentAdminBusy.deleting,
);
const canCreateAdminUser = computed(
  () =>
    canManageUsers.value &&
    userCreateForm.username.trim().length > 0 &&
    userCreateForm.name.trim().length > 0 &&
    userCreateForm.initialPassword.length > 0 &&
    userCreateForm.initialPassword === userCreateForm.passwordConfirm &&
    userCreateForm.departmentIds.length > 0 &&
    userCreateForm.departmentIds.every((id) =>
      createUserDepartmentOptions.value.some((department) => department.id === id),
    ) &&
    !userAdminBusy.creating,
);
const canUpdateSelectedAdminUser = computed(
  () =>
    Boolean(selectedAdminUser.value) &&
    canManageUsers.value &&
    userEditForm.name.trim().length > 0 &&
    (userEditForm.status !== "disabled" ||
      !selectedAdminUserIsSystemAdmin.value ||
      userEditForm.confirmedDisableAdmin) &&
    !userAdminBusy.updating,
);
const canDeleteSelectedAdminUser = computed(
  () =>
    Boolean(selectedAdminUser.value) &&
    canManageUsers.value &&
    userDangerForm.confirmedDelete &&
    !userAdminBusy.updating,
);
const canResetSelectedUserPassword = computed(
  () =>
    Boolean(selectedAdminUser.value) &&
    canManageUsers.value &&
    passwordResetForm.newPassword.length > 0 &&
    passwordResetForm.newPassword === passwordResetForm.passwordConfirm &&
    passwordResetForm.confirmed &&
    !userAdminBusy.resettingPassword,
);
const canSaveSelectedUserDepartments = computed(
  () =>
    Boolean(selectedAdminUser.value) &&
    canManageDepartments.value &&
    userDepartmentForm.departmentIds.length > 0 &&
    (!selectedUserPrimaryDepartmentWillChange.value ||
      userDepartmentForm.confirmedReplacePrimary) &&
    !userAdminBusy.updatingDepartments,
);
const canAddSelectedUserRole = computed(
  () =>
    Boolean(selectedAdminUser.value) &&
    Boolean(selectedRoleForBinding.value) &&
    canManageRoles.value &&
    selectedRoleBindingScopeReady.value &&
    Boolean(selectedRoleBindingKey.value) &&
    !selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value) &&
    !userAdminBusy.updatingRoles,
);
const roleBindingDisabledReason = computed(() => {
  if (canAddSelectedUserRole.value || userAdminBusy.updatingRoles) {
    return "";
  }
  if (!selectedAdminUser.value) {
    return "请选择需要授权的用户。";
  }
  if (!canManageRoles.value) {
    return "当前账号缺少 role:manage，不能授予角色。";
  }
  if (!selectedRoleForBinding.value) {
    return availableRoleBindingCandidates.value.length === 0
      ? "当前没有可授予的角色作用域；请确认部门或知识库作用域已创建且当前账号有读取权限。"
      : "请选择要授予的角色。";
  }
  if (!selectedRoleBindingScopeReady.value) {
    return selectedRoleBindingScopeType.value === "department"
      ? "请选择部门作用域。"
      : "请选择知识库作用域。";
  }
  if (selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value)) {
    return "该角色作用域已经绑定，请选择其他角色或作用域。";
  }
  return "";
});
const activeConfigVersion = computed(() => {
  const activeVersion = configVersions.value.find((version) => version.status === "active");
  return activeVersion?.version ?? setupState.value?.active_config_version ?? 1;
});
const newestConfigVersion = computed(() =>
  configVersions.value.reduce((max, version) => Math.max(max, version.version), activeConfigVersion.value),
);
const configEditorParseError = computed(() => validateConfigForm());
const configValidationFresh = computed(
  () =>
    configValidationResult.value?.valid === true &&
    lastConfigValidatedText.value === configEditorText.value,
);
const canValidateSelectedConfig = computed(
  () =>
    Boolean(configModalMode.value) &&
    canManageConfig.value &&
    !configBusy.loading &&
    !configBusy.validating &&
    !configBusy.saving &&
    !configBusy.publishing &&
    !configBusy.deleting &&
    configEditorParseError.value === null,
);
const canSaveSelectedConfigDraft = computed(
  () =>
    canValidateSelectedConfig.value &&
    !configBusy.validating &&
    configValidationFresh.value,
);
const canPublishSelectedDraft = computed(
  () =>
    Boolean(selectedDraftVersion.value) &&
    canManageConfig.value &&
    !configBusy.loading &&
    !configBusy.validating &&
    !configBusy.saving &&
    !configBusy.publishing &&
    !configBusy.deleting,
);
const fieldIssueMap = computed(() => {
  const result = new Map<keyof SetupFormModel, LocalValidationIssue[]>();
  for (const issue of localValidationIssues.value) {
    if (!issue.field) {
      continue;
    }
    const issues = result.get(issue.field) ?? [];
    issues.push(issue);
    result.set(issue.field, issues);
  }
  return result;
});
const sectionCheckItems = computed<Array<{ title: string; errors: number; warnings: number; tone: Tone }>>(() =>
  sections.map((section) => {
    const issues = localValidationIssues.value.filter((issue) => issue.section === section.title);
    const errors = issues.filter((issue) => issue.tone === "error").length;
    const warnings = issues.filter((issue) => issue.tone === "warning").length;
    return {
      title: section.title,
      errors,
      warnings,
      tone: errors > 0 ? "error" : warnings > 0 ? "warning" : "success",
    };
  }),
);
const statusLabel = computed(() => {
  if (!setupState.value) {
    return "状态未知";
  }
  return statusLabels[setupState.value.setup_status] ?? setupState.value.setup_status;
});
const statusTone = computed<Tone>(() => {
  if (!setupState.value) {
    return "neutral";
  }
  if (setupState.value.initialized) {
    return "success";
  }
  if (setupState.value.error_code || setupState.value.setup_status.includes("failed")) {
    return "error";
  }
  return "warning";
});
const recoveryMode = computed(() => setupState.value?.recovery_setup_allowed === true);
const canValidate = computed(
  () => !busy.validating && !busy.submitting && localChecksPassed.value && setupWritable.value,
);
const canSubmit = computed(() => {
  return (
    !busy.submitting &&
    !busy.validating &&
    submitConfirmed.value &&
    setupWritable.value &&
    localChecksPassed.value &&
    backendValidationFresh.value
  );
});
const validationGateMessage = computed(() => {
  if (!setupWritable.value) {
    return "当前系统已初始化，初始化写接口应保持关闭。";
  }
  if (!localChecksPassed.value) {
    return `还有 ${localBlockingIssues.value.length} 个本地阻断项需要处理。`;
  }
  if (backendValidationFresh.value) {
    return "后端配置校验已通过，且请求体未变化。";
  }
  if (validationResult.value?.valid === true) {
    return "请求体已变化，需要重新执行配置校验。";
  }
  return "本地核查通过后，先执行后端配置校验。";
});
const flowItems = computed<Array<{ label: string; value: string; tone: Tone }>>(() => [
  {
    label: "初始化令牌",
    value: form.setupToken.trim() ? "已填写" : "缺失",
    tone: form.setupToken.trim() ? "success" : "error",
  },
  {
    label: "本地核查",
    value: localChecksPassed.value ? "通过" : `${localBlockingIssues.value.length} 个阻断项`,
    tone: localChecksPassed.value ? "success" : "error",
  },
  {
    label: "后端校验",
    value: backendValidationFresh.value ? "通过" : "待校验",
    tone: backendValidationFresh.value ? "success" : "neutral",
  },
  {
    label: "初始化提交",
    value: canSubmit.value ? "可提交" : "受控",
    tone: canSubmit.value ? "success" : "neutral",
  },
]);
const submitConfirmationText = computed(() =>
  recoveryMode.value ? "确认恢复当前生效配置" : "确认写入首个管理员、默认组织和当前生效配置",
);
const submitButtonText = computed(() => {
  if (busy.submitting) {
    return "提交中...";
  }
  return recoveryMode.value ? "执行恢复初始化" : "执行初始化";
});
const summaryItems = computed(() => [
  { label: "企业编码", value: form.enterpriseCode },
  { label: "默认部门", value: form.departmentCode },
  { label: "配置版本", value: "1" },
  { label: "向量维度", value: String(form.embeddingDimension) },
  { label: "向量模型服务", value: form.embeddingProviderBaseUrl },
  { label: "重排模型服务", value: form.rerankProviderBaseUrl },
  { label: "大模型服务", value: form.llmProviderBaseUrl },
  { label: "切片策略", value: form.chunkStrategyMode },
  { label: "切片大小", value: `${form.chunkDefaultSizeTokens} tokens` },
  { label: "向量库", value: form.qdrantBaseUrl },
]);
const normalFieldsBySection = computed(() =>
  new Map(
    sections.map((section) => [
      section.title,
      section.fields.filter((field) => !field.group),
    ]),
  ),
);
const checkboxFieldsBySection = computed(() =>
  new Map(
    sections.map((section) => [
      section.title,
      section.fields.filter((field) => field.group === "chunk-preserve" || field.group === "cache-switch"),
    ]),
  ),
);
const validationErrorItems = computed(() => extractStructuredIssues(validationErrorPayload.value));
const initializationErrorItems = computed(() =>
  extractStructuredIssues(initializationErrorPayload.value),
);
const initializationFailedChecks = computed(() =>
  extractBootstrapChecks(initializationErrorPayload.value).filter((item) => item.status !== "passed"),
);
const initializationDatabaseError = computed(() =>
  extractDatabaseError(initializationErrorPayload.value),
);

onMounted(async () => {
  authBusy.bootstrapping = true;
  try {
    await refreshState();
    await restoreAuthenticatedSession();
    syncRouteToCurrentState();
  } finally {
    authBusy.bootstrapping = false;
  }
});

async function refreshState(): Promise<void> {
  busy.refreshing = true;
  try {
    // setup-state 不依赖初始化令牌；传入 token 只是为了复用统一的请求客户端。
    const response = await getSetupState(form.setupToken || undefined);
    setupState.value = response.data;
    feedback.value = null;
    if (!authBusy.bootstrapping) {
      syncRouteToCurrentState();
    }
  } catch (error) {
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取 setup 状态失败"),
    };
  } finally {
    busy.refreshing = false;
  }
}

async function submitLogin(): Promise<void> {
  const username = loginForm.username.trim();
  const password = loginForm.password;
  if (!username || !password) {
    authFeedback.value = {
      tone: "error",
      message: "请输入登录名和密码。",
    };
    return;
  }

  authBusy.loggingIn = true;
  try {
    const tokenResponse = await createSession({
      username,
      password,
    });
    saveAuthTokens(tokenResponse);
    let userResponse;
    try {
      userResponse = await getAdminCurrentUserCapabilities(tokenResponse.access_token);
    } catch (error) {
      if (isAdminPortalForbidden(error)) {
        await rejectAdminPortalLogin(tokenResponse.access_token);
        loginForm.password = "";
        return;
      }
      throw error;
    }
    currentUser.value = userResponse.data;
    if (!canAccessAdminPortal()) {
      await rejectAdminPortalLogin(tokenResponse.access_token);
      loginForm.password = "";
      return;
    }
    adminAccessGranted.value = true;
    ensureVisibleAdminTab();
    await refreshSelectedAdminTabState();
    loginForm.password = "";
    authFeedback.value = {
      tone: "success",
      message: "登录成功。",
    };
    navigateTo("/admin");
  } catch (error) {
    clearAuthSession();
    authFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "登录失败"),
    };
  } finally {
    authBusy.loggingIn = false;
  }
}

async function restoreAuthenticatedSession(): Promise<void> {
  if (!authTokens.value?.accessToken || setupModeRequired.value) {
    currentUser.value = null;
    return;
  }

  try {
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      clearAuthSession();
      return;
    }
    const userResponse = await getAdminCurrentUserCapabilities(accessToken);
    currentUser.value = userResponse.data;
    if (!canAccessAdminPortal()) {
      await rejectAdminPortalLogin(accessToken);
      return;
    }
    adminAccessGranted.value = true;
    authFeedback.value = null;
    ensureVisibleAdminTab();
    await refreshSelectedAdminTabState();
  } catch (error) {
    if (isAdminPortalForbidden(error)) {
      const accessToken = authTokens.value?.accessToken;
      if (accessToken) {
        await rejectAdminPortalLogin(accessToken);
        return;
      }
    }
    clearAuthSession();
  }
}

function syncPaginationState(state: PaginationState, pagination: PaginationData): void {
  state.page = pagination.page;
  state.pageSize = pagination.page_size;
  state.total = pagination.total;
}

function clearPaginationState(state: PaginationState): void {
  state.page = 1;
  state.total = 0;
}

function paginationTotalPages(state: PaginationState): number {
  return Math.max(1, Math.ceil(state.total / Math.max(state.pageSize, 1)));
}

function paginationStart(state: PaginationState): number {
  if (state.total === 0) {
    return 0;
  }
  return (state.page - 1) * state.pageSize + 1;
}

function paginationEnd(state: PaginationState): number {
  return Math.min(state.total, state.page * state.pageSize);
}

function changePaginationPage(
  state: PaginationState,
  refresh: () => Promise<void>,
  page: number,
): void {
  const nextPage = Math.min(Math.max(page, 1), paginationTotalPages(state));
  if (state.page === nextPage) {
    return;
  }
  state.page = nextPage;
  void refresh();
}

function changePaginationPageSize(
  state: PaginationState,
  refresh: () => Promise<void>,
): void {
  state.page = 1;
  void refresh();
}

function refreshFirstPage(state: PaginationState, refresh: () => Promise<void>): void {
  state.page = 1;
  void refresh();
}

async function refreshConfigAdminState(): Promise<void> {
  if (!canReadConfig.value && !canManageConfig.value) {
    configItems.value = [];
    configVersions.value = [];
    configVersionDetails.value = {};
    clearPaginationState(configVersionPagination);
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.loading = true;
  try {
    const versionsResponse = await listConfigVersions(accessToken, {
      page: configVersionPagination.page,
      page_size: configVersionPagination.pageSize,
    });
    configVersions.value = versionsResponse.data;
    syncPaginationState(configVersionPagination, versionsResponse.pagination);
    const activeVersionNumber =
      configVersions.value.find((version) => version.status === "active")?.version ??
      setupState.value?.active_config_version ??
      activeConfigVersion.value;
    if (activeVersionNumber) {
      await ensureConfigVersionDetail(activeVersionNumber, accessToken);
    }
    configItems.value = configItemsFromVersion(activeConfigVersionRecord.value);
    if (canReadAudit.value) {
      try {
        const auditResponse = await listAuditLogs(accessToken, {
          page: auditLogPagination.page,
          page_size: auditLogPagination.pageSize,
          resource_type: "config",
        });
        auditLogs.value = auditResponse.data;
        syncPaginationState(auditLogPagination, auditResponse.pagination);
        auditFeedback.value = null;
      } catch (error) {
        auditLogs.value = [];
        clearPaginationState(auditLogPagination);
        auditFeedback.value = {
          tone: "error",
          message: normalizeErrorMessage(error, "读取配置审计日志失败"),
        };
      }
    } else {
      auditLogs.value = [];
      clearPaginationState(auditLogPagination);
      auditFeedback.value = null;
    }
    syncConfigFormFromVersion(activeConfigVersionRecord.value);
    configFeedback.value = {
      tone: "success",
      message: "配置管理数据已刷新。",
    };
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取配置管理数据失败"),
    };
  } finally {
    configBusy.loading = false;
  }
}

async function refreshDepartmentOptions(existingAccessToken?: string): Promise<void> {
  if (!canReadDepartments.value) {
    adminDepartmentOptions.value = [];
    ensureDefaultCreateDepartmentSelection();
    syncKnowledgeBaseCreateOwnerDefault();
    syncRoleBindingScopeDefault();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminDepartmentOptions(accessToken, {
    keyword: optionSearchForm.departmentKeyword.trim() || undefined,
    status: "active",
    page_size: selectorPageSize,
  });
  adminDepartmentOptions.value = mergeDepartmentOptions(response.data);
  ensureDefaultCreateDepartmentSelection();
  syncKnowledgeBaseCreateOwnerDefault();
  syncRoleBindingScopeDefault();
}

async function refreshAssignableRoleOptions(existingAccessToken?: string): Promise<void> {
  if (!canReadRoles.value) {
    adminRoles.value = [];
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminAssignableRoleOptions(accessToken, {
    keyword: optionSearchForm.roleKeyword.trim() || undefined,
    status: "active",
    page_size: selectorPageSize,
  });
  adminRoles.value = mergeAssignableRoleOptions(response.data);
  if (!roleBindingForm.roleId && assignableRoles.value.length > 0) {
    roleBindingForm.roleId = assignableRoles.value[0].id;
  }
  syncRoleBindingScopeDefault();
}

async function refreshKnowledgeBaseOptions(existingAccessToken?: string): Promise<void> {
  if (!canManageKnowledgeBases.value) {
    adminKnowledgeBaseOptions.value = [];
    syncRoleBindingScopeDefault();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminKnowledgeBaseOptions(accessToken, {
    keyword: optionSearchForm.knowledgeBaseKeyword.trim() || undefined,
    status: "active",
    page_size: selectorPageSize,
  });
  adminKnowledgeBaseOptions.value = mergeKnowledgeBaseOptions(response.data);
  syncRoleBindingScopeDefault();
}

async function refreshFolderOptions(existingAccessToken?: string): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canManageFolders.value) {
    adminFolderOptions.value = [];
    importUploadForm.folderId = "";
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminFolderOptions(knowledgeBase.id, accessToken, {
    keyword: optionSearchForm.folderKeyword.trim() || undefined,
    status: "active",
    page_size: selectorPageSize,
  });
  adminFolderOptions.value = mergeFolderOptions(response.data);
}

function refreshDepartmentOptionsFromSearch(): void {
  void refreshDepartmentOptions();
}

function refreshAssignableRoleOptionsFromSearch(): void {
  void refreshAssignableRoleOptions();
}

function refreshKnowledgeBaseOptionsFromSearch(): void {
  void refreshKnowledgeBaseOptions();
}

function refreshFolderOptionsFromSearch(): void {
  void refreshFolderOptions();
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    if (seen.has(item.id)) {
      continue;
    }
    seen.add(item.id);
    result.push(item);
  }
  return result;
}

function departmentOptionFromDepartment(
  department: { id: string; name: string; status: string; is_default?: boolean | null } | null | undefined,
): AdminDepartmentOptionData | null {
  if (!department) {
    return null;
  }
  return {
    id: department.id,
    name: department.name,
    status: department.status,
    is_default: "is_default" in department ? Boolean(department.is_default) : false,
  };
}

function mergeDepartmentOptions(
  options: AdminDepartmentOptionData[],
): AdminDepartmentOptionData[] {
  const pinned = [
    ...(currentUser.value?.departments ?? []),
    ...(selectedAdminUser.value?.departments ?? []),
    ...selectedUserDepartments.value,
    ...adminDepartments.value,
    ...(selectedKnowledgeBaseDetail.value?.owner_department
      ? [selectedKnowledgeBaseDetail.value.owner_department]
      : []),
    ...(selectedKnowledgeBaseDetail.value?.default_document_owner_department
      ? [selectedKnowledgeBaseDetail.value.default_document_owner_department]
      : []),
  ]
    .map(departmentOptionFromDepartment)
    .filter((department): department is AdminDepartmentOptionData => Boolean(department));
  return uniqueById([...options, ...pinned]);
}

function mergeAssignableRoleOptions(
  options: AdminAssignableRoleOptionData[],
): AdminAssignableRoleOptionData[] {
  const pinned =
    selectedAdminUser.value?.roles.map((role) => ({
      id: role.id,
      code: role.code,
      name: role.name,
      scope_type: role.scope_type,
      status: role.status,
      risk_level: isHighRiskAdminRole(role) ? "high" as const : "low" as const,
    })) ?? [];
  return uniqueById([...options, ...pinned]);
}

function mergeKnowledgeBaseOptions(
  options: AdminKnowledgeBaseOptionData[],
): AdminKnowledgeBaseOptionData[] {
  const pinned = [
    ...adminKnowledgeBases.value.map((knowledgeBase) => ({
      id: knowledgeBase.id,
      name: knowledgeBase.name,
      status: knowledgeBase.status,
    })),
    ...(selectedKnowledgeBaseDetail.value
      ? [
          {
            id: selectedKnowledgeBaseDetail.value.id,
            name: selectedKnowledgeBaseDetail.value.name,
            status: selectedKnowledgeBaseDetail.value.status,
          },
        ]
      : []),
  ];
  return uniqueById([...options, ...pinned]);
}

function mergeFolderOptions(options: AdminFolderOptionData[]): AdminFolderOptionData[] {
  const pinned = adminFolders.value.map((folder) => ({
    id: folder.id,
    name: folder.name,
    status: folder.status,
  }));
  return uniqueById([...options, ...pinned]);
}

async function refreshUserRoleAdminState(): Promise<void> {
  if (!canLoadUserAdmin.value) {
    adminUsers.value = [];
    clearPaginationState(userPagination);
    adminDepartmentOptions.value = [];
    adminKnowledgeBaseOptions.value = [];
    adminRoles.value = [];
    selectedAdminUserId.value = "";
    selectedAdminUserDetail.value = null;
    selectedUserDepartments.value = [];
    selectedUserRoleBindings.value = [];
    clearPaginationState(selectedUserDepartmentPagination);
    clearPaginationState(selectedUserRoleBindingPagination);
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

    userAdminBusy.loading = true;
  try {
    if (canReadRoles.value) {
      await refreshAssignableRoleOptions(accessToken);
    } else {
      adminRoles.value = [];
    }
    if (canReadDepartments.value) {
      await refreshDepartmentOptions(accessToken);
    } else {
      adminDepartmentOptions.value = [];
      ensureDefaultCreateDepartmentSelection();
    }
    if (canManageKnowledgeBases.value) {
      await refreshKnowledgeBaseOptions(accessToken);
    } else {
      adminKnowledgeBaseOptions.value = [];
    }
    if (canReadUsers.value) {
      const usersResponse = await listAdminUsers(accessToken, {
        keyword: userSearchForm.keyword.trim() || undefined,
        status: userSearchForm.status || undefined,
        page: userPagination.page,
        page_size: userPagination.pageSize,
      });
      adminUsers.value = usersResponse.data;
      syncPaginationState(userPagination, usersResponse.pagination);
      if (
        !selectedAdminUserId.value ||
        !adminUsers.value.some((user) => user.id === selectedAdminUserId.value)
      ) {
        selectedAdminUserId.value = adminUsers.value[0]?.id ?? "";
        selectedAdminUserDetail.value = null;
        clearPaginationState(selectedUserDepartmentPagination);
        clearPaginationState(selectedUserRoleBindingPagination);
      } else if (selectedAdminUserDetail.value?.id !== selectedAdminUserId.value) {
        selectedAdminUserDetail.value = null;
      }
    } else {
      adminUsers.value = [];
      clearPaginationState(userPagination);
    selectedAdminUserId.value = "";
    selectedAdminUserDetail.value = null;
    clearPaginationState(selectedUserDepartmentPagination);
    clearPaginationState(selectedUserRoleBindingPagination);
  }
    if (selectedAdminUserId.value && selectedAdminUserDetail.value) {
      await refreshSelectedAdminUserDetail(accessToken);
    }
    await refreshSelectedUserDepartments(accessToken);
    await refreshSelectedUserRoleBindings(accessToken);
    if (!roleBindingForm.roleId || selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value)) {
      selectNextAvailableRoleBindingTarget();
    } else {
      syncRoleBindingScopeDefault();
    }
    userAdminFeedback.value = {
      tone: "success",
      message: "用户与角色数据已刷新。",
    };
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取用户与角色数据失败"),
    };
  } finally {
    userAdminBusy.loading = false;
  }
}

async function refreshDepartmentAdminState(): Promise<void> {
  if (!canLoadDepartmentAdmin.value) {
    adminDepartments.value = [];
    clearPaginationState(departmentPagination);
    selectedDepartmentId.value = "";
    syncDepartmentEditForm();
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  departmentAdminBusy.loading = true;
  try {
    const response = await listAdminDepartments(accessToken, {
      keyword: departmentSearchForm.keyword.trim() || undefined,
      status: departmentSearchForm.status || undefined,
      page: departmentPagination.page,
      page_size: departmentPagination.pageSize,
    });
    adminDepartments.value = response.data;
    syncPaginationState(departmentPagination, response.pagination);
    if (
      !selectedDepartmentId.value ||
      !adminDepartments.value.some((department) => department.id === selectedDepartmentId.value)
    ) {
      selectedDepartmentId.value = adminDepartments.value[0]?.id ?? "";
    }
    syncDepartmentEditForm();
    departmentAdminFeedback.value = {
      tone: "success",
      message: "部门数据已刷新。",
    };
  } catch (error) {
    departmentAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取部门数据失败"),
    };
  } finally {
    departmentAdminBusy.loading = false;
  }
}

async function refreshImportJobList(
  accessToken: string,
  fallbackKbId?: string,
): Promise<void> {
  if (!canReadImportJobs.value) {
    adminImportJobs.value = [];
    clearPaginationState(importJobPagination);
    return;
  }
  const jobsResponse = await listAdminImportJobs(accessToken, {
    page: importJobPagination.page,
    page_size: importJobPagination.pageSize,
    kb_id: importSearchForm.kbId || fallbackKbId || undefined,
    job_type: importSearchForm.jobType || undefined,
    status: importSearchForm.status || undefined,
    stage: importSearchForm.stage || undefined,
  });
  adminImportJobs.value = jobsResponse.data;
  syncPaginationState(importJobPagination, jobsResponse.pagination);
}

function refreshImportTaskFilters(): void {
  importJobPagination.page = 1;
  failedIndexJobPagination.page = 1;
  void refreshKnowledgeBaseAdminState();
}

async function refreshKnowledgeBaseAdminState(): Promise<void> {
  if (!canLoadImportAdmin.value) {
    adminKnowledgeBases.value = [];
    adminKnowledgeBaseOptions.value = [];
    selectedKnowledgeBaseDetail.value = null;
    clearPaginationState(knowledgeBasePagination);
    adminFolders.value = [];
    adminFolderOptions.value = [];
    clearPaginationState(folderPagination);
    adminDocuments.value = [];
    clearPaginationState(documentPagination);
    clearSelectedDocumentDetails();
    clearSelectedDocumentMetadata();
    adminImportJobs.value = [];
    clearPaginationState(importJobPagination);
    failedIndexJobs.value = [];
    selectedFailedIndexJobIds.value = [];
    clearPaginationState(failedIndexJobPagination);
    selectedKnowledgeBaseId.value = "";
    selectedFolderId.value = "";
    selectedDocumentId.value = "";
    importAdminFeedback.value = {
      tone: "error",
      message: "当前账号缺少知识库、文件夹、文档、权限或导入任务读取权限。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.loading = true;
  let failedIndexJobsLoaded = true;
  try {
    if (canReadDepartments.value) {
      await refreshDepartmentOptions(accessToken);
    } else {
      adminDepartmentOptions.value = [];
    }
    if (canManageKnowledgeBases.value) {
      await refreshKnowledgeBaseOptions(accessToken);
      const previousSelectedKnowledgeBaseId = selectedKnowledgeBaseId.value;
      const knowledgeBasesResponse = await listAdminKnowledgeBases(accessToken, {
        keyword: knowledgeBaseSearchForm.keyword.trim() || undefined,
        status: knowledgeBaseSearchForm.status || undefined,
        page: knowledgeBasePagination.page,
        page_size: knowledgeBasePagination.pageSize,
      });
      adminKnowledgeBases.value = knowledgeBasesResponse.data;
      syncPaginationState(knowledgeBasePagination, knowledgeBasesResponse.pagination);
      if (
        !selectedKnowledgeBaseId.value ||
        !adminKnowledgeBases.value.some((knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId.value)
      ) {
        selectedKnowledgeBaseId.value = adminKnowledgeBases.value[0]?.id ?? "";
        selectedKnowledgeBaseDetail.value = null;
      }
      if (selectedKnowledgeBaseId.value !== previousSelectedKnowledgeBaseId) {
        selectedFolderId.value = "";
        selectedDocumentId.value = "";
        clearPaginationState(folderPagination);
        clearPaginationState(documentPagination);
        clearSelectedDocumentDetails();
        clearSelectedDocumentMetadata();
      }
      ensureImportKnowledgeBaseSelection();
      if (selectedKnowledgeBaseId.value) {
        await refreshSelectedKnowledgeBaseDetail(accessToken);
      } else {
        selectedKnowledgeBaseDetail.value = null;
      }
      if (canManageFolders.value) {
        await refreshSelectedKnowledgeBaseFolders(accessToken);
      } else {
        adminFolders.value = [];
        adminFolderOptions.value = [];
        clearPaginationState(folderPagination);
        selectedFolderId.value = "";
      }
      if (canManageDocuments.value) {
        await refreshSelectedKnowledgeBaseDocuments(accessToken);
      } else {
        adminDocuments.value = [];
        clearPaginationState(documentPagination);
        selectedDocumentId.value = "";
        clearSelectedDocumentDetails();
        clearSelectedDocumentMetadata();
      }
    } else {
      clearPaginationState(knowledgeBasePagination);
      adminKnowledgeBaseOptions.value = [];
      selectedKnowledgeBaseDetail.value = null;
      adminFolders.value = [];
      adminFolderOptions.value = [];
      clearPaginationState(folderPagination);
      adminDocuments.value = [];
      clearPaginationState(documentPagination);
      selectedFolderId.value = "";
      selectedDocumentId.value = "";
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
    }
    if (canReadImportJobs.value) {
      await refreshImportJobList(accessToken);
      failedIndexJobsLoaded = await refreshFailedIndexJobs(accessToken);
    } else {
      adminImportJobs.value = [];
      clearPaginationState(importJobPagination);
      failedIndexJobs.value = [];
      selectedFailedIndexJobIds.value = [];
      clearPaginationState(failedIndexJobPagination);
    }
    if (failedIndexJobsLoaded) {
      importAdminFeedback.value = {
        tone: "success",
        message: "知识库管理数据已刷新。",
      };
    }
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取知识库管理数据失败"),
    };
  } finally {
    importAdminBusy.loading = false;
  }
}

async function refreshFailedIndexJobs(existingAccessToken?: string): Promise<boolean> {
  if (!canReadImportJobs.value) {
    failedIndexJobs.value = [];
    selectedFailedIndexJobIds.value = [];
    clearPaginationState(failedIndexJobPagination);
    return true;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return false;
  }

  importAdminBusy.loadingFailedIndexJobs = true;
  try {
    const response = await listAdminImportJobs(accessToken, {
      kb_id: importSearchForm.kbId || undefined,
      status: "failed",
      job_type: "index_rebuild",
      page: failedIndexJobPagination.page,
      page_size: failedIndexJobPagination.pageSize,
    });
    failedIndexJobs.value = response.data;
    syncPaginationState(failedIndexJobPagination, response.pagination);
    if (
      failedIndexJobs.value.length === 0 &&
      failedIndexJobPagination.total > 0 &&
      failedIndexJobPagination.page > 1
    ) {
      failedIndexJobPagination.page = paginationTotalPages(failedIndexJobPagination);
      return refreshFailedIndexJobs(accessToken);
    }
    const availableIds = new Set(response.data.map((job) => job.id));
    selectedFailedIndexJobIds.value = selectedFailedIndexJobIds.value.filter((id) =>
      availableIds.has(id),
    );
    if (selectedFailedIndexJobIds.value.length === 0) {
      indexRetryForm.confirmedRetry = false;
    }
    return true;
  } catch (error) {
    failedIndexJobs.value = [];
    selectedFailedIndexJobIds.value = [];
    clearPaginationState(failedIndexJobPagination);
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取失败索引任务失败"),
    };
    return false;
  } finally {
    importAdminBusy.loadingFailedIndexJobs = false;
  }
}

async function refreshFailedIndexJobsPage(): Promise<void> {
  await refreshFailedIndexJobs();
}

function toggleFailedIndexJob(jobId: string, checked: boolean): void {
  const next = new Set(selectedFailedIndexJobIds.value);
  if (checked) {
    next.add(jobId);
  } else {
    next.delete(jobId);
  }
  selectedFailedIndexJobIds.value = Array.from(next);
  if (selectedFailedIndexJobIds.value.length === 0) {
    indexRetryForm.confirmedRetry = false;
  }
}

function onFailedIndexJobToggle(jobId: string, event: Event): void {
  toggleFailedIndexJob(jobId, (event.target as HTMLInputElement).checked);
}

function toggleAllFailedIndexJobs(checked: boolean): void {
  selectedFailedIndexJobIds.value = checked ? failedIndexJobs.value.map((job) => job.id) : [];
  if (!checked) {
    indexRetryForm.confirmedRetry = false;
  }
}

function onAllFailedIndexJobsToggle(event: Event): void {
  toggleAllFailedIndexJobs((event.target as HTMLInputElement).checked);
}

async function retrySelectedFailedIndexJobs(): Promise<void> {
  if (!canRetrySelectedFailedIndexJobs.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "批量重试前必须选择失败索引任务，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.retryingIndexJobs = true;
  try {
    const response = await retryAdminIndexJobs(
      { job_ids: selectedFailedIndexJobIds.value },
      accessToken,
      true,
    );
    indexRetryForm.confirmedRetry = false;
    selectedFailedIndexJobIds.value = [];
    await refreshKnowledgeBaseAdminState();
    importAdminFeedback.value = {
      tone: "success",
      message: `已创建 ${response.data.length} 个索引重试任务。`,
    };
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "批量重试索引任务失败"),
    };
  } finally {
    importAdminBusy.retryingIndexJobs = false;
  }
}

async function refreshSelectedUserRoleBindings(existingAccessToken?: string): Promise<void> {
  if (!selectedAdminUserId.value || !canReadRoles.value) {
    selectedUserRoleBindings.value = [];
    clearPaginationState(selectedUserRoleBindingPagination);
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminUserRoleBindings(selectedAdminUserId.value, accessToken, {
    page: selectedUserRoleBindingPagination.page,
    page_size: selectedUserRoleBindingPagination.pageSize,
  });
  selectedUserRoleBindings.value = response.data;
  syncPaginationState(selectedUserRoleBindingPagination, response.pagination);
  if (
    selectedUserRoleBindings.value.length === 0 &&
    selectedUserRoleBindingPagination.total > 0 &&
    selectedUserRoleBindingPagination.page > 1
  ) {
    selectedUserRoleBindingPagination.page = paginationTotalPages(selectedUserRoleBindingPagination);
    await refreshSelectedUserRoleBindings(accessToken);
    return;
  }
  syncRoleBindingScopeDefault();
}

async function refreshSelectedUserRoleBindingsPage(): Promise<void> {
  await refreshSelectedUserRoleBindings();
}

async function refreshSelectedUserDepartments(existingAccessToken?: string): Promise<void> {
  if (!selectedAdminUserId.value) {
    selectedUserDepartments.value = [];
    clearPaginationState(selectedUserDepartmentPagination);
    syncSelectedUserDepartmentForm();
    return;
  }
  if (!canReadDepartments.value) {
    selectedUserDepartments.value = selectedAdminUser.value?.departments ?? [];
    selectedUserDepartmentPagination.page = 1;
    selectedUserDepartmentPagination.total = selectedUserDepartments.value.length;
    syncSelectedUserDepartmentForm();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminUserDepartments(selectedAdminUserId.value, accessToken, {
    page: selectedUserDepartmentPagination.page,
    page_size: selectedUserDepartmentPagination.pageSize,
  });
  selectedUserDepartments.value = response.data;
  syncPaginationState(selectedUserDepartmentPagination, response.pagination);
  if (
    selectedUserDepartments.value.length === 0 &&
    selectedUserDepartmentPagination.total > 0 &&
    selectedUserDepartmentPagination.page > 1
  ) {
    selectedUserDepartmentPagination.page = paginationTotalPages(selectedUserDepartmentPagination);
    await refreshSelectedUserDepartments(accessToken);
    return;
  }
  syncSelectedUserDepartmentForm();
}

async function refreshSelectedUserDepartmentsPage(): Promise<void> {
  await refreshSelectedUserDepartments();
}

async function refreshSelectedKnowledgeBaseDetail(existingAccessToken?: string): Promise<void> {
  if (!selectedKnowledgeBaseId.value || !canManageKnowledgeBases.value) {
    selectedKnowledgeBaseDetail.value = null;
    syncKnowledgeBaseEditForm();
    syncKnowledgeBasePermissionForm();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await getAdminKnowledgeBase(selectedKnowledgeBaseId.value, accessToken);
  selectedKnowledgeBaseDetail.value = response.data;
  upsertKnowledgeBase(response.data);
  syncKnowledgeBaseEditForm();
  syncKnowledgeBasePermissionForm();
}

async function refreshSelectedKnowledgeBaseFolders(existingAccessToken?: string): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canManageFolders.value) {
    adminFolders.value = [];
    adminFolderOptions.value = [];
    clearPaginationState(folderPagination);
    selectedFolderId.value = "";
    importUploadForm.folderId = "";
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  importAdminBusy.loadingFolders = true;
  try {
    const foldersResponse = await listAdminFolders(knowledgeBase.id, accessToken, {
      page: folderPagination.page,
      page_size: folderPagination.pageSize,
    });
    adminFolders.value = foldersResponse.data;
    syncPaginationState(folderPagination, foldersResponse.pagination);
    if (adminFolders.value.length === 0 && folderPagination.total > 0 && folderPagination.page > 1) {
      folderPagination.page = paginationTotalPages(folderPagination);
      await refreshSelectedKnowledgeBaseFolders(accessToken);
      return;
    }
    await refreshFolderOptions(accessToken);
    if (
      selectedFolderId.value &&
      !adminFolders.value.some((folder) => folder.id === selectedFolderId.value)
    ) {
      selectedFolderId.value = "";
    }
    syncFolderEditForm();
  } catch (error) {
    adminFolders.value = [];
    adminFolderOptions.value = [];
    clearPaginationState(folderPagination);
    selectedFolderId.value = "";
    importUploadForm.folderId = "";
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取知识库文件夹失败"),
    };
  } finally {
    importAdminBusy.loadingFolders = false;
  }
}

function clearSelectedDocumentDetails(): void {
  selectedDocumentVersions.value = [];
  selectedDocumentIndexVersions.value = [];
  selectedDocumentChunks.value = [];
  highlightedDocumentChunkId.value = "";
  clearPaginationState(documentVersionPagination);
  clearPaginationState(documentIndexVersionPagination);
  clearPaginationState(documentChunkPagination);
  documentIndexForm.confirmedRebuild = false;
  clearIndexVersionCleanupSelection();
}

function clearSelectedDocumentMetadata(): void {
  selectedAdminDocumentDetail.value = null;
  syncDocumentPermissionForm();
}

function clearBatchDocumentSelection(): void {
  selectedBatchDocumentIds.value = [];
  documentIndexForm.confirmedBatchRebuild = false;
}

function clearIndexVersionCleanupSelection(): void {
  selectedCleanupIndexVersionIds.value = [];
  documentIndexForm.confirmedCleanup = false;
}

async function refreshSelectedKnowledgeBaseDocuments(existingAccessToken?: string): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canManageDocuments.value) {
    adminDocuments.value = [];
    selectedDocumentId.value = "";
    clearPaginationState(documentPagination);
    clearSelectedDocumentDetails();
    clearSelectedDocumentMetadata();
    clearBatchDocumentSelection();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  importAdminBusy.loadingDocuments = true;
  try {
    const response = await listAdminDocuments(knowledgeBase.id, accessToken, {
      status: documentSearchForm.status || undefined,
      page: documentPagination.page,
      page_size: documentPagination.pageSize,
    });
    adminDocuments.value = response.data;
    syncPaginationState(documentPagination, response.pagination);
    if (adminDocuments.value.length === 0 && documentPagination.total > 0 && documentPagination.page > 1) {
      documentPagination.page = paginationTotalPages(documentPagination);
      await refreshSelectedKnowledgeBaseDocuments(accessToken);
      return;
    }
    pruneSelectedBatchDocuments();
    if (
      selectedDocumentId.value &&
      !adminDocuments.value.some((document) => document.id === selectedDocumentId.value)
    ) {
      selectedDocumentId.value = "";
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
    }
    syncDocumentPermissionForm();
    if (selectedDocumentId.value && documentModalMode.value === "details") {
      await refreshSelectedDocumentDetails(accessToken);
    } else if (selectedDocumentId.value && documentModalMode.value === "permissions") {
      await refreshSelectedDocumentMetadata(accessToken);
    }
  } catch (error) {
    adminDocuments.value = [];
    selectedDocumentId.value = "";
    clearPaginationState(documentPagination);
    clearBatchDocumentSelection();
    clearSelectedDocumentDetails();
    clearSelectedDocumentMetadata();
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取知识库文档失败"),
    };
  } finally {
    importAdminBusy.loadingDocuments = false;
  }
}

async function refreshSelectedDocumentDetails(existingAccessToken?: string): Promise<void> {
  const documentId = selectedDocumentId.value;
  if (!documentId || !canManageDocuments.value) {
    clearSelectedDocumentDetails();
    clearSelectedDocumentMetadata();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  importAdminBusy.loadingDocumentDetails = true;
  importAdminBusy.loadingDocumentVersions = true;
  importAdminBusy.loadingIndexVersions = canIndexDocuments.value;
  try {
    const [documentResponse, versionsResponse, chunksResponse, indexVersionsResponse] = await Promise.all([
      getAdminDocument(documentId, accessToken),
      listAdminDocumentVersions(documentId, accessToken, {
        page: documentVersionPagination.page,
        page_size: documentVersionPagination.pageSize,
      }),
      listAdminDocumentChunks(documentId, accessToken, {
        page: documentChunkPagination.page,
        page_size: documentChunkPagination.pageSize,
      }),
      canIndexDocuments.value
        ? listAdminDocumentIndexVersions(documentId, accessToken, {
            page: documentIndexVersionPagination.page,
            page_size: documentIndexVersionPagination.pageSize,
          })
        : Promise.resolve({
            request_id: "",
            data: [] as IndexVersionData[],
            pagination: { page: 1, page_size: documentIndexVersionPagination.pageSize, total: 0 },
          }),
    ]);
    selectedAdminDocumentDetail.value = documentResponse.data;
    selectedDocumentVersions.value = versionsResponse.data;
    syncPaginationState(documentVersionPagination, versionsResponse.pagination);
    selectedDocumentChunks.value = chunksResponse.data;
    syncPaginationState(documentChunkPagination, chunksResponse.pagination);
    selectedDocumentIndexVersions.value = indexVersionsResponse.data;
    syncPaginationState(documentIndexVersionPagination, indexVersionsResponse.pagination);
    highlightedDocumentChunkId.value = chunksResponse.data[0]?.id ?? "";
    documentIndexForm.confirmedRebuild = false;
    pruneSelectedIndexVersionsForCleanup();
    syncDocumentPermissionForm();
  } catch (error) {
    clearSelectedDocumentDetails();
    clearSelectedDocumentMetadata();
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取文档版本、chunk 或索引版本失败"),
    };
  } finally {
    importAdminBusy.loadingDocumentDetails = false;
    importAdminBusy.loadingDocumentVersions = false;
    importAdminBusy.loadingIndexVersions = false;
  }
}

async function refreshSelectedDocumentMetadata(existingAccessToken?: string): Promise<void> {
  const documentId = selectedDocumentId.value;
  if (!documentId || !canManageDocuments.value) {
    clearSelectedDocumentMetadata();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  importAdminBusy.loadingDocumentDetails = true;
  try {
    const response = await getAdminDocument(documentId, accessToken);
    selectedAdminDocumentDetail.value = response.data;
    syncDocumentPermissionForm();
  } catch (error) {
    clearSelectedDocumentMetadata();
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取文档详情失败"),
    };
  } finally {
    importAdminBusy.loadingDocumentDetails = false;
  }
}

async function refreshSelectedDocumentVersions(existingAccessToken?: string): Promise<void> {
  const documentId = selectedDocumentId.value;
  if (!documentId || !canManageDocuments.value) {
    selectedDocumentVersions.value = [];
    clearPaginationState(documentVersionPagination);
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  importAdminBusy.loadingDocumentVersions = true;
  try {
    const response = await listAdminDocumentVersions(documentId, accessToken, {
      page: documentVersionPagination.page,
      page_size: documentVersionPagination.pageSize,
    });
    selectedDocumentVersions.value = response.data;
    syncPaginationState(documentVersionPagination, response.pagination);
  } catch (error) {
    selectedDocumentVersions.value = [];
    clearPaginationState(documentVersionPagination);
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取文档版本失败"),
    };
  } finally {
    importAdminBusy.loadingDocumentVersions = false;
  }
}

async function refreshSelectedDocumentIndexVersions(existingAccessToken?: string): Promise<void> {
  const documentId = selectedDocumentId.value;
  if (!documentId || !canIndexDocuments.value) {
    selectedDocumentIndexVersions.value = [];
    clearPaginationState(documentIndexVersionPagination);
    clearIndexVersionCleanupSelection();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  importAdminBusy.loadingIndexVersions = true;
  try {
    const response = await listAdminDocumentIndexVersions(documentId, accessToken, {
      page: documentIndexVersionPagination.page,
      page_size: documentIndexVersionPagination.pageSize,
    });
    selectedDocumentIndexVersions.value = response.data;
    syncPaginationState(documentIndexVersionPagination, response.pagination);
    pruneSelectedIndexVersionsForCleanup();
  } catch (error) {
    selectedDocumentIndexVersions.value = [];
    clearPaginationState(documentIndexVersionPagination);
    clearIndexVersionCleanupSelection();
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取文档索引版本失败"),
    };
  } finally {
    importAdminBusy.loadingIndexVersions = false;
  }
}

function isDocumentBatchRebuildEligible(document: AdminDocumentData | AdminDocumentListItemData): boolean {
  if ("can_rebuild_index" in document) {
    return document.can_rebuild_index;
  }
  return document.lifecycle_status === "active" && Boolean(document.current_version_id);
}

function pruneSelectedBatchDocuments(): void {
  const visibleEligibleIds = new Set(
    adminDocuments.value
      .filter((document) => isDocumentBatchRebuildEligible(document))
      .map((document) => document.id),
  );
  selectedBatchDocumentIds.value = selectedBatchDocumentIds.value.filter((documentId) =>
    visibleEligibleIds.has(documentId),
  );
  if (selectedBatchDocumentIds.value.length === 0) {
    documentIndexForm.confirmedBatchRebuild = false;
  }
}

function toggleBatchDocumentSelection(documentId: string, checked: boolean): void {
  const next = new Set(selectedBatchDocumentIds.value);
  if (checked) {
    next.add(documentId);
  } else {
    next.delete(documentId);
  }
  selectedBatchDocumentIds.value = Array.from(next);
  if (selectedBatchDocumentIds.value.length === 0) {
    documentIndexForm.confirmedBatchRebuild = false;
  }
}

function onBatchDocumentSelectionToggle(documentId: string, event: Event): void {
  toggleBatchDocumentSelection(documentId, (event.target as HTMLInputElement).checked);
}

function toggleAllBatchDocuments(checked: boolean): void {
  selectedBatchDocumentIds.value = checked
    ? batchRebuildEligibleDocuments.value.map((document) => document.id)
    : [];
  if (!checked) {
    documentIndexForm.confirmedBatchRebuild = false;
  }
}

function onAllBatchDocumentsToggle(event: Event): void {
  toggleAllBatchDocuments((event.target as HTMLInputElement).checked);
}

function pruneSelectedIndexVersionsForCleanup(): void {
  const eligibleIds = new Set(
    selectedDocumentIndexVersions.value
      .filter((version) => version.status === "pending_delete")
      .map((version) => version.id),
  );
  selectedCleanupIndexVersionIds.value = selectedCleanupIndexVersionIds.value.filter(
    (indexVersionId) => eligibleIds.has(indexVersionId),
  );
  if (selectedCleanupIndexVersionIds.value.length === 0) {
    documentIndexForm.confirmedCleanup = false;
  }
}

function toggleIndexVersionCleanupSelection(indexVersionId: string, checked: boolean): void {
  const next = new Set(selectedCleanupIndexVersionIds.value);
  if (checked) {
    next.add(indexVersionId);
  } else {
    next.delete(indexVersionId);
  }
  selectedCleanupIndexVersionIds.value = Array.from(next);
  if (selectedCleanupIndexVersionIds.value.length === 0) {
    documentIndexForm.confirmedCleanup = false;
  }
}

function onIndexVersionCleanupSelectionToggle(indexVersionId: string, event: Event): void {
  toggleIndexVersionCleanupSelection(indexVersionId, (event.target as HTMLInputElement).checked);
}

function toggleAllIndexVersionsForCleanup(checked: boolean): void {
  selectedCleanupIndexVersionIds.value = checked
    ? cleanupEligibleIndexVersions.value.map((version) => version.id)
    : [];
  if (!checked) {
    documentIndexForm.confirmedCleanup = false;
  }
}

function onAllIndexVersionsForCleanupToggle(event: Event): void {
  toggleAllIndexVersionsForCleanup((event.target as HTMLInputElement).checked);
}

async function refreshDiagnosticsState(): Promise<void> {
  if (!canLoadDiagnostics.value && !canLoadIndexOps.value) {
    queryLogs.value = [];
    modelCallLogs.value = [];
    indexHealth.value = [];
    clearPaginationState(indexHealthPagination);
    indexCollectionSnapshots.value = [];
    clearPaginationState(indexSnapshotPagination);
    selectedQueryLog.value = null;
    diagnosticsFeedback.value = {
      tone: "error",
      message: "当前账号缺少 audit:read 和 document:index，无法查看查询诊断或索引运维。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  diagnosticsFeedback.value = null;
  const tasks: Promise<void>[] = [];
  if (canLoadDiagnostics.value) {
    tasks.push(refreshQueryLogs(accessToken), refreshModelCallLogs(accessToken));
  } else {
    queryLogs.value = [];
    modelCallLogs.value = [];
    selectedQueryLog.value = null;
    selectedModelCallLog.value = null;
    modelCallLogDetailModalOpen.value = false;
  }
  if (canLoadIndexOps.value) {
    tasks.push(refreshIndexHealth(accessToken));
  } else {
    indexHealth.value = [];
    clearPaginationState(indexHealthPagination);
    indexCollectionSnapshots.value = [];
    clearPaginationState(indexSnapshotPagination);
  }
  await Promise.all(tasks);
}

function syncIndexCollectionSelection(): void {
  const selected = indexCollectionOpsForm.selectedCollectionName;
  if (selected && indexHealth.value.some((item) => item.collection_name === selected)) {
    return;
  }
  indexCollectionOpsForm.selectedCollectionName = indexHealth.value[0]?.collection_name ?? "";
  clearPaginationState(indexSnapshotPagination);
  indexCollectionOpsForm.confirmedSnapshot = false;
  indexCollectionOpsForm.confirmedRestore = false;
  indexCollectionOpsForm.confirmedRebuild = false;
}

async function refreshIndexHealth(existingAccessToken?: string): Promise<void> {
  if (!canLoadIndexOps.value) {
    indexHealth.value = [];
    clearPaginationState(indexHealthPagination);
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.loadingIndexHealth = true;
  try {
    const response = await getAdminIndexHealth(accessToken, {
      page: indexHealthPagination.page,
      page_size: indexHealthPagination.pageSize,
    });
    indexHealth.value = response.data;
    syncPaginationState(indexHealthPagination, response.pagination);
    if (indexHealth.value.length === 0 && indexHealthPagination.total > 0 && indexHealthPagination.page > 1) {
      indexHealthPagination.page = paginationTotalPages(indexHealthPagination);
      await refreshIndexHealth(accessToken);
      return;
    }
    diagnosticsFeedback.value = null;
    syncIndexCollectionSelection();
    if (indexCollectionOpsForm.selectedCollectionName) {
      await refreshIndexCollectionSnapshots(accessToken);
    } else {
      indexCollectionSnapshots.value = [];
      clearPaginationState(indexSnapshotPagination);
    }
  } catch (error) {
    indexHealth.value = [];
    clearPaginationState(indexHealthPagination);
    indexCollectionSnapshots.value = [];
    clearPaginationState(indexSnapshotPagination);
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取索引运维诊断失败"),
    };
  } finally {
    diagnosticsBusy.loadingIndexHealth = false;
  }
}

async function refreshIndexCollectionSnapshots(existingAccessToken?: string): Promise<void> {
  if (!canLoadIndexOps.value || !indexCollectionOpsForm.selectedCollectionName) {
    indexCollectionSnapshots.value = [];
    clearPaginationState(indexSnapshotPagination);
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.loadingIndexSnapshots = true;
  try {
    const response = await listAdminIndexCollectionSnapshots(
      indexCollectionOpsForm.selectedCollectionName,
      accessToken,
      {
        page: indexSnapshotPagination.page,
        page_size: indexSnapshotPagination.pageSize,
      },
    );
    indexCollectionSnapshots.value = response.data;
    syncPaginationState(indexSnapshotPagination, response.pagination);
    if (
      indexCollectionSnapshots.value.length === 0 &&
      indexSnapshotPagination.total > 0 &&
      indexSnapshotPagination.page > 1
    ) {
      indexSnapshotPagination.page = paginationTotalPages(indexSnapshotPagination);
      await refreshIndexCollectionSnapshots(accessToken);
      return;
    }
    diagnosticsFeedback.value = null;
  } catch (error) {
    indexCollectionSnapshots.value = [];
    clearPaginationState(indexSnapshotPagination);
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取 collection 快照失败"),
    };
  } finally {
    diagnosticsBusy.loadingIndexSnapshots = false;
  }
}

async function onIndexCollectionSelectionChange(): Promise<void> {
  indexCollectionOpsForm.confirmedSnapshot = false;
  indexCollectionOpsForm.confirmedRestore = false;
  indexCollectionOpsForm.confirmedRebuild = false;
  clearPaginationState(indexSnapshotPagination);
  await refreshIndexCollectionSnapshots();
}

async function createSelectedIndexCollectionSnapshot(): Promise<void> {
  if (!canCreateIndexCollectionSnapshot.value) {
    diagnosticsFeedback.value = {
      tone: "error",
      message: "创建快照前必须选择 collection，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.creatingIndexSnapshot = true;
  try {
    const response = await createAdminIndexCollectionSnapshot(
      indexCollectionOpsForm.selectedCollectionName,
      accessToken,
      true,
    );
    indexCollectionOpsForm.confirmedSnapshot = false;
    indexSnapshotPagination.page = 1;
    await refreshIndexCollectionSnapshots(accessToken);
    diagnosticsFeedback.value = {
      tone: "success",
      message: `Qdrant 快照已创建：${response.data.name}`,
    };
  } catch (error) {
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建 Qdrant 快照失败"),
    };
  } finally {
    diagnosticsBusy.creatingIndexSnapshot = false;
  }
}

async function recoverSelectedIndexCollectionSnapshot(): Promise<void> {
  if (!canRecoverIndexCollectionSnapshot.value) {
    diagnosticsFeedback.value = {
      tone: "error",
      message: "恢复快照前必须填写 snapshot URL 或 file URI，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.recoveringIndexSnapshot = true;
  try {
    const response = await recoverAdminIndexCollectionSnapshot(
      indexCollectionOpsForm.selectedCollectionName,
      {
        location: indexCollectionOpsForm.snapshotLocation.trim(),
        priority: indexCollectionOpsForm.recoverPriority,
        checksum: indexCollectionOpsForm.snapshotChecksum.trim() || null,
      },
      accessToken,
      true,
    );
    indexCollectionOpsForm.confirmedRestore = false;
    await refreshIndexHealth(accessToken);
    diagnosticsFeedback.value = {
      tone: "success",
      message: `Qdrant 快照恢复已提交：${response.data.result === false ? "未完成" : "已接受"}`,
    };
  } catch (error) {
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "恢复 Qdrant 快照失败"),
    };
  } finally {
    diagnosticsBusy.recoveringIndexSnapshot = false;
  }
}

async function rebuildSelectedIndexCollection(): Promise<void> {
  if (!canRebuildIndexCollection.value) {
    diagnosticsFeedback.value = {
      tone: "error",
      message: "重建 collection 索引前必须选择 collection，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.rebuildingIndexCollection = true;
  try {
    const response = await createAdminIndexCollectionRebuildJob(
      indexCollectionOpsForm.selectedCollectionName,
      accessToken,
      true,
    );
    indexCollectionOpsForm.confirmedRebuild = false;
    await refreshIndexHealth(accessToken);
    diagnosticsFeedback.value = {
      tone: "success",
      message: `Collection 重建索引任务已创建：${response.data.job_id ?? "-"}`,
    };
  } catch (error) {
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建 collection 重建索引任务失败"),
    };
  } finally {
    diagnosticsBusy.rebuildingIndexCollection = false;
  }
}

async function refreshQueryLogs(existingAccessToken?: string): Promise<void> {
  if (!canLoadDiagnostics.value) {
    queryLogs.value = [];
    clearPaginationState(queryLogPagination);
    selectedQueryLog.value = null;
    queryLogDetailModalOpen.value = false;
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.loadingQueryLogs = true;
  try {
    const response = await listQueryLogs(accessToken, {
      page: queryLogPagination.page,
      page_size: queryLogPagination.pageSize,
      user_id: queryLogSearchForm.userId.trim() || undefined,
      kb_id: queryLogSearchForm.kbId.trim() || undefined,
      status: queryLogSearchForm.status || undefined,
      degraded: parseBooleanFilter(queryLogSearchForm.degraded),
      degrade_reason: queryLogSearchForm.degradeReason.trim() || undefined,
      request_id: queryLogSearchForm.requestId.trim() || undefined,
      trace_id: queryLogSearchForm.traceId.trim() || undefined,
      error_code: queryLogSearchForm.errorCode.trim() || undefined,
    });
    queryLogs.value = response.data;
    syncPaginationState(queryLogPagination, response.pagination);
    if (
      selectedQueryLog.value &&
      !queryLogs.value.some((log) => log.id === selectedQueryLog.value?.id)
    ) {
      selectedQueryLog.value = null;
      queryLogDetailModalOpen.value = false;
    }
    diagnosticsFeedback.value = null;
  } catch (error) {
    queryLogs.value = [];
    clearPaginationState(queryLogPagination);
    selectedQueryLog.value = null;
    queryLogDetailModalOpen.value = false;
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取查询日志失败"),
    };
  } finally {
    diagnosticsBusy.loadingQueryLogs = false;
  }
}

async function refreshModelCallLogs(existingAccessToken?: string): Promise<void> {
  if (!canLoadDiagnostics.value) {
    modelCallLogs.value = [];
    clearPaginationState(modelCallLogPagination);
    selectedModelCallLog.value = null;
    modelCallLogDetailModalOpen.value = false;
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }

  diagnosticsBusy.loadingModelCallLogs = true;
  try {
    const response = await listModelCallLogs(accessToken, {
      page: modelCallLogPagination.page,
      page_size: modelCallLogPagination.pageSize,
      model: modelCallSearchForm.model.trim() || undefined,
      model_type: modelCallSearchForm.modelType.trim() || undefined,
      caller: modelCallSearchForm.caller.trim() || undefined,
      status: modelCallSearchForm.status || undefined,
      degraded: parseBooleanFilter(modelCallSearchForm.degraded),
      request_id: modelCallSearchForm.requestId.trim() || undefined,
      trace_id: modelCallSearchForm.traceId.trim() || undefined,
      error_code: modelCallSearchForm.errorCode.trim() || undefined,
    });
    modelCallLogs.value = response.data;
    syncPaginationState(modelCallLogPagination, response.pagination);
    if (
      selectedModelCallLog.value &&
      !modelCallLogs.value.some((log) => log.id === selectedModelCallLog.value?.id)
    ) {
      selectedModelCallLog.value = null;
      modelCallLogDetailModalOpen.value = false;
    }
    diagnosticsFeedback.value = null;
  } catch (error) {
    modelCallLogs.value = [];
    clearPaginationState(modelCallLogPagination);
    selectedModelCallLog.value = null;
    modelCallLogDetailModalOpen.value = false;
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取模型调用日志失败"),
    };
  } finally {
    diagnosticsBusy.loadingModelCallLogs = false;
  }
}

async function selectQueryLog(queryLogId: string): Promise<void> {
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }
  diagnosticsBusy.loadingQueryDetail = true;
  try {
    const response = await getQueryLog(queryLogId, accessToken);
    selectedQueryLog.value = response.data;
    queryLogDetailModalOpen.value = true;
    modelCallSearchForm.traceId = response.data.trace_id;
    modelCallSearchForm.requestId = "";
    modelCallSearchForm.model = "";
    modelCallSearchForm.modelType = "";
    modelCallSearchForm.caller = "";
    modelCallSearchForm.status = "";
    modelCallSearchForm.degraded = "";
    modelCallSearchForm.errorCode = "";
    modelCallLogPagination.page = 1;
    await refreshModelCallLogs(accessToken);
  } catch (error) {
    selectedQueryLog.value = null;
    queryLogDetailModalOpen.value = false;
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取查询日志详情失败"),
    };
  } finally {
    diagnosticsBusy.loadingQueryDetail = false;
  }
}

function closeQueryLogDetailModal(): void {
  queryLogDetailModalOpen.value = false;
}

async function openModelCallLogDetail(log: ModelCallLogListItemData): Promise<void> {
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }
  diagnosticsBusy.loadingModelCallDetail = true;
  try {
    const response = await getModelCallLog(log.id, accessToken);
    selectedModelCallLog.value = response.data;
    modelCallLogDetailModalOpen.value = true;
    diagnosticsFeedback.value = null;
  } catch (error) {
    selectedModelCallLog.value = null;
    modelCallLogDetailModalOpen.value = false;
    diagnosticsFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取模型调用详情失败"),
    };
  } finally {
    diagnosticsBusy.loadingModelCallDetail = false;
  }
}

function closeModelCallLogDetailModal(): void {
  modelCallLogDetailModalOpen.value = false;
}

async function selectAdminUser(userId: string): Promise<void> {
  selectedAdminUserId.value = userId;
  selectedAdminUserDetail.value = null;
  clearPaginationState(selectedUserDepartmentPagination);
  clearPaginationState(selectedUserRoleBindingPagination);
  userDangerForm.confirmedDelete = false;
  passwordResetForm.newPassword = "";
  passwordResetForm.passwordConfirm = "";
  passwordResetForm.confirmed = false;
  userDepartmentForm.confirmedReplacePrimary = false;
  try {
    await refreshSelectedAdminUserDetail();
    selectedUserDepartments.value = selectedAdminUser.value?.departments ?? [];
    syncSelectedUserDepartmentForm();
    roleBindingForm.confirmedRemoveAdmin = false;
    await refreshSelectedUserDepartments();
    await refreshSelectedUserRoleBindings();
    syncUserEditForm();
  } catch (error) {
    selectedUserDepartments.value = selectedAdminUser.value?.departments ?? [];
    selectedUserRoleBindings.value = [];
    syncSelectedUserDepartmentForm();
    syncUserEditForm();
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取用户部门或角色绑定失败"),
    };
  }
}

async function refreshSelectedAdminUserDetail(existingAccessToken?: string): Promise<void> {
  if (!selectedAdminUserId.value) {
    selectedAdminUserDetail.value = null;
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await getAdminUser(selectedAdminUserId.value, accessToken);
  selectedAdminUserDetail.value = response.data;
}

function canAccessAdminTab(tab: ActiveAdminTab): boolean {
  if (tab === "config") {
    return canReadConfig.value || canManageConfig.value;
  }
  if (tab === "departments") {
    return canLoadDepartmentAdmin.value;
  }
  if (tab === "users") {
    return canLoadUserAdmin.value;
  }
  if (tab === "knowledge") {
    return canLoadImportAdmin.value;
  }
  if (tab === "diagnostics") {
    return canLoadDiagnostics.value || canLoadIndexOps.value;
  }
  return false;
}

function ensureVisibleAdminTab(): void {
  if (canAccessAdminTab(selectedAdminTab.value)) {
    return;
  }
  selectedAdminTab.value = visibleAdminTabs.value[0]?.key ?? "config";
}

function canAccessAdminPortal(): boolean {
  return adminTabDefinitions.value.some((item) => canAccessAdminTab(item.key));
}

function isAdminPortalForbidden(error: unknown): boolean {
  return (
    error instanceof ApiRequestError &&
    error.payload?.error_code === "AUTH_ADMIN_PORTAL_FORBIDDEN"
  );
}

async function rejectAdminPortalLogin(accessToken: string): Promise<void> {
  try {
    await deleteCurrentSession(accessToken);
  } catch {
    // The local admin session must still be cleared even if server-side revocation fails.
  }
  clearAuthSession();
  authFeedback.value = {
    tone: "error",
    message: "当前账号仅具备普通用户权限，不能登录管理后台。",
  };
}

async function refreshSelectedAdminTabState(): Promise<void> {
  if (!canAccessAdminTab(selectedAdminTab.value)) {
    return;
  }
  if (selectedAdminTab.value === "departments") {
    await refreshDepartmentAdminState();
  } else if (selectedAdminTab.value === "users") {
    await refreshUserRoleAdminState();
  } else if (selectedAdminTab.value === "knowledge") {
    await refreshKnowledgeBaseAdminState();
  } else if (selectedAdminTab.value === "diagnostics") {
    await refreshDiagnosticsState();
  } else if (selectedAdminTab.value === "config") {
    await refreshConfigAdminState();
  }
}

function switchAdminTab(tab: ActiveAdminTab): void {
  if (!canAccessAdminTab(tab)) {
    ensureVisibleAdminTab();
    return;
  }
  selectedAdminTab.value = tab;
  if (tab !== "knowledge") {
    documentManagerModalOpen.value = false;
  }
  void refreshSelectedAdminTabState();
}

function syncKnowledgeBaseCreateOwnerDefault(): void {
  if (
    knowledgeBaseCreateForm.ownerDepartmentId &&
    activeDepartments.value.some((department) => department.id === knowledgeBaseCreateForm.ownerDepartmentId)
  ) {
    return;
  }
  const defaultDepartment =
    activeDepartments.value.find((department) => department.is_default) ??
    currentUser.value?.departments.find((department) => department.status === "active") ??
    activeDepartments.value[0];
  knowledgeBaseCreateForm.ownerDepartmentId = defaultDepartment?.id ?? knowledgeBaseCreateForm.ownerDepartmentId;
  knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId =
    knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId ||
    knowledgeBaseCreateForm.ownerDepartmentId;
}

function syncKnowledgeBaseEditForm(): void {
  const knowledgeBase =
    selectedKnowledgeBaseDetail.value?.id === selectedKnowledgeBaseId.value
      ? selectedKnowledgeBaseDetail.value
      : null;
  knowledgeBaseEditForm.name = knowledgeBase?.name ?? "";
  knowledgeBaseEditForm.status = knowledgeBase?.status ?? "active";
  knowledgeBaseEditForm.kbVisibility = knowledgeBase?.kb_visibility ?? "enterprise";
  knowledgeBaseEditForm.defaultDocumentVisibility =
    knowledgeBase?.default_document_visibility ?? "department";
  knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId =
    knowledgeBase?.default_document_owner_department_id ?? "";
  knowledgeBaseEditForm.configScopeId = knowledgeBase?.config_scope_id ?? "";
  knowledgeBaseEditForm.confirmedVisibilityExpand = false;
}

function syncKnowledgeBasePermissionForm(): void {
  const knowledgeBase =
    selectedKnowledgeBaseDetail.value?.id === selectedKnowledgeBaseId.value
      ? selectedKnowledgeBaseDetail.value
      : null;
  knowledgeBasePermissionForm.kbVisibility = knowledgeBase?.kb_visibility ?? "enterprise";
  knowledgeBasePermissionForm.defaultDocumentVisibility =
    knowledgeBase?.default_document_visibility ?? "department";
  knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId =
    knowledgeBase?.default_document_owner_department_id ?? knowledgeBase?.owner_department_id ?? "";
  knowledgeBasePermissionForm.accessDepartmentIds = knowledgeBase
    ? queryDepartmentIdsForKnowledgeBase(knowledgeBase)
    : [];
  knowledgeBasePermissionForm.confirmedReplace = false;
}

function syncFolderEditForm(): void {
  const folder = selectedFolder.value;
  folderEditForm.name = folder?.name ?? "";
  folderEditForm.parentId = folder?.parent_id ?? "";
  folderEditForm.status = folder?.status ?? "active";
}

function syncDocumentPermissionForm(): void {
  const document = selectedAdminDocument.value;
  documentPermissionForm.visibility = document?.visibility ?? "department";
  documentPermissionForm.ownerDepartmentId = document?.owner_department_id ?? "";
  documentPermissionForm.confirmedReplace = false;
}

function resetKnowledgeBaseCreateForm(): void {
  knowledgeBaseCreateForm.name = "";
  knowledgeBaseCreateForm.kbVisibility = "enterprise";
  knowledgeBaseCreateForm.defaultDocumentVisibility = "department";
  knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId = "";
  knowledgeBaseCreateForm.accessDepartmentIds = [];
  knowledgeBaseCreateForm.configScopeId = "";
  knowledgeBaseCreateForm.confirmedEnterpriseVisibility = false;
  syncKnowledgeBaseCreateOwnerDefault();
}

function openCreateKnowledgeBaseModal(): void {
  resetKnowledgeBaseCreateForm();
  importAdminFeedback.value = null;
  knowledgeBaseModalMode.value = "create";
}

async function openEditKnowledgeBaseModal(knowledgeBase: AdminKnowledgeBaseListItemData): Promise<void> {
  await selectKnowledgeBase(knowledgeBase.id);
  knowledgeBaseModalMode.value = "edit";
  syncKnowledgeBaseEditForm();
}

async function openDeleteKnowledgeBaseModal(knowledgeBase: AdminKnowledgeBaseListItemData): Promise<void> {
  knowledgeBaseDangerForm.confirmedDelete = false;
  await selectKnowledgeBase(knowledgeBase.id);
  knowledgeBaseModalMode.value = "delete";
}

async function openKnowledgeBasePermissionsModal(knowledgeBase: AdminKnowledgeBaseListItemData): Promise<void> {
  await selectKnowledgeBase(knowledgeBase.id);
  knowledgeBaseModalMode.value = "permissions";
  syncKnowledgeBasePermissionForm();
}

async function openRebuildKnowledgeBaseIndexModal(
  knowledgeBase: AdminKnowledgeBaseListItemData,
): Promise<void> {
  knowledgeBaseIndexForm.confirmedRebuild = false;
  await selectKnowledgeBase(knowledgeBase.id);
  knowledgeBaseModalMode.value = "rebuildIndex";
}

async function openKnowledgeBaseDocumentManagerModal(
  knowledgeBase: AdminKnowledgeBaseListItemData,
): Promise<void> {
  importAdminFeedback.value = null;
  await selectKnowledgeBase(knowledgeBase.id);
  documentManagerModalOpen.value = true;
}

function closeKnowledgeBaseDocumentManagerModal(): void {
  documentManagerModalOpen.value = false;
  if (documentModalMode.value === "details") {
    documentModalMode.value = null;
  }
}

async function openUploadKnowledgeBaseModal(knowledgeBase: AdminKnowledgeBaseListItemData): Promise<void> {
  await selectKnowledgeBase(knowledgeBase.id);
  knowledgeBaseModalMode.value = "upload";
  importUploadForm.kbId = knowledgeBase.id;
  importUploadForm.folderId =
    selectedFolderId.value && activeFolders.value.some((folder) => folder.id === selectedFolderId.value)
      ? selectedFolderId.value
      : "";
  importUploadForm.visibility = knowledgeBase.default_document_visibility;
  importUploadForm.idempotencyKey = "";
  clearImportFiles();
}

function closeKnowledgeBaseModal(): void {
  knowledgeBaseModalMode.value = null;
  knowledgeBaseDangerForm.confirmedDelete = false;
  knowledgeBaseCreateForm.confirmedEnterpriseVisibility = false;
  knowledgeBaseEditForm.confirmedVisibilityExpand = false;
  knowledgeBasePermissionForm.confirmedReplace = false;
  knowledgeBaseIndexForm.confirmedRebuild = false;
}

function ensureImportKnowledgeBaseSelection(): void {
  if (
    importUploadForm.kbId &&
    activeKnowledgeBases.value.some((knowledgeBase) => knowledgeBase.id === importUploadForm.kbId)
  ) {
    return;
  }
  importUploadForm.kbId = activeKnowledgeBases.value[0]?.id ?? importUploadForm.kbId;
}

function openCreateFolderModal(): void {
  if (!selectedKnowledgeBase.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请先选择知识库。",
    };
    return;
  }
  folderCreateForm.name = "";
  folderCreateForm.parentId =
    selectedFolderId.value && activeFolders.value.some((folder) => folder.id === selectedFolderId.value)
      ? selectedFolderId.value
      : "";
  importAdminFeedback.value = null;
  folderModalMode.value = "create";
}

function openEditFolderModal(folder: AdminFolderData): void {
  selectedFolderId.value = folder.id;
  folderDangerForm.confirmedDelete = false;
  syncFolderEditForm();
  folderModalMode.value = "edit";
}

function openDeleteFolderModal(folder: AdminFolderData): void {
  selectedFolderId.value = folder.id;
  folderDangerForm.confirmedDelete = false;
  syncFolderEditForm();
  folderModalMode.value = "delete";
}

function closeFolderModal(): void {
  folderModalMode.value = null;
  folderDangerForm.confirmedDelete = false;
}

function onImportFilesChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectedImportFiles.value = Array.from(input.files ?? []);
}

function clearImportFiles(): void {
  selectedImportFiles.value = [];
  importFileInputKey.value += 1;
}

async function submitDocumentUpload(): Promise<void> {
  if (importUploadPermissionParentConflict.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: importUploadPermissionParentConflict.value,
    };
    return;
  }
  if (!canUploadImportFiles.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: !canImportDocuments.value
        ? "当前账号缺少 document:import，不能上传文档。"
        : "请选择目标知识库和至少一个文件。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.uploading = true;
  try {
    const response = await uploadKnowledgeBaseDocuments(
      importUploadForm.kbId.trim(),
      {
        files: selectedImportFiles.value,
        visibility: importUploadForm.visibility,
        owner_department_id:
          selectedImportKnowledgeBase.value?.default_document_owner_department_id,
        folder_id: importUploadForm.folderId || undefined,
        idempotency_key: importUploadForm.idempotencyKey.trim() || undefined,
      },
      accessToken,
    );
    const listItem = importJobListItemFromDetail(response.data);
    adminImportJobs.value = [
      listItem,
      ...adminImportJobs.value.filter((job) => job.id !== listItem.id),
    ];
    clearImportFiles();
    importUploadForm.idempotencyKey = "";
    if (canReadImportJobs.value) {
      await refreshKnowledgeBaseAdminState();
    }
    importAdminFeedback.value = {
      tone: "success",
      message: `上传任务已创建：${response.data.id}`,
    };
    closeKnowledgeBaseModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "上传文档失败"),
    };
  } finally {
    importAdminBusy.uploading = false;
  }
}

async function submitCreateKnowledgeBase(): Promise<void> {
  if (!canCreateKnowledgeBase.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请填写知识库名称和所属部门。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.creating = true;
  try {
    const response = await createAdminKnowledgeBase(
      {
        name: knowledgeBaseCreateForm.name.trim(),
        owner_department_id: knowledgeBaseCreateForm.ownerDepartmentId.trim(),
        kb_visibility: knowledgeBaseCreateForm.kbVisibility,
        default_document_visibility: knowledgeBaseCreateForm.defaultDocumentVisibility,
        default_document_owner_department_id:
          knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId.trim(),
        access_rules: buildDepartmentKnowledgeBaseAccessRules(
          knowledgeBaseCreateForm.kbVisibility === "enterprise"
            ? []
            : [
                ...knowledgeBaseCreateForm.accessDepartmentIds,
                knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId.trim(),
              ],
        ),
        config_scope_id: knowledgeBaseCreateForm.configScopeId.trim() || null,
      },
      accessToken,
      knowledgeBaseCreateForm.confirmedEnterpriseVisibility,
    );
    upsertKnowledgeBase(response.data);
    selectedKnowledgeBaseId.value = response.data.id;
    importSearchForm.kbId = response.data.id;
    await refreshKnowledgeBaseAdminState();
    importAdminFeedback.value = {
      tone: "success",
      message: "知识库已创建。",
    };
    closeKnowledgeBaseModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建知识库失败"),
    };
  } finally {
    importAdminBusy.creating = false;
  }
}

async function submitCreateFolder(): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canCreateFolder.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请选择知识库并填写文件夹名称。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.managingFolder = true;
  try {
    const response = await createAdminFolder(
      knowledgeBase.id,
      {
        name: folderCreateForm.name.trim(),
        parent_id: folderCreateForm.parentId || null,
      },
      accessToken,
    );
    selectedFolderId.value = response.data.id;
    folderPagination.page = 1;
    await refreshSelectedKnowledgeBaseFolders(accessToken);
    importAdminFeedback.value = {
      tone: "success",
      message: "文件夹已创建。",
    };
    closeFolderModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建文件夹失败"),
    };
  } finally {
    importAdminBusy.managingFolder = false;
  }
}

async function submitPatchFolder(): Promise<void> {
  const folder = selectedFolder.value;
  if (!folder || !canUpdateSelectedFolder.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请选择文件夹并填写文件夹名称。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.managingFolder = true;
  try {
    const response = await patchAdminFolder(
      folder.id,
      {
        name: folderEditForm.name.trim(),
        parent_id: folderEditForm.parentId || null,
        status: folderEditForm.status,
      },
      accessToken,
    );
    selectedFolderId.value = response.data.id;
    await refreshSelectedKnowledgeBaseFolders(accessToken);
    importAdminFeedback.value = {
      tone: "success",
      message: "文件夹已更新。",
    };
    closeFolderModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新文件夹失败"),
    };
  } finally {
    importAdminBusy.managingFolder = false;
  }
}

async function deleteSelectedFolder(): Promise<void> {
  const folder = selectedFolder.value;
  if (!folder || !folderDangerForm.confirmedDelete) {
    importAdminFeedback.value = {
      tone: "error",
      message: "删除文件夹前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.managingFolder = true;
  try {
    await deleteAdminFolder(folder.id, accessToken, true);
    selectedFolderId.value = "";
    importUploadForm.folderId = importUploadForm.folderId === folder.id ? "" : importUploadForm.folderId;
    await refreshSelectedKnowledgeBaseFolders(accessToken);
    await refreshSelectedKnowledgeBaseDocuments(accessToken);
    importAdminFeedback.value = {
      tone: "success",
      message: "文件夹已删除，并已写入访问阻断。",
    };
    closeFolderModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "删除文件夹失败"),
    };
  } finally {
    importAdminBusy.managingFolder = false;
  }
}

async function selectKnowledgeBase(kbId: string): Promise<void> {
  selectedKnowledgeBaseId.value = kbId;
  selectedKnowledgeBaseDetail.value = null;
  selectedFolderId.value = "";
  selectedDocumentId.value = "";
  clearPaginationState(folderPagination);
  clearPaginationState(documentPagination);
  clearSelectedDocumentDetails();
  clearSelectedDocumentMetadata();
  clearBatchDocumentSelection();
  knowledgeBaseDangerForm.confirmedDelete = false;
  folderDangerForm.confirmedDelete = false;
  syncKnowledgeBaseEditForm();
  syncKnowledgeBasePermissionForm();
  syncFolderEditForm();

  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }
  try {
    if (canManageKnowledgeBases.value) {
      await refreshSelectedKnowledgeBaseDetail(accessToken);
    }
    await refreshSelectedKnowledgeBaseFolders(accessToken);
    await refreshSelectedKnowledgeBaseDocuments(accessToken);
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取知识库详情、文件夹或文档失败"),
    };
  }
}

async function submitPatchKnowledgeBase(): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canUpdateSelectedKnowledgeBase.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请选择知识库并填写知识库名称。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.updating = true;
  try {
    const response = await patchAdminKnowledgeBase(
      knowledgeBase.id,
      {
        name: knowledgeBaseEditForm.name.trim(),
        status: knowledgeBaseEditForm.status,
        kb_visibility: knowledgeBaseEditForm.kbVisibility,
        default_document_visibility: knowledgeBaseEditForm.defaultDocumentVisibility,
        default_document_owner_department_id:
          knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId.trim(),
        config_scope_id: knowledgeBaseEditForm.configScopeId.trim() || null,
      },
      accessToken,
      knowledgeBaseEditForm.confirmedVisibilityExpand,
    );
    upsertKnowledgeBase(response.data);
    selectedKnowledgeBaseId.value = response.data.id;
    await refreshKnowledgeBaseAdminState();
    importAdminFeedback.value = {
      tone: "success",
      message: "知识库已更新。",
    };
    closeKnowledgeBaseModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新知识库失败"),
    };
  } finally {
    importAdminBusy.updating = false;
  }
}

async function submitKnowledgeBasePermissions(): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canReplaceSelectedKnowledgeBasePermissions.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请选择知识库、填写默认文档所属部门并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.updatingPermissions = true;
  try {
    await putKnowledgeBasePermissions(
      knowledgeBase.id,
      {
        kb_visibility: knowledgeBasePermissionForm.kbVisibility,
        default_document_visibility: knowledgeBasePermissionForm.defaultDocumentVisibility,
        default_document_owner_department_id:
          knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId.trim(),
        access_rules: buildDepartmentKnowledgeBaseAccessRules(
          knowledgeBasePermissionForm.kbVisibility === "enterprise"
            ? []
            : [
                ...knowledgeBasePermissionForm.accessDepartmentIds,
                knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId.trim(),
              ],
        ),
      },
      accessToken,
      true,
    );
    await refreshKnowledgeBaseAdminState();
    importAdminFeedback.value = {
      tone: "success",
      message: "知识库权限策略已更新。",
    };
    closeKnowledgeBaseModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新知识库权限失败"),
    };
  } finally {
    importAdminBusy.updatingPermissions = false;
  }
}

async function deleteSelectedKnowledgeBase(): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !knowledgeBaseDangerForm.confirmedDelete) {
    importAdminFeedback.value = {
      tone: "error",
      message: "删除知识库前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.deleting = true;
  try {
    await deleteAdminKnowledgeBase(knowledgeBase.id, accessToken, true);
    selectedKnowledgeBaseId.value = "";
    knowledgeBaseDangerForm.confirmedDelete = false;
    await refreshKnowledgeBaseAdminState();
    importAdminFeedback.value = {
      tone: "success",
      message: "知识库已删除，并已创建索引清理任务。",
    };
    closeKnowledgeBaseModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "删除知识库失败"),
    };
  } finally {
    importAdminBusy.deleting = false;
  }
}

async function rebuildSelectedKnowledgeBaseIndex(): Promise<void> {
  const knowledgeBase = selectedKnowledgeBase.value;
  if (!knowledgeBase || !canRebuildSelectedKnowledgeBaseIndex.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "重建知识库索引前必须选择 active 知识库，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.rebuildingIndex = true;
  try {
    const response = await createAdminIndexJob({ kb_id: knowledgeBase.id }, accessToken, true);
    knowledgeBaseIndexForm.confirmedRebuild = false;
    await refreshSelectedKnowledgeBaseDocuments(accessToken);
    if (canReadImportJobs.value) {
      importJobPagination.page = 1;
      await refreshImportJobList(accessToken, knowledgeBase.id);
    }
    if (canLoadIndexOps.value) {
      await refreshIndexHealth(accessToken);
    }
    importAdminFeedback.value = {
      tone: "success",
      message: `知识库索引重建任务已创建：${response.data.job_id ?? "-"}`,
    };
    closeKnowledgeBaseModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建知识库索引重建任务失败"),
    };
  } finally {
    importAdminBusy.rebuildingIndex = false;
  }
}

function knowledgeBaseListItemFromDetail(
  knowledgeBase: AdminKnowledgeBaseData,
): AdminKnowledgeBaseListItemData {
  return {
    id: knowledgeBase.id,
    name: knowledgeBase.name,
    status: knowledgeBase.status,
    owner_department_id: knowledgeBase.owner_department_id,
    owner_department_name: knowledgeBase.owner_department?.name ?? null,
    kb_visibility: knowledgeBase.kb_visibility,
    default_document_visibility: knowledgeBase.default_document_visibility,
    default_document_owner_department_id: knowledgeBase.default_document_owner_department_id,
    default_document_owner_department_name:
      knowledgeBase.default_document_owner_department?.name ?? null,
  };
}

function upsertKnowledgeBase(knowledgeBase: AdminKnowledgeBaseData): void {
  const index = adminKnowledgeBases.value.findIndex((item) => item.id === knowledgeBase.id);
  const listItem = knowledgeBaseListItemFromDetail(knowledgeBase);
  if (index >= 0) {
    adminKnowledgeBases.value[index] = listItem;
  } else {
    adminKnowledgeBases.value = [listItem, ...adminKnowledgeBases.value];
  }
  const option: AdminKnowledgeBaseOptionData = {
    id: knowledgeBase.id,
    name: knowledgeBase.name,
    status: knowledgeBase.status,
  };
  const optionIndex = adminKnowledgeBaseOptions.value.findIndex(
    (item) => item.id === knowledgeBase.id,
  );
  if (option.status === "active") {
    if (optionIndex >= 0) {
      adminKnowledgeBaseOptions.value[optionIndex] = option;
    } else {
      adminKnowledgeBaseOptions.value = [option, ...adminKnowledgeBaseOptions.value];
    }
  } else if (optionIndex >= 0) {
    adminKnowledgeBaseOptions.value = adminKnowledgeBaseOptions.value.filter(
      (item) => item.id !== knowledgeBase.id,
    );
  }
}

async function openDocumentDetailsModal(document: AdminDocumentListItemData): Promise<void> {
  selectedDocumentId.value = document.id;
  selectedAdminDocumentDetail.value = null;
  clearPaginationState(documentVersionPagination);
  clearPaginationState(documentIndexVersionPagination);
  clearPaginationState(documentChunkPagination);
  syncDocumentPermissionForm();
  documentModalMode.value = "details";
  await refreshSelectedDocumentDetails();
}

async function openDocumentPermissionsModal(document: AdminDocumentListItemData): Promise<void> {
  selectedDocumentId.value = document.id;
  selectedAdminDocumentDetail.value = null;
  clearPaginationState(documentVersionPagination);
  clearPaginationState(documentIndexVersionPagination);
  clearPaginationState(documentChunkPagination);
  clearSelectedDocumentDetails();
  syncDocumentPermissionForm();
  documentModalMode.value = "permissions";
  await refreshSelectedDocumentMetadata();
}

function closeDocumentModal(): void {
  documentModalMode.value = null;
  documentPermissionForm.confirmedReplace = false;
}

async function submitDocumentPermissions(): Promise<void> {
  const document = selectedAdminDocument.value;
  if (documentPermissionParentConflict.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: documentPermissionParentConflict.value,
    };
    return;
  }
  if (!document || !canReplaceSelectedDocumentPermissions.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "请选择文档、填写所属部门并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.updatingPermissions = true;
  try {
    await putDocumentPermissions(
      document.id,
      {
        visibility: documentPermissionForm.visibility,
        owner_department_id: documentPermissionForm.ownerDepartmentId.trim(),
      },
      accessToken,
      true,
    );
    await refreshSelectedKnowledgeBaseDocuments(accessToken);
    importAdminFeedback.value = {
      tone: "success",
      message: "文档权限策略已更新。",
    };
    closeDocumentModal();
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新文档权限失败"),
    };
  } finally {
    importAdminBusy.updatingPermissions = false;
  }
}

async function rebuildSelectedDocumentIndex(): Promise<void> {
  const document = selectedAdminDocument.value;
  if (!document || !canRebuildSelectedDocumentIndex.value) {
    importAdminFeedback.value = {
      tone: "error",
      message: "重建索引前必须选择 active 文档、确认当前版本存在，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.rebuildingIndex = true;
  try {
    const response = await createAdminDocumentIndexJob(document.id, accessToken, true);
    documentIndexForm.confirmedRebuild = false;
    await refreshSelectedKnowledgeBaseDocuments(accessToken);
    if (canReadImportJobs.value) {
      importJobPagination.page = 1;
      await refreshImportJobList(accessToken);
    }
    importAdminFeedback.value = {
      tone: "success",
      message: `索引重建任务已创建：${response.data.job_id ?? "-"}`,
    };
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建索引重建任务失败"),
    };
  } finally {
    importAdminBusy.rebuildingIndex = false;
  }
}

async function rebuildSelectedDocumentsIndex(): Promise<void> {
  const documentIds = selectedBatchRebuildDocumentIds.value;
  if (!canRebuildSelectedDocumentsIndex.value || documentIds.length === 0) {
    importAdminFeedback.value = {
      tone: "error",
      message: "批量重建索引前必须选择可重建文档，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.rebuildingBatchIndex = true;
  try {
    const response = await createAdminIndexJob({ document_ids: documentIds }, accessToken, true);
    clearBatchDocumentSelection();
    await refreshSelectedKnowledgeBaseDocuments(accessToken);
    if (canReadImportJobs.value) {
      importJobPagination.page = 1;
      await refreshImportJobList(accessToken, selectedKnowledgeBase.value?.id);
    }
    if (canLoadIndexOps.value) {
      await refreshIndexHealth(accessToken);
    }
    importAdminFeedback.value = {
      tone: "success",
      message: `已为 ${documentIds.length} 个文档创建批量索引重建任务：${response.data.job_id ?? "-"}`,
    };
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建批量索引重建任务失败"),
    };
  } finally {
    importAdminBusy.rebuildingBatchIndex = false;
  }
}

async function cleanupSelectedIndexVersions(): Promise<void> {
  const indexVersionIds = selectedCleanupPendingDeleteIndexVersionIds.value;
  if (!canCleanupSelectedIndexVersions.value || indexVersionIds.length === 0) {
    importAdminFeedback.value = {
      tone: "error",
      message: "清理索引前必须选择 pending_delete 索引版本，并勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  importAdminBusy.cleaningIndexVersions = true;
  try {
    const response = await createAdminIndexVersionCleanupJob(
      { index_version_ids: indexVersionIds },
      accessToken,
      true,
    );
    clearIndexVersionCleanupSelection();
    await refreshSelectedDocumentIndexVersions(accessToken);
    if (canReadImportJobs.value) {
      importJobPagination.page = 1;
      await refreshImportJobList(accessToken, selectedKnowledgeBase.value?.id);
    }
    if (canLoadIndexOps.value) {
      await refreshIndexHealth(accessToken);
    }
    importAdminFeedback.value = {
      tone: "success",
      message: `已创建 ${indexVersionIds.length} 个索引版本的清理任务：${response.data.job_id ?? "-"}`,
    };
  } catch (error) {
    importAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建索引清理任务失败"),
    };
  } finally {
    importAdminBusy.cleaningIndexVersions = false;
  }
}

function toggleCreateRole(roleId: string, checked: boolean): void {
  const next = new Set(userCreateForm.roleIds);
  if (checked) {
    next.add(roleId);
  } else {
    next.delete(roleId);
  }
  userCreateForm.roleIds = Array.from(next);
}

function toggleCreateDepartment(departmentId: string, checked: boolean): void {
  const next = new Set(userCreateForm.departmentIds);
  if (checked) {
    next.add(departmentId);
  } else {
    next.delete(departmentId);
  }
  userCreateForm.departmentIds = Array.from(next);
}

function toggleSelectedUserDepartment(departmentId: string, checked: boolean): void {
  const next = new Set(userDepartmentForm.departmentIds);
  if (checked) {
    next.add(departmentId);
  } else {
    next.delete(departmentId);
  }
  userDepartmentForm.departmentIds = Array.from(next);
  if (!selectedUserPrimaryDepartmentWillChange.value) {
    userDepartmentForm.confirmedReplacePrimary = false;
  }
}

function toggleKnowledgeBaseCreateAccessDepartment(departmentId: string, checked: boolean): void {
  const next = new Set(knowledgeBaseCreateForm.accessDepartmentIds);
  if (checked) {
    next.add(departmentId);
  } else {
    next.delete(departmentId);
  }
  knowledgeBaseCreateForm.accessDepartmentIds = Array.from(next);
}

function onKnowledgeBaseCreateAccessDepartmentChange(departmentId: string, event: Event): void {
  toggleKnowledgeBaseCreateAccessDepartment(
    departmentId,
    (event.target as HTMLInputElement | null)?.checked ?? false,
  );
}

function toggleKnowledgeBasePermissionAccessDepartment(
  departmentId: string,
  checked: boolean,
): void {
  const next = new Set(knowledgeBasePermissionForm.accessDepartmentIds);
  if (checked) {
    next.add(departmentId);
  } else {
    next.delete(departmentId);
  }
  knowledgeBasePermissionForm.accessDepartmentIds = Array.from(next);
}

function onKnowledgeBasePermissionAccessDepartmentChange(
  departmentId: string,
  event: Event,
): void {
  toggleKnowledgeBasePermissionAccessDepartment(
    departmentId,
    (event.target as HTMLInputElement | null)?.checked ?? false,
  );
}

function ensureDefaultCreateDepartmentSelection(): void {
  const availableIds = new Set(createUserDepartmentOptions.value.map((department) => department.id));
  userCreateForm.departmentIds = userCreateForm.departmentIds.filter((id) => availableIds.has(id));
  if (userCreateForm.departmentIds.length > 0) {
    return;
  }
  const defaultDepartment =
    createUserDepartmentOptions.value.find((department) => department.is_primary) ??
    createUserDepartmentOptions.value.find((department) => department.is_default) ??
    createUserDepartmentOptions.value[0];
  if (defaultDepartment) {
    userCreateForm.departmentIds = [defaultDepartment.id];
  }
}

function openCreateDepartmentModal(): void {
  departmentCreateForm.code = "";
  departmentCreateForm.name = "";
  departmentAdminFeedback.value = null;
  departmentModalMode.value = "create";
}

async function openEditDepartmentModal(department: AdminDepartmentListItemData): Promise<void> {
  departmentModalMode.value = "edit";
  await selectDepartment(department.id);
}

async function openDeleteDepartmentModal(department: AdminDepartmentListItemData): Promise<void> {
  departmentDangerForm.confirmedDelete = false;
  departmentModalMode.value = "delete";
  await selectDepartment(department.id);
}

function closeDepartmentModal(): void {
  departmentModalMode.value = null;
  departmentDangerForm.confirmedDelete = false;
}

function openCreateUserModal(): void {
  resetCreateUserForm();
  ensureDefaultCreateDepartmentSelection();
  userAdminFeedback.value = null;
  userModalMode.value = "create";
}

async function openEditUserModal(user: AdminUserListItemData): Promise<void> {
  await selectAdminUser(user.id);
  userModalMode.value = "edit";
  syncUserEditForm();
}

async function openUserDepartmentsModal(user: AdminUserListItemData): Promise<void> {
  await selectAdminUser(user.id);
  userModalMode.value = "departments";
}

async function openUserRolesModal(user: AdminUserListItemData): Promise<void> {
  await selectAdminUser(user.id);
  userModalMode.value = "roles";
  if (!roleBindingForm.roleId && assignableRoles.value.length > 0) {
    roleBindingForm.roleId = assignableRoles.value[0].id;
  }
  if (!roleBindingForm.roleId || selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value)) {
    selectNextAvailableRoleBindingTarget();
  } else {
    syncRoleBindingScopeDefault();
  }
}

async function openPasswordResetModal(user: AdminUserListItemData): Promise<void> {
  await selectAdminUser(user.id);
  userModalMode.value = "password";
}

async function openDeleteUserModal(user: AdminUserListItemData): Promise<void> {
  userDangerForm.confirmedDelete = false;
  await selectAdminUser(user.id);
  userModalMode.value = "delete";
}

function closeUserModal(): void {
  userModalMode.value = null;
  userDangerForm.confirmedDelete = false;
  passwordResetForm.newPassword = "";
  passwordResetForm.passwordConfirm = "";
  passwordResetForm.confirmed = false;
  roleBindingForm.scopeId = "";
  roleBindingForm.confirmedHighRisk = false;
  roleBindingForm.confirmedRemoveAdmin = false;
}

function onRoleBindingRoleChange(roleId: string): void {
  roleBindingForm.roleId = roleId;
  roleBindingForm.confirmedHighRisk = false;
  syncRoleBindingScopeDefault();
}

function syncRoleBindingScopeDefault(): void {
  const role = selectedRoleForBinding.value;
  if (!role || role.scope_type === "enterprise") {
    roleBindingForm.scopeId = "";
    return;
  }
  const candidates =
    role.scope_type === "department" ? activeDepartments.value : activeKnowledgeBases.value;
  const currentScopeExists = candidates.some((item) => item.id === roleBindingForm.scopeId);
  if (currentScopeExists) {
    const currentKey = roleBindingKeyFromParts(role.id, role.scope_type, roleBindingForm.scopeId);
    if (!selectedUserRoleBindingKeys.value.has(currentKey)) {
      return;
    }
  }
  if (role.scope_type === "department") {
    const preferredDepartment = preferredDepartmentScopeForRole(role);
    if (preferredDepartment) {
      roleBindingForm.scopeId = preferredDepartment.id;
      return;
    }
  }
  const nextAvailableScope = candidates.find(
    (item) =>
      !selectedUserRoleBindingKeys.value.has(
        roleBindingKeyFromParts(role.id, role.scope_type, item.id),
      ),
  );
  roleBindingForm.scopeId = nextAvailableScope?.id ?? candidates[0]?.id ?? "";
}

function selectNextAvailableRoleBindingTarget(): void {
  const currentRoleId = selectedRoleForBinding.value?.id;
  const currentRole = selectedRoleForBinding.value;
  if (currentRole?.scope_type === "department") {
    const preferredDepartment = preferredDepartmentScopeForRole(currentRole);
    if (preferredDepartment) {
      roleBindingForm.confirmedHighRisk = false;
      roleBindingForm.roleId = currentRole.id;
      roleBindingForm.scopeId = preferredDepartment.id;
      return;
    }
  }
  const candidate =
    availableRoleBindingCandidates.value.find((item) => item.role.id === currentRoleId) ??
    availableRoleBindingCandidates.value[0];
  roleBindingForm.confirmedHighRisk = false;
  if (!candidate) {
    roleBindingForm.roleId = "";
    roleBindingForm.scopeId = "";
    return;
  }
  roleBindingForm.roleId = candidate.role.id;
  if (candidate.role.scope_type === "department") {
    roleBindingForm.scopeId = preferredDepartmentScopeForRole(candidate.role)?.id ?? candidate.scopeId ?? "";
    return;
  }
  roleBindingForm.scopeId = candidate.scopeId ?? "";
}

function preferredDepartmentScopeForRole(
  role: AdminAssignableRoleOptionData,
): AdminDepartmentOptionData | null {
  if (role.scope_type !== "department") {
    return null;
  }
  const activeDepartmentIds = new Set(activeDepartments.value.map((department) => department.id));
  for (const departmentId of selectedUserPreferredDepartmentIds()) {
    if (!activeDepartmentIds.has(departmentId)) {
      continue;
    }
    const bindingKey = roleBindingKeyFromParts(role.id, "department", departmentId);
    if (!selectedUserRoleBindingKeys.value.has(bindingKey)) {
      return activeDepartments.value.find((department) => department.id === departmentId) ?? null;
    }
  }
  return null;
}

function selectedUserPreferredDepartmentIds(): string[] {
  const departments = selectedUserDepartmentsForForm.value;
  const preferredIds: string[] = [];
  const primaryDepartment = departments.find((department) => department.is_primary);
  if (primaryDepartment) {
    preferredIds.push(primaryDepartment.id);
  }
  for (const department of departments) {
    if (!preferredIds.includes(department.id)) {
      preferredIds.push(department.id);
    }
  }
  return preferredIds;
}

async function submitCreateDepartment(): Promise<void> {
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  departmentAdminBusy.creating = true;
  try {
    const response = await createAdminDepartment(
      {
        code: departmentCreateForm.code.trim(),
        name: departmentCreateForm.name.trim(),
      },
      accessToken,
    );
    departmentCreateForm.code = "";
    departmentCreateForm.name = "";
    departmentSearchForm.status = "";
    selectedDepartmentId.value = response.data.id;
    upsertDepartment(response.data);
    syncDepartmentEditForm();
    ensureDefaultCreateDepartmentSelection();
    await refreshDepartmentAdminState();
    departmentAdminFeedback.value = {
      tone: "success",
      message: "部门已创建。",
    };
    closeDepartmentModal();
  } catch (error) {
    departmentAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建部门失败"),
    };
  } finally {
    departmentAdminBusy.creating = false;
  }
}

async function selectDepartment(departmentId: string): Promise<void> {
  selectedDepartmentId.value = departmentId;
  departmentDangerForm.confirmedDelete = false;
  syncDepartmentEditForm();

  const accessToken = await ensureAccessToken();
  if (!accessToken || !canReadDepartments.value) {
    return;
  }
  try {
    const response = await getAdminDepartment(departmentId, accessToken);
    upsertDepartment(response.data);
    syncDepartmentEditForm();
  } catch (error) {
    departmentAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取部门详情失败"),
    };
  }
}

async function submitPatchDepartment(): Promise<void> {
  const department = selectedDepartment.value;
  if (!department) {
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  departmentAdminBusy.updating = true;
  try {
    const response = await patchAdminDepartment(
      department.id,
      {
        name: departmentEditForm.name.trim(),
        status: departmentEditForm.status,
      },
      accessToken,
    );
    upsertDepartment(response.data);
    syncDepartmentEditForm();
    await refreshDepartmentAdminState();
    departmentAdminFeedback.value = {
      tone: "success",
      message: "部门已更新。",
    };
    closeDepartmentModal();
  } catch (error) {
    departmentAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新部门失败"),
    };
  } finally {
    departmentAdminBusy.updating = false;
  }
}

async function deleteSelectedDepartment(): Promise<void> {
  const department = selectedDepartment.value;
  if (!department || !departmentDangerForm.confirmedDelete) {
    departmentAdminFeedback.value = {
      tone: "error",
      message: "删除部门前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  departmentAdminBusy.deleting = true;
  try {
    await deleteAdminDepartment(department.id, accessToken, true);
    selectedDepartmentId.value = "";
    adminDepartmentOptions.value = adminDepartmentOptions.value.filter((item) => item.id !== department.id);
    departmentDangerForm.confirmedDelete = false;
    await refreshDepartmentAdminState();
    ensureDefaultCreateDepartmentSelection();
    departmentAdminFeedback.value = {
      tone: "success",
      message: "部门已删除。",
    };
    closeDepartmentModal();
  } catch (error) {
    departmentAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "删除部门失败"),
    };
  } finally {
    departmentAdminBusy.deleting = false;
  }
}

function syncDepartmentEditForm(): void {
  const department = selectedDepartment.value;
  departmentEditForm.name = department?.name ?? "";
  departmentEditForm.status =
    department?.status === "disabled" || department?.status === "active"
      ? department.status
      : "active";
}

function syncUserEditForm(): void {
  const user = selectedAdminUser.value;
  userEditForm.name = user?.name ?? "";
  userEditForm.status =
    user?.status === "disabled" || user?.status === "locked" || user?.status === "active"
      ? user.status
      : "active";
  userEditForm.confirmedDisableAdmin = false;
}

function upsertDepartment(department: AdminDepartmentData): void {
  const index = adminDepartments.value.findIndex((item) => item.id === department.id);
  const listItem: AdminDepartmentListItemData = {
    id: department.id,
    name: department.name,
    status: department.status,
    is_default: department.is_default,
  };
  if (index >= 0) {
    adminDepartments.value[index] = listItem;
  } else {
    adminDepartments.value = [listItem, ...adminDepartments.value];
  }
  upsertDepartmentOption(department);
}

function upsertDepartmentOption(department: AdminDepartmentData): void {
  const option: AdminDepartmentOptionData = {
    id: department.id,
    name: department.name,
    status: department.status,
    is_default: department.is_default,
  };
  const index = adminDepartmentOptions.value.findIndex((item) => item.id === department.id);
  if (index >= 0) {
    adminDepartmentOptions.value[index] = option;
    return;
  }
  if (option.status === "active") {
    adminDepartmentOptions.value = [option, ...adminDepartmentOptions.value];
  }
}

async function submitCreateAdminUser(): Promise<void> {
  if (userCreateForm.initialPassword !== userCreateForm.passwordConfirm) {
    userAdminFeedback.value = {
      tone: "error",
      message: "两次输入的初始密码不一致。",
    };
    return;
  }
  if (userCreateForm.departmentIds.length === 0) {
    userAdminFeedback.value = {
      tone: "error",
      message: "请至少选择一个归属部门。",
    };
    return;
  }
  const highRisk = selectedCreateRoles.value.some(isHighRiskAdminRole);
  if (highRisk && !userCreateForm.confirmedHighRisk) {
    userAdminFeedback.value = {
      tone: "error",
      message: "授予高风险角色前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.creating = true;
  try {
    const response = await createAdminUser(
      {
        username: userCreateForm.username.trim(),
        name: userCreateForm.name.trim(),
        initial_password: userCreateForm.initialPassword,
        department_ids: userCreateForm.departmentIds,
        role_ids: userCreateForm.roleIds,
      },
      accessToken,
      userCreateForm.confirmedHighRisk,
    );
    selectedAdminUserId.value = response.data.id;
    resetCreateUserForm();
    await refreshUserRoleAdminState();
    userAdminFeedback.value = {
      tone: "success",
      message: "用户已创建。",
    };
    closeUserModal();
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "创建用户失败"),
    };
  } finally {
    userAdminBusy.creating = false;
  }
}

async function submitPatchSelectedAdminUser(): Promise<void> {
  const user = selectedAdminUser.value;
  if (!user) {
    return;
  }
  if (!userEditForm.name.trim()) {
    userAdminFeedback.value = {
      tone: "error",
      message: "显示名不能为空。",
    };
    return;
  }
  if (
    userEditForm.status === "disabled" &&
    selectedAdminUserIsSystemAdmin.value &&
    !userEditForm.confirmedDisableAdmin
  ) {
    userAdminFeedback.value = {
      tone: "error",
      message: "禁用系统管理员前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.updating = true;
  try {
    const shouldUnlock = user.status === "locked" && userEditForm.status === "active";
    if (shouldUnlock) {
      await unlockAdminUser(user.id, accessToken);
    }
    await patchAdminUser(
      user.id,
      {
        name: userEditForm.name.trim(),
        status: shouldUnlock ? undefined : userEditForm.status,
      },
      accessToken,
      userEditForm.confirmedDisableAdmin,
    );
    await refreshUserRoleAdminState();
    syncUserEditForm();
    userAdminFeedback.value = {
      tone: "success",
      message: "用户信息已更新。",
    };
    closeUserModal();
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新用户失败"),
    };
  } finally {
    userAdminBusy.updating = false;
  }
}

async function deleteSelectedAdminUser(): Promise<void> {
  const user = selectedAdminUser.value;
  if (!user || !userDangerForm.confirmedDelete) {
    userAdminFeedback.value = {
      tone: "error",
      message: "删除用户前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.updating = true;
  try {
    await deleteAdminUser(user.id, accessToken, true);
    selectedAdminUserId.value = "";
    selectedUserRoleBindings.value = [];
    await refreshUserRoleAdminState();
    userAdminFeedback.value = {
      tone: "success",
      message: "用户已删除。",
    };
    closeUserModal();
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "删除用户失败"),
    };
  } finally {
    userAdminBusy.updating = false;
  }
}

async function saveSelectedUserDepartments(): Promise<void> {
  const user = selectedAdminUser.value;
  if (!user) {
    return;
  }
  if (userDepartmentForm.departmentIds.length === 0) {
    userAdminFeedback.value = {
      tone: "error",
      message: "请至少选择一个用户归属部门。",
    };
    return;
  }
  if (
    selectedUserPrimaryDepartmentWillChange.value &&
    !userDepartmentForm.confirmedReplacePrimary
  ) {
    userAdminFeedback.value = {
      tone: "error",
      message: "更换主部门前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.updatingDepartments = true;
  try {
    const response = await replaceAdminUserDepartments(
      user.id,
      { department_ids: userDepartmentForm.departmentIds },
      accessToken,
      userDepartmentForm.confirmedReplacePrimary,
    );
    selectedUserDepartments.value = response.data;
    syncPaginationState(selectedUserDepartmentPagination, response.pagination);
    updateSelectedAdminUserDepartments(response.data);
    await refreshSelectedAdminUserDetail(accessToken);
    syncSelectedUserDepartmentForm();
    userAdminFeedback.value = {
      tone: "success",
      message: "用户部门归属已更新。",
    };
    closeUserModal();
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "更新用户部门归属失败"),
    };
  } finally {
    userAdminBusy.updatingDepartments = false;
  }
}

async function submitPasswordReset(): Promise<void> {
  const user = selectedAdminUser.value;
  if (!user) {
    return;
  }
  if (passwordResetForm.newPassword !== passwordResetForm.passwordConfirm) {
    userAdminFeedback.value = {
      tone: "error",
      message: "两次输入的新密码不一致。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.resettingPassword = true;
  try {
    await resetAdminUserPassword(
      user.id,
      {
        new_password: passwordResetForm.newPassword,
        force_change_password: passwordResetForm.forceChangePassword,
      },
      accessToken,
      passwordResetForm.confirmed,
    );
    passwordResetForm.newPassword = "";
    passwordResetForm.passwordConfirm = "";
    passwordResetForm.confirmed = false;
    userAdminFeedback.value = {
      tone: "success",
      message: "密码已重置，相关会话已由后端吊销。",
    };
    closeUserModal();
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "重置密码失败"),
    };
  } finally {
    userAdminBusy.resettingPassword = false;
  }
}

async function addSelectedUserRoleBinding(): Promise<void> {
  const user = selectedAdminUser.value;
  const role = selectedRoleForBinding.value;
  if (!user || !role) {
    return;
  }
  if (isHighRiskAdminRole(role) && !roleBindingForm.confirmedHighRisk) {
    userAdminFeedback.value = {
      tone: "error",
      message: "授予高风险角色前必须勾选确认项。",
    };
    return;
  }
  if (role.scope_type !== "enterprise" && !roleBindingForm.scopeId) {
    userAdminFeedback.value = {
      tone: "error",
      message: role.scope_type === "department" ? "请选择部门作用域。" : "请选择知识库作用域。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.updatingRoles = true;
  try {
    const response = await createAdminUserRoleBindings(
      user.id,
      [
        {
          role_id: role.id,
          scope_type: role.scope_type,
          scope_id: role.scope_type === "enterprise" ? null : roleBindingForm.scopeId,
        },
      ],
      accessToken,
      roleBindingForm.confirmedHighRisk,
    );
    selectedUserRoleBindings.value = response.data;
    syncPaginationState(selectedUserRoleBindingPagination, response.pagination);
    roleBindingForm.confirmedHighRisk = false;
    await refreshUserRoleAdminState();
    selectNextAvailableRoleBindingTarget();
    userAdminFeedback.value = {
      tone: "success",
      message: "角色已授予。",
    };
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "授予角色失败"),
    };
  } finally {
    userAdminBusy.updatingRoles = false;
  }
}

async function revokeSelectedUserRoleBinding(binding: AdminRoleBindingData): Promise<void> {
  const user = selectedAdminUser.value;
  if (!user) {
    return;
  }
  if (binding.role_code === "system_admin" && !roleBindingForm.confirmedRemoveAdmin) {
    userAdminFeedback.value = {
      tone: "error",
      message: "移除系统管理员角色前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.updatingRoles = true;
  try {
    await revokeAdminUserRoleBinding(
      user.id,
      binding.id,
      accessToken,
      roleBindingForm.confirmedRemoveAdmin,
    );
    await refreshUserRoleAdminState();
    roleBindingForm.roleId = binding.role_id;
    roleBindingForm.scopeId = binding.scope_id ?? "";
    roleBindingForm.confirmedHighRisk = false;
    roleBindingForm.confirmedRemoveAdmin = false;
    syncRoleBindingScopeDefault();
    userAdminFeedback.value = {
      tone: "success",
      message: "角色绑定已撤销。",
    };
  } catch (error) {
    userAdminFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "撤销角色绑定失败"),
    };
  } finally {
    userAdminBusy.updatingRoles = false;
  }
}

function resetCreateUserForm(): void {
  userCreateForm.username = "";
  userCreateForm.name = "";
  userCreateForm.initialPassword = "";
  userCreateForm.passwordConfirm = "";
  userCreateForm.departmentIds = [];
  userCreateForm.roleIds = [];
  userCreateForm.confirmedHighRisk = false;
  ensureDefaultCreateDepartmentSelection();
}

function syncSelectedUserDepartmentForm(): void {
  userDepartmentForm.departmentIds = selectedUserDepartmentsForForm.value.map(
    (department) => department.id,
  );
  userDepartmentForm.confirmedReplacePrimary = false;
}

function updateSelectedAdminUserDepartments(departments: AdminDepartmentData[]): void {
  if (selectedAdminUserDetail.value?.id === selectedAdminUserId.value) {
    selectedAdminUserDetail.value = {
      ...selectedAdminUserDetail.value,
      departments,
    };
  }
  const index = adminUsers.value.findIndex((user) => user.id === selectedAdminUserId.value);
  if (index < 0) {
    return;
  }
  adminUsers.value[index] = {
    ...adminUsers.value[index],
    department_names: departments.map((department) => department.name),
  };
}

function selectConfigItem(itemOrKey: ConfigItemData | string): void {
  const item =
    typeof itemOrKey === "string"
      ? (configItems.value.find((entry) => entry.key === itemOrKey && entry.status === "active") ??
        configItems.value.find((entry) => entry.key === itemOrKey))
      : itemOrKey;
  selectedConfigKey.value = typeof itemOrKey === "string" ? itemOrKey : itemOrKey.key;
  selectedDraftVersion.value =
    item && (item.status === "draft" || item.status === "validating") ? item.version : null;
  configValidationResult.value = null;
  lastConfigValidatedText.value = null;
  syncConfigFormFromActiveConfig(item ?? null);
}

async function ensureConfigVersionDetail(
  version: number,
  existingAccessToken?: string,
): Promise<ConfigVersionData | null> {
  const cached = configVersionDetails.value[version];
  if (cached?.config) {
    return cached;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return null;
  }
  const response = await getConfigVersion(version, accessToken);
  configVersionDetails.value = {
    ...configVersionDetails.value,
    [response.data.version]: response.data,
  };
  return response.data;
}

async function openCreateConfigModal(): Promise<void> {
  selectedConfigVersionNumber.value = null;
  selectedDraftVersion.value = null;
  try {
    await ensureConfigVersionDetail(activeConfigVersion.value);
    syncConfigFormFromVersion(activeConfigVersionRecord.value);
    resetConfigModalState();
    configModalMode.value = "create";
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取当前配置详情失败"),
    };
  }
}

async function openEditConfigVersion(version: ConfigVersionListItemData): Promise<void> {
  try {
    const detail = await ensureConfigVersionDetail(version.version);
    if (!detail) {
      return;
    }
    selectedConfigVersionNumber.value = detail.version;
    selectedDraftVersion.value = detail.version;
    syncConfigFormFromVersion(detail);
    resetConfigModalState();
    configModalMode.value = "edit";
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取配置版本详情失败"),
    };
  }
}

function closeConfigModal(): void {
  configModalMode.value = null;
}

function configModalTitle(): string {
  if (configModalMode.value === "create") {
    return "新建配置版本";
  }
  if (configModalMode.value === "edit") {
    return `编辑配置版本 v${selectedConfigVersionNumber.value ?? "-"}`;
  }
  return "配置管理";
}

function resetConfigModalState(): void {
  configFeedback.value = null;
  configValidationResult.value = null;
  lastConfigValidatedText.value = null;
  configEditorText.value = configFormSignature();
}

function onConfigKeyChange(key: string): void {
  selectedConfigKey.value = key;
  selectedDraftVersion.value = null;
  syncConfigFormFromActiveConfig();
  resetConfigModalState();
}

function updateConfigFieldFromInput(field: FieldDefinition, value: string): void {
  if (field.input === "number") {
    const parsed = Number(value);
    setConfigFormValue(field.key, Number.isFinite(parsed) ? parsed : 0);
    resetConfigValidationState();
    return;
  }
  setConfigFormValue(field.key, value);
  resetConfigValidationState();
}

function updateConfigFieldFromSelect(field: FieldDefinition, value: string): void {
  setConfigFormValue(field.key, value);
  resetConfigValidationState();
}

function updateConfigFieldFromCheckbox(field: FieldDefinition, value: boolean): void {
  setConfigFormValue(field.key, value);
  resetConfigValidationState();
}

function setConfigFormValue(key: keyof SetupFormModel, value: unknown): void {
  (configForm as Record<keyof SetupFormModel, unknown>)[key] = value;
}

function resetConfigValidationState(): void {
  configValidationResult.value = null;
  lastConfigValidatedText.value = null;
  configEditorText.value = configFormSignature();
}

async function validateSelectedConfig(): Promise<void> {
  const configBundle = buildEditedActiveConfigBundle();
  if (!configBundle) {
    configFeedback.value = {
      tone: "error",
      message: configEditorParseError.value ?? "请先完成配置表单。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.validating = true;
  try {
    const response = await validateAdminConfig(configBundle, accessToken);
    configValidationResult.value = response.data;
    configEditorText.value = configFormSignature();
    lastConfigValidatedText.value = response.data.valid ? configEditorText.value : null;
    configFeedback.value = {
      tone: response.data.valid ? "success" : "error",
      message: response.data.valid ? "配置校验通过。" : "配置校验未通过。",
    };
  } catch (error) {
    configValidationResult.value = null;
    lastConfigValidatedText.value = null;
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "配置校验失败"),
    };
  } finally {
    configBusy.validating = false;
  }
}

async function saveSelectedDraft(): Promise<void> {
  const configBundle = buildEditedActiveConfigBundle();
  if (!configBundle) {
    configFeedback.value = {
      tone: "error",
      message: configEditorParseError.value ?? "请填写需要保存的完整配置。",
    };
    return;
  }
  if (configModalMode.value === "edit" && selectedConfigVersionNumber.value === null) {
    configFeedback.value = {
      tone: "error",
      message: "请选择需要编辑的配置版本。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.saving = true;
  try {
    const response =
      configModalMode.value === "create"
        ? await createConfigVersion(configBundle, accessToken)
        : await updateConfigVersion(selectedConfigVersionNumber.value ?? 0, configBundle, accessToken);
    selectedConfigVersionNumber.value = response.data.version;
    selectedDraftVersion.value = response.data.version;
    configFeedback.value = {
      tone: "success",
      message: `已保存配置版本 v${response.data.version}。`,
    };
    await refreshConfigAdminState();
    closeConfigModal();
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "保存配置草稿失败"),
    };
  } finally {
    configBusy.saving = false;
  }
}

async function publishDraftVersion(version?: number | null): Promise<void> {
  const targetVersion = version ?? selectedDraftVersion.value;
  if (!targetVersion) {
    configFeedback.value = {
      tone: "error",
      message: "请选择需要发布的配置草稿版本。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.publishing = true;
  try {
    const response = await publishConfigVersion(targetVersion, accessToken);
    selectedDraftVersion.value = null;
    configValidationResult.value = null;
    lastConfigValidatedText.value = null;
    configFeedback.value = {
      tone: "success",
      message: `已激活配置版本 v${response.data.version}。`,
    };
    await refreshConfigAdminState();
    closeConfigModal();
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "激活配置版本失败"),
    };
  } finally {
    configBusy.publishing = false;
  }
}

async function archiveConfigVersionFromUi(version: ConfigVersionListItemData): Promise<void> {
  if (!isArchivableConfigVersion(version)) {
    configFeedback.value = {
      tone: "error",
      message: "只能归档非 active 且未归档的配置版本。",
    };
    return;
  }
  const confirmed = window.confirm(`确认归档配置版本 v${version.version}？归档后将不能直接激活该版本。`);
  if (!confirmed) {
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.deleting = true;
  try {
    await archiveConfigVersion(version.version, accessToken);
    configFeedback.value = {
      tone: "success",
      message: `已归档配置版本 v${version.version}。`,
    };
    await refreshConfigAdminState();
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "归档配置版本失败"),
    };
  } finally {
    configBusy.deleting = false;
  }
}

async function ensureAccessToken(): Promise<string | null> {
  const tokenState = authTokens.value;
  if (!tokenState) {
    return null;
  }
  if (Date.now() < tokenState.accessTokenExpiresAt - TOKEN_REFRESH_SKEW_MS) {
    return tokenState.accessToken;
  }
  return refreshAccessToken();
}

async function refreshAccessToken(): Promise<string | null> {
  const tokenState = authTokens.value;
  if (!tokenState?.refreshToken) {
    return null;
  }
  authBusy.refreshing = true;
  try {
    const response = await refreshSession(tokenState.refreshToken);
    saveAuthTokens(response);
    return response.access_token;
  } catch {
    clearAuthSession();
    return null;
  } finally {
    authBusy.refreshing = false;
  }
}

async function logout(): Promise<void> {
  const accessToken = authTokens.value?.accessToken;
  authBusy.loggingOut = true;
  try {
    if (accessToken) {
      await deleteCurrentSession(accessToken);
    }
  } catch {
    // 本地退出必须可靠，后端吊销失败不能阻塞清理本地登录态。
  } finally {
    clearAuthSession();
    authBusy.loggingOut = false;
    authFeedback.value = {
      tone: "neutral",
      message: "已退出登录。",
    };
    navigateTo("/admin/login");
  }
}

function loadStoredAuthTokens(): AuthTokenState | null {
  try {
    const raw = window.sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (
      typeof parsed.accessToken === "string" &&
      typeof parsed.refreshToken === "string" &&
      typeof parsed.accessTokenExpiresAt === "number"
    ) {
      return parsed;
    }
  } catch {
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }
  return null;
}

function saveAuthTokens(response: TokenResponse): void {
  const tokenState: AuthTokenState = {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    accessTokenExpiresAt: Date.now() + response.expires_in * 1000,
  };
  authTokens.value = tokenState;
  window.sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokenState));
}

function clearAuthSession(): void {
  authTokens.value = null;
  currentUser.value = null;
  adminAccessGranted.value = false;
  documentManagerModalOpen.value = false;
  queryLogDetailModalOpen.value = false;
  modelCallLogDetailModalOpen.value = false;
  configItems.value = [];
  configVersions.value = [];
  configVersionDetails.value = {};
  auditLogs.value = [];
  queryLogs.value = [];
  modelCallLogs.value = [];
  indexHealth.value = [];
  clearPaginationState(indexHealthPagination);
  indexCollectionSnapshots.value = [];
  clearPaginationState(indexSnapshotPagination);
  selectedQueryLog.value = null;
  selectedModelCallLog.value = null;
  adminUsers.value = [];
  selectedAdminUserDetail.value = null;
  selectedUserDepartments.value = [];
  selectedUserRoleBindings.value = [];
  adminDepartments.value = [];
  adminDepartmentOptions.value = [];
  adminKnowledgeBases.value = [];
  adminKnowledgeBaseOptions.value = [];
  selectedKnowledgeBaseDetail.value = null;
  adminFolders.value = [];
  adminFolderOptions.value = [];
  clearPaginationState(folderPagination);
  adminDocuments.value = [];
  clearPaginationState(documentPagination);
  clearSelectedDocumentDetails();
  clearSelectedDocumentMetadata();
  adminRoles.value = [];
  adminImportJobs.value = [];
  failedIndexJobs.value = [];
  selectedFailedIndexJobIds.value = [];
  clearPaginationState(failedIndexJobPagination);
  selectedBatchDocumentIds.value = [];
  selectedKnowledgeBaseId.value = "";
  selectedFolderId.value = "";
  selectedDocumentId.value = "";
  selectedImportFiles.value = [];
  clearPaginationState(configVersionPagination);
  clearPaginationState(auditLogPagination);
  clearPaginationState(departmentPagination);
  clearPaginationState(userPagination);
  clearPaginationState(selectedUserDepartmentPagination);
  clearPaginationState(selectedUserRoleBindingPagination);
  clearPaginationState(knowledgeBasePagination);
  clearPaginationState(importJobPagination);
  clearPaginationState(failedIndexJobPagination);
  clearPaginationState(queryLogPagination);
  clearPaginationState(modelCallLogPagination);
  clearPaginationState(indexHealthPagination);
  clearPaginationState(indexSnapshotPagination);
  knowledgeBaseSearchForm.keyword = "";
  knowledgeBaseSearchForm.status = "";
  resetDiagnosticsFilters();
  knowledgeBaseModalMode.value = null;
  folderModalMode.value = null;
  documentModalMode.value = null;
  knowledgeBaseDangerForm.confirmedDelete = false;
  folderDangerForm.confirmedDelete = false;
  knowledgeBasePermissionForm.confirmedReplace = false;
  documentPermissionForm.confirmedReplace = false;
  knowledgeBaseIndexForm.confirmedRebuild = false;
  documentIndexForm.confirmedRebuild = false;
  documentIndexForm.confirmedBatchRebuild = false;
  documentIndexForm.confirmedCleanup = false;
  indexRetryForm.confirmedRetry = false;
  indexCollectionOpsForm.selectedCollectionName = "";
  indexCollectionOpsForm.snapshotLocation = "";
  indexCollectionOpsForm.snapshotChecksum = "";
  indexCollectionOpsForm.recoverPriority = "Snapshot";
  indexCollectionOpsForm.confirmedSnapshot = false;
  indexCollectionOpsForm.confirmedRestore = false;
  indexCollectionOpsForm.confirmedRebuild = false;
  importUploadForm.kbId = "";
  importUploadForm.folderId = "";
  importUploadForm.idempotencyKey = "";
  importSearchForm.kbId = "";
  importSearchForm.jobType = "";
  importSearchForm.status = "";
  importSearchForm.stage = "";
  documentSearchForm.status = "";
  selectedAdminUserId.value = "";
  selectedUserRoleBindings.value = [];
  selectedConfigKey.value = "";
  configEditorText.value = "";
  configValidationResult.value = null;
  selectedDraftVersion.value = null;
  lastConfigValidatedText.value = null;
  configModalMode.value = null;
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
}

function syncRouteToCurrentState(): void {
  const path = window.location.pathname;
  if (!setupState.value) {
    return;
  }
  if (setupModeRequired.value) {
    if (path !== "/admin/setup-initialization") {
      navigateTo("/admin/setup-initialization", true);
    }
    return;
  }
  if (path === "/admin/setup-initialization") {
    navigateTo(authenticated.value ? "/admin" : "/admin/login", true);
    return;
  }
  if (authenticated.value && path === "/admin/login") {
    navigateTo("/admin", true);
    return;
  }
  if ((path === "/admin" || path === "/admin/") && !authenticated.value) {
    navigateTo("/admin/login", true);
  }
}

function navigateTo(path: string, replace = false): void {
  if (window.location.pathname === path) {
    return;
  }
  if (replace) {
    window.history.replaceState(null, "", path);
    return;
  }
  window.history.pushState(null, "", path);
}

async function runValidation(): Promise<void> {
  if (!canValidate.value) {
    feedback.value = {
      tone: "error",
      message: validationGateMessage.value,
    };
    return;
  }
  busy.validating = true;
  try {
    const response = await validateSetupConfig(payload.value, form.setupToken || undefined);
    validationResult.value = response.data;
    validationErrorPayload.value = null;
    // 只记录“已通过”的请求签名，防止表单变更后误放行初始化提交。
    lastValidatedPayload.value = response.data.valid ? payloadSignature.value : null;
    feedback.value = {
      tone: response.data.valid ? "success" : "error",
      message: response.data.valid ? "配置校验通过" : "配置校验未通过",
    };
    await refreshState();
  } catch (error) {
    validationResult.value = null;
    lastValidatedPayload.value = null;
    validationErrorPayload.value = error instanceof ApiRequestError ? error.payload : null;
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "配置校验失败"),
    };
  } finally {
    busy.validating = false;
  }
}

async function runInitialization(): Promise<void> {
  if (!canSubmit.value) {
    feedback.value = {
      tone: "error",
      message: validationGateMessage.value,
    };
    return;
  }
  busy.submitting = true;
  try {
    // initializeSetup 会自动带 x-setup-confirm；后端仍会二次校验确认头和请求体。
    const response = await initializeSetup(payload.value, form.setupToken || undefined);
    initializationResult.value = response.data;
    initializationErrorPayload.value = null;
    feedback.value = {
      tone: "success",
      message: "初始化提交成功",
    };
    submitConfirmed.value = false;
    await refreshState();
  } catch (error) {
    initializationResult.value = null;
    initializationErrorPayload.value = error instanceof ApiRequestError ? error.payload : null;
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "初始化提交失败"),
    };
  } finally {
    busy.submitting = false;
  }
}

function resetForm(): void {
  // 恢复默认值时同步清空校验和提交结果，避免旧反馈误导当前表单。
  Object.assign(form, createDefaultSetupForm());
  validationResult.value = null;
  lastValidatedPayload.value = null;
  initializationResult.value = null;
  validationErrorPayload.value = null;
  initializationErrorPayload.value = null;
  feedback.value = {
    tone: "neutral",
    message: "已恢复本地默认初始化配置",
  };
  submitConfirmed.value = false;
}

function updateStringField(key: StringFieldKey, value: string): void {
  setFormValue(key, value);
}

function updateNumberField(key: NumberFieldKey, value: string): void {
  const parsed = Number(value);
  setFormValue(key, Number.isFinite(parsed) ? parsed : 0);
}

function updateBooleanField(key: BooleanFieldKey, value: boolean): void {
  setFormValue(key, value);
}

function updateFieldFromInput(field: FieldDefinition, value: string): void {
  if (field.input === "number") {
    updateNumberField(field.key as NumberFieldKey, value);
    return;
  }
  updateStringField(field.key as StringFieldKey, value);
}

function updateFieldFromSelect(field: FieldDefinition, value: string): void {
  updateStringField(field.key as StringFieldKey, value);
}

function updateFieldFromCheckbox(field: FieldDefinition, value: boolean): void {
  updateBooleanField(field.key as BooleanFieldKey, value);
}

function setFormValue<K extends keyof SetupFormModel>(key: K, value: SetupFormModel[K]): void {
  form[key] = value;
}

function fieldIssues(key: keyof SetupFormModel): LocalValidationIssue[] {
  return fieldIssueMap.value.get(key) ?? [];
}

function hasFieldError(key: keyof SetupFormModel): boolean {
  return fieldIssues(key).some((issue) => issue.tone === "error");
}

function hasFieldWarning(key: keyof SetupFormModel): boolean {
  return fieldIssues(key).some((issue) => issue.tone === "warning");
}

function sectionToneText(item: { errors: number; warnings: number }): string {
  if (item.errors > 0) {
    return `${item.errors} 阻断`;
  }
  if (item.warnings > 0) {
    return `${item.warnings} 提醒`;
  }
  return "通过";
}

function issueToneText(tone: LocalIssueTone): string {
  return tone === "error" ? "阻断" : "提醒";
}

function formatBoolean(value: boolean): string {
  return value ? "是" : "否";
}

function formatSetupStatus(status: string): string {
  return statusLabels[status] ?? `未知状态（${status}）`;
}

function formatStatusText(status: string | null | undefined): string {
  if (!status) {
    return "-";
  }
  const labels: Record<string, string> = {
    active: "启用",
    disabled: "禁用",
    locked: "锁定",
    deleted: "已删除",
    archived: "已归档",
    inactive: "未启用",
    draft: "草稿",
    validating: "校验中",
    ready: "就绪",
    pending_delete: "待清理",
    published: "已发布",
    processing: "处理中",
    failed: "失败",
    success: "成功",
    denied: "拒绝",
    degraded: "已降级",
    none: "未索引",
    indexing: "索引中",
    indexed: "已索引",
    index_failed: "索引失败",
    blocked: "已阻断",
    queued: "排队中",
    running: "运行中",
    retrying: "重试中",
    partial_success: "部分成功",
    cancelled: "已取消",
    upload: "文件导入",
    url: "链接导入",
    metadata_batch: "元数据批量任务",
    index_rebuild: "索引重建",
    permission_refresh: "权限刷新",
    llm: "大模型",
    rerank: "重排",
    embedding: "向量化",
    green: "正常",
    yellow: "告警",
    red: "异常",
    unreachable: "不可达",
    unknown: "未知",
  };
  return labels[status] ?? status;
}

function riskLevelText(riskLevel: string | null | undefined): string {
  if (!riskLevel) {
    return "-";
  }
  const labels: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };
  return labels[riskLevel] ?? riskLevel;
}

function formatStatusOption(status: string): string {
  return formatStatusText(status);
}

function formatRoleLabel(role: { code?: string | null; name?: string | null } | null | undefined): string {
  if (!role) {
    return "-";
  }
  const code = role.code?.trim();
  if (code && builtinRoleLabels[code]) {
    return builtinRoleLabels[code];
  }
  return role.name?.trim() || code || "-";
}

function formatRoleCodeLabel(roleCode: string | null | undefined, fallback = "-"): string {
  if (!roleCode) {
    return fallback;
  }
  return builtinRoleLabels[roleCode] ?? roleCode;
}

function formatRoleList(roles: Array<{ code?: string | null; name?: string | null }>): string {
  const labels = roles.map((role) => formatRoleLabel(role)).filter((label) => label !== "-");
  return labels.length ? labels.join(" / ") : "-";
}

function formatRoleScopeType(scopeType: string | null | undefined): string {
  if (scopeType === "enterprise") {
    return "企业级";
  }
  if (scopeType === "department") {
    return "部门级";
  }
  if (scopeType === "knowledge_base") {
    return "知识库级";
  }
  return scopeType || "-";
}

function formatDepartmentLabel(
  department: { code?: string | null; name?: string | null } | null | undefined,
): string {
  if (!department) {
    return "-";
  }
  const name = department.name?.trim();
  const code = department.code?.trim();
  if (name) {
    return name;
  }
  return code ? "未命名部门" : "-";
}

function formatDepartmentList(
  departments: Array<{ code?: string | null; name?: string | null }>,
): string {
  const labels = departments
    .map((department) => formatDepartmentLabel(department))
    .filter((label) => label !== "-");
  return labels.length ? labels.join(" / ") : "-";
}

function formatKnowledgeBaseLabel(
  knowledgeBase: { name?: string | null; id?: string | null } | null | undefined,
): string {
  if (!knowledgeBase) {
    return "-";
  }
  return knowledgeBase.name?.trim() || (knowledgeBase.id?.trim() ? "未命名知识库" : "-");
}

function formatFolderLabel(folder: { name?: string | null; id?: string | null } | null | undefined): string {
  if (!folder) {
    return "根目录";
  }
  return folder.name?.trim() || (folder.id?.trim() ? "未命名文件夹" : "根目录");
}

function formatFolderById(folderId: string | null): string {
  if (!folderId) {
    return "根目录";
  }
  const folder =
    adminFolderOptions.value.find((item) => item.id === folderId) ??
    adminFolders.value.find((item) => item.id === folderId);
  return folder ? formatFolderLabel(folder) : "未读取到文件夹";
}

function departmentSnapshotById(
  departmentId: string,
): { code?: string | null; name?: string | null } | null {
  const knowledgeBaseOwner = adminKnowledgeBases.value.find(
    (item) => item.owner_department_id === departmentId,
  );
  const knowledgeBaseDefaultOwner = adminKnowledgeBases.value.find(
    (item) => item.default_document_owner_department_id === departmentId,
  );
  return (
    adminDepartmentOptions.value.find((item) => item.id === departmentId) ??
    adminDepartments.value.find((item) => item.id === departmentId) ??
    currentUser.value?.departments.find((item) => item.id === departmentId) ??
    (selectedKnowledgeBaseDetail.value?.owner_department?.id === departmentId
      ? selectedKnowledgeBaseDetail.value.owner_department
      : null) ??
    (selectedKnowledgeBaseDetail.value?.default_document_owner_department?.id === departmentId
      ? selectedKnowledgeBaseDetail.value.default_document_owner_department
      : null) ??
    (knowledgeBaseOwner?.owner_department_name
      ? { name: knowledgeBaseOwner.owner_department_name }
      : null) ??
    (knowledgeBaseDefaultOwner?.default_document_owner_department_name
      ? { name: knowledgeBaseDefaultOwner.default_document_owner_department_name }
      : null) ??
    null
  );
}

function formatDepartmentById(departmentId: string | null | undefined): string {
  if (!departmentId) {
    return "-";
  }
  const department = departmentSnapshotById(departmentId);
  return department ? formatDepartmentLabel(department) : "未读取到部门";
}

function folderStatusTone(status: AdminFolderData["status"]): Tone {
  if (status === "active") {
    return "success";
  }
  if (status === "disabled") {
    return "warning";
  }
  return "neutral";
}

function knowledgeBaseStatusTone(status: AdminKnowledgeBaseData["status"]): Tone {
  if (status === "active") {
    return "success";
  }
  if (status === "disabled") {
    return "warning";
  }
  return "neutral";
}

function knowledgeBaseVisibilityLabel(visibility: AdminKnowledgeBaseData["kb_visibility"]): string {
  if (visibility === "enterprise") {
    return "企业可见";
  }
  return visibility === "department_acl" ? "指定部门可见" : "私密可见";
}

function documentVisibilityLabel(visibility: "department" | "enterprise"): string {
  return visibility === "enterprise" ? "企业可见" : "部门可见";
}

function queryDepartmentIdsForKnowledgeBase(knowledgeBase: AdminKnowledgeBaseData): string[] {
  const ids = new Set<string>();
  for (const rule of knowledgeBase.access_rules ?? []) {
    if (
      rule.subject_type === "department" &&
      (rule.permission === "query" || rule.permission === "manage")
    ) {
      ids.add(rule.subject_id);
    }
  }
  return Array.from(ids);
}

function departmentCanQueryKnowledgeBase(
  knowledgeBase: AdminKnowledgeBaseData,
  departmentId: string,
): boolean {
  if (knowledgeBase.kb_visibility === "enterprise") {
    return true;
  }
  return queryDepartmentIdsForKnowledgeBase(knowledgeBase).includes(departmentId);
}

function buildDepartmentKnowledgeBaseAccessRules(
  departmentIds: string[],
): KnowledgeBaseAccessRuleData[] {
  const rules: KnowledgeBaseAccessRuleData[] = [];
  for (const departmentId of new Set(departmentIds.filter(Boolean))) {
    rules.push(
      { subject_type: "department", subject_id: departmentId, permission: "discover" },
      { subject_type: "department", subject_id: departmentId, permission: "query" },
      { subject_type: "department", subject_id: departmentId, permission: "manage" },
    );
  }
  return rules;
}

function documentLifecycleStatusTone(status: AdminDocumentData["lifecycle_status"]): Tone {
  if (status === "active") {
    return "success";
  }
  if (status === "draft" || status === "archived") {
    return "warning";
  }
  return "error";
}

function documentIndexStatusTone(status: AdminDocumentData["index_status"]): Tone {
  if (status === "indexed") {
    return "success";
  }
  if (status === "indexing") {
    return "warning";
  }
  if (status === "index_failed" || status === "blocked") {
    return "error";
  }
  return "neutral";
}

function documentVersionStatusTone(status: string): Tone {
  if (status === "active" || status === "published" || status === "ready") {
    return "success";
  }
  if (status === "draft" || status === "processing") {
    return "warning";
  }
  if (status === "failed" || status === "deleted") {
    return "error";
  }
  return "neutral";
}

function indexVersionStatusTone(status: IndexVersionData["status"]): Tone {
  if (status === "active") {
    return "success";
  }
  if (status === "ready" || status === "draft" || status === "pending_delete") {
    return "warning";
  }
  if (status === "failed") {
    return "error";
  }
  return "neutral";
}

function formatDocumentVersion(version: DocumentVersionData): string {
  return `v${version.version_no}`;
}

function formatDocumentVersionById(versionId: string | null | undefined): string {
  if (!versionId) {
    return "-";
  }
  const version = selectedDocumentVersions.value.find((item) => item.id === versionId);
  return version ? formatDocumentVersion(version) : "-";
}

function formatDocumentCurrentVersion(
  document: AdminDocumentData | AdminDocumentListItemData,
): string {
  if (typeof document.current_version_no === "number") {
    return `v${document.current_version_no}`;
  }
  if ("current_version_id" in document && document.current_version_id && document.id === selectedDocumentId.value) {
    return formatDocumentVersionById(document.current_version_id);
  }
  return "-";
}

function formatIndexVersionLabel(index: number): string {
  return `索引版本 ${(documentIndexVersionPagination.page - 1) * documentIndexVersionPagination.pageSize + index + 1}`;
}

function formatChunkOrdinal(chunk: ChunkData, index: number): string {
  return `片段 ${chunk.ordinal || (documentChunkPagination.page - 1) * documentChunkPagination.pageSize + index + 1}`;
}

function formatChunkPageRange(chunk: Pick<ChunkData, "page_start" | "page_end">): string {
  if (chunk.page_start === null && chunk.page_end === null) {
    return "-";
  }
  if (chunk.page_start === chunk.page_end || chunk.page_end === null) {
    return String(chunk.page_start ?? "-");
  }
  return `${chunk.page_start ?? "-"}-${chunk.page_end}`;
}

function selectDocumentChunk(chunkId: string): void {
  highlightedDocumentChunkId.value = chunkId;
}

function formatImportJobKnowledgeBase(job: ImportJobData | ImportJobListItemData): string {
  const knowledgeBase =
    adminKnowledgeBaseOptions.value.find((item) => item.id === job.kb_id) ??
    adminKnowledgeBases.value.find((item) => item.id === job.kb_id);
  return knowledgeBase ? formatKnowledgeBaseLabel(knowledgeBase) : "未读取到知识库";
}

function formatDocumentCount(documentCount: number): string {
  return documentCount > 0 ? `${documentCount} 个文档` : "-";
}

function formatImportJobTitle(job: ImportJobData | ImportJobListItemData): string {
  if (job.job_type === "upload") {
    return "文档导入任务";
  }
  if (job.job_type === "index_rebuild") {
    return "索引重建任务";
  }
  if (job.job_type === "permission_refresh") {
    return "权限刷新任务";
  }
  return "后台任务";
}

function importJobListItemFromDetail(job: ImportJobData): ImportJobListItemData {
  return {
    id: job.id,
    kb_id: job.kb_id,
    job_type: job.job_type,
    status: job.status,
    stage: job.stage,
    document_count: job.document_ids.length,
    error_summary: job.error_summary,
  };
}

function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function importJobStatusTone(status: ImportJobStatus): Tone {
  if (status === "success" || status === "partial_success") {
    return "success";
  }
  if (status === "failed" || status === "cancelled") {
    return "error";
  }
  if (status === "retrying") {
    return "warning";
  }
  return "neutral";
}

function importJobStageLabel(stage: ImportJobStage): string {
  const labels: Record<ImportJobStage, string> = {
    validate: "校验",
    parse: "解析",
    clean: "清洗",
    chunk: "切片",
    embed: "向量化",
    index: "写索引",
    publish: "发布",
    cleanup: "清理",
    finished: "完成",
  };
  return labels[stage];
}

function formatStatusWithDegradation(status: string, degraded: boolean): string {
  const statusText = formatStatusText(status);
  if (status === "degraded") {
    return "已降级";
  }
  if (degraded) {
    return `${statusText} / 已降级`;
  }
  return `${statusText} / 未降级`;
}

function formatDiagnosticReasonCode(reason: string): string {
  const labels: Record<string, string> = {
    llm_context_empty: "无可用上下文",
    llm_runtime_config_unavailable: "LLM 配置不可用",
    llm_stream_result_missing: "流式输出为空",
    llm_degraded: "LLM 降级",
    citation_missing: "缺少引用",
    citation_auto_attached: "自动补充引用",
    citation_invalid_format: "引用格式无效",
    citation_unauthorized: "引用未授权",
    vector_retriever_unavailable: "向量检索不可用",
    vector_runtime_config_unavailable: "向量配置不可用",
    vector_runtime_config_incomplete: "向量配置不完整",
    vector_collection_unavailable: "向量集合不可用",
    query_embedding_failed: "问题向量化失败",
    vector_search_failed: "向量检索失败",
    vector_retrieval_degraded: "向量检索降级",
    retrieval_relevance_too_low: "召回相关性过低",
    RERANK_PROVIDER_UNAVAILABLE: "精排服务不可用",
    RERANK_PROVIDER_HTTP_ERROR: "精排服务异常",
    RERANK_PROVIDER_RESPONSE_INVALID: "精排响应无效",
    QUERY_RERANK_INPUT_UNAVAILABLE: "精排输入不可用",
    rerank_input_mismatch: "精排输入不匹配",
    rerank_degraded: "精排降级",
    LLM_PROVIDER_HTTP_ERROR: "LLM 服务异常",
    LLM_PROVIDER_UNAVAILABLE: "LLM 服务不可用",
    LLM_PROVIDER_RESPONSE_INVALID: "LLM 响应无效",
    QUERY_STREAM_FINALIZE_FAILED: "流式收尾失败",
  };
  return labels[reason] ?? "未归类降级";
}

function formatDiagnosticReasonList(value: string | null | undefined, fallback = "未降级"): string {
  if (!value) {
    return fallback;
  }
  return value
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean)
    .map(formatDiagnosticReasonCode)
    .filter((item, index, items) => items.indexOf(item) === index)
    .join("；") || fallback;
}

type QueryLogDisplayData = QueryLogData | QueryLogListItemData;
type ModelCallLogDisplayData = ModelCallLogData | ModelCallLogListItemData;

function formatQueryLogStatus(log: QueryLogDisplayData): string {
  return formatStatusWithDegradation(log.status, log.degraded);
}

function formatModelCallStatus(log: ModelCallLogDisplayData): string {
  return formatStatusWithDegradation(log.status, log.degraded);
}

function formatModelCallTitle(log: ModelCallLogDisplayData): string {
  return `${log.model_name} / ${formatModelCallStatus(log)}`;
}

function formatRoleBindingScope(binding: AdminRoleBindingData): string {
  if (binding.scope_type === "enterprise") {
    return "全企业";
  }
  if (binding.scope_type === "department") {
    const department =
      adminDepartmentOptions.value.find((item) => item.id === binding.scope_id) ??
      adminDepartments.value.find((item) => item.id === binding.scope_id);
    return `部门：${department ? formatDepartmentLabel(department) : "未读取到部门"}`;
  }
  const knowledgeBase =
    adminKnowledgeBaseOptions.value.find((item) => item.id === binding.scope_id) ??
    adminKnowledgeBases.value.find((item) => item.id === binding.scope_id);
  return `知识库：${formatKnowledgeBaseLabel(knowledgeBase ?? { id: binding.scope_id, name: "" })}`;
}

function roleBindingKey(binding: AdminRoleBindingData): string {
  return roleBindingKeyFromParts(binding.role_id, binding.scope_type, binding.scope_id);
}

function roleBindingKeyFromParts(
  roleId: string,
  scopeType: "enterprise" | "department" | "knowledge_base",
  scopeId: string | null,
): string {
  return `${roleId}:${scopeType}:${scopeType === "enterprise" ? "enterprise" : scopeId ?? ""}`;
}

function toneClass(tone: Tone): string {
  return `tone tone--${tone}`;
}

function hasScope(scopes: string[], requiredScope: string): boolean {
  if (scopes.includes("*") || scopes.includes(requiredScope)) {
    return true;
  }
  const prefix = requiredScope.split(":", 1)[0];
  return scopes.includes(`${prefix}:*`);
}

function isHighRiskAdminRole(role: AdminAssignableRoleOptionData | AdminRoleData): boolean {
  if ("risk_level" in role) {
    return role.risk_level === "high";
  }
  return (
    role.code === "system_admin" ||
    role.code === "security_admin" ||
    role.code === "audit_admin" ||
    role.scopes.includes("*") ||
    role.scopes.some(isHighRiskScope)
  );
}

function isHighRiskScope(scope: string): boolean {
  if (["config:manage", "user:manage", "role:manage", "permission:manage"].includes(scope)) {
    return true;
  }
  return ["config:*", "user:*", "role:*", "permission:*"].includes(scope);
}

function setupFields(...keys: Array<keyof SetupFormModel>): FieldDefinition[] {
  return keys
    .map((key) => setupFieldByKey.get(key))
    .filter((field): field is FieldDefinition => Boolean(field));
}

function configDefinitionForKey(key: string): ConfigSectionFormDefinition | null {
  return configSectionDefinitions.find((definition) => definition.key === key) ?? null;
}

function syncConfigFormFromActiveConfig(preferredItem: ConfigItemData | null = null): void {
  const defaults = createDefaultSetupForm();
  Object.assign(configForm, defaults);
  const configBundle = buildCurrentConfigBundle(preferredItem);
  hydrateConfigForm(configForm, configBundle);
  const selectedValue = selectedConfigKey.value ? configBundle[selectedConfigKey.value] : null;
  configJsonText.value = JSON.stringify(isRecord(selectedValue) ? selectedValue : {}, null, 2);
  configEditorText.value = configFormSignature();
}

function syncConfigFormFromVersion(version: ConfigVersionData | null): void {
  const configBundle = version?.config ?? activeConfigVersionRecord.value?.config ?? {};
  const defaults = createDefaultSetupForm();
  Object.assign(configForm, defaults);
  hydrateConfigForm(configForm, configBundle);
  configJsonText.value = JSON.stringify(configBundle, null, 2);
  configEditorText.value = configFormSignature();
}

function configItemsFromVersion(version: ConfigVersionData | null): ConfigItemData[] {
  if (!version?.config) {
    return [];
  }
  return Object.entries(version.config)
    .filter(([key, value]) => !["schema_version", "config_version", "scope"].includes(key) && isRecord(value))
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => ({
      key,
      value_json: cloneJsonRecord(value as Record<string, unknown>),
      scope_type: "global",
      status: version.status,
      version: version.version,
    }));
}

function hydrateConfigForm(target: SetupFormModel, config: Record<string, unknown>): void {
  const secretProvider = asRecord(config.secret_provider);
  const redis = asRecord(config.redis);
  const storage = asRecord(config.storage);
  const vectorStore = asRecord(config.vector_store);
  const keywordSearch = asRecord(config.keyword_search);
  const modelGateway = asRecord(config.model_gateway);
  const providers = asRecord(modelGateway?.providers);
  const embeddingProvider = asRecord(providers?.embedding);
  const rerankProvider = asRecord(providers?.rerank);
  const llmProvider = asRecord(providers?.llm);
  const model = asRecord(config.model);
  const auth = asRecord(config.auth);
  const retrieval = asRecord(config.retrieval);
  const chunk = asRecord(config.chunk);
  const chunkStrategy = asRecord(chunk?.strategy);
  const importConfig = asRecord(config.import);
  const cache = asRecord(config.cache);
  const rateLimit = asRecord(config.rate_limit);
  const audit = asRecord(config.audit);
  const llm = asRecord(config.llm);
  const llmRetryPolicy = asRecord(llm?.retry_policy);
  const llmExtraBody = asRecord(llm?.openai_extra_body);
  const llmChatTemplateKwargs = asRecord(llmExtraBody?.chat_template_kwargs);
  const permission = asRecord(config.permission);
  const tighteningPolicy = asRecord(permission?.tightening_block_policy);
  const security = asRecord(config.security);
  const promptLeakagePolicy = asRecord(security?.prompt_leakage_policy);
  const piiRedactionPolicy = asRecord(security?.pii_redaction_policy);
  const timeout = asRecord(config.timeout);
  const degrade = asRecord(config.degrade);
  const observability = asRecord(config.observability);
  const alertThresholds = asRecord(observability?.alert_thresholds);

  target.secretProviderEndpoint = asString(secretProvider?.endpoint, target.secretProviderEndpoint);
  target.redisUrl = asString(redis?.url, target.redisUrl);
  target.minioEndpoint = asString(storage?.minio_endpoint, target.minioEndpoint);
  target.minioBucket = asString(storage?.bucket, target.minioBucket);
  target.minioRegion = asString(storage?.region, target.minioRegion);
  target.objectKeyPrefix = asString(storage?.object_key_prefix, target.objectKeyPrefix);
  target.minioAccessKeyRef = asString(storage?.access_key_ref, target.minioAccessKeyRef);
  target.minioSecretKeyRef = asString(storage?.secret_key_ref, target.minioSecretKeyRef);
  target.qdrantBaseUrl = asString(vectorStore?.qdrant_base_url, target.qdrantBaseUrl);
  target.qdrantApiKeyRef = asString(vectorStore?.api_key_ref, target.qdrantApiKeyRef);
  target.collectionPrefix = asString(vectorStore?.collection_prefix, target.collectionPrefix);
  target.vectorDistance = asVectorDistance(vectorStore?.distance, target.vectorDistance);
  target.keywordLanguage = asString(keywordSearch?.language, target.keywordLanguage);
  target.keywordAnalyzer = asString(keywordSearch?.keyword_analyzer, target.keywordAnalyzer);
  target.modelGatewayMode = asModelGatewayMode(modelGateway?.mode, target.modelGatewayMode);
  target.embeddingProviderBaseUrl = asString(embeddingProvider?.base_url, target.embeddingProviderBaseUrl);
  target.rerankProviderBaseUrl = asString(rerankProvider?.base_url, target.rerankProviderBaseUrl);
  target.llmProviderBaseUrl = asString(llmProvider?.base_url, target.llmProviderBaseUrl);
  target.embeddingDimension = asNumber(model?.embedding_dimension, target.embeddingDimension);
  target.embeddingModel = asString(model?.embedding_model, target.embeddingModel);
  target.rerankModel = asString(model?.rerank_model, target.rerankModel);
  target.llmModel = asString(model?.llm_model, target.llmModel);
  target.llmFallbackModel = asString(model?.llm_fallback_model, target.llmFallbackModel);
  target.passwordMinLength = asNumber(auth?.password_min_length, target.passwordMinLength);
  target.accessTokenTtlMinutes = asNumber(auth?.access_token_ttl_minutes, target.accessTokenTtlMinutes);
  target.refreshTokenTtlMinutes = asNumber(auth?.refresh_token_ttl_minutes, target.refreshTokenTtlMinutes);
  target.jwtIssuer = asString(auth?.jwt_issuer, target.jwtIssuer);
  target.jwtAudience = asString(auth?.jwt_audience, target.jwtAudience);
  target.jwtSigningKeyRef = asString(auth?.jwt_signing_key_ref, target.jwtSigningKeyRef);
  target.vectorTopK = asNumber(retrieval?.vector_top_k, target.vectorTopK);
  target.keywordTopK = asNumber(retrieval?.keyword_top_k, target.keywordTopK);
  target.rerankInputTopK = asNumber(retrieval?.rerank_input_top_k, target.rerankInputTopK);
  target.rerankMinScore = asNumber(retrieval?.rerank_min_score, target.rerankMinScore);
  target.finalContextTopK = asNumber(retrieval?.final_context_top_k, target.finalContextTopK);
  target.maxContextTokens = asNumber(retrieval?.max_context_tokens, target.maxContextTokens);
  target.chunkDefaultSizeTokens = asNumber(chunk?.default_size_tokens, target.chunkDefaultSizeTokens);
  target.chunkOverlapTokens = asNumber(chunk?.overlap_tokens, target.chunkOverlapTokens);
  target.chunkStrategyMode = asChunkStrategyMode(chunkStrategy?.mode, target.chunkStrategyMode);
  target.chunkPreserveTables = asBoolean(chunkStrategy?.preserve_tables, target.chunkPreserveTables);
  target.chunkPreserveCodeBlocks = asBoolean(chunkStrategy?.preserve_code_blocks, target.chunkPreserveCodeBlocks);
  target.chunkPreserveContractClauses = asBoolean(
    chunkStrategy?.preserve_contract_clauses,
    target.chunkPreserveContractClauses,
  );
  target.maxFileMb = asNumber(importConfig?.max_file_mb, target.maxFileMb);
  target.maxConcurrentJobs = asNumber(importConfig?.max_concurrent_jobs, target.maxConcurrentJobs);
  target.embeddingBatchSize = asNumber(importConfig?.embedding_batch_size, target.embeddingBatchSize);
  target.indexBatchSize = asNumber(importConfig?.index_batch_size, target.indexBatchSize);
  target.queryEmbeddingEnabled = asBoolean(cache?.query_embedding_enabled, target.queryEmbeddingEnabled);
  target.retrievalResultEnabled = asBoolean(cache?.retrieval_result_enabled, target.retrievalResultEnabled);
  target.finalAnswerEnabled = asBoolean(cache?.final_answer_enabled, target.finalAnswerEnabled);
  target.crossUserFinalAnswerAllowed = asBoolean(
    cache?.cross_user_final_answer_allowed,
    target.crossUserFinalAnswerAllowed,
  );
  target.queryQpsPerUser = asNumber(rateLimit?.query_qps_per_user, target.queryQpsPerUser);
  target.auditRetentionDays = asNumber(audit?.retention_days, target.auditRetentionDays);
  target.auditQueryTextMode = asAuditQueryTextMode(audit?.query_text_mode, target.auditQueryTextMode);
  target.llmTemperature = asNumber(llm?.temperature, target.llmTemperature);
  target.llmMaxTokens = asNumber(llm?.max_tokens, target.llmMaxTokens);
  target.llmFirstTokenTimeoutMs = asNumber(llm?.first_token_timeout_ms, target.llmFirstTokenTimeoutMs);
  target.llmTotalTimeoutMs = asNumber(llm?.total_timeout_ms, target.llmTotalTimeoutMs);
  target.llmMaxRetries = asNumber(llmRetryPolicy?.max_retries, target.llmMaxRetries);
  target.llmRetryBackoffMs = asNumber(llmRetryPolicy?.backoff_ms, target.llmRetryBackoffMs);
  target.llmEnableThinking = asBoolean(llmChatTemplateKwargs?.enable_thinking, target.llmEnableThinking);
  target.permissionDefaultVisibility = asPermissionVisibility(
    permission?.default_visibility,
    target.permissionDefaultVisibility,
  );
  target.permissionCacheTtlSeconds = asNumber(permission?.cache_ttl_seconds, target.permissionCacheTtlSeconds);
  target.permissionWriteAccessBlockFirst = asBoolean(
    tighteningPolicy?.write_access_block_first,
    target.permissionWriteAccessBlockFirst,
  );
  target.permissionBlockOldIndexRefs = asBoolean(
    tighteningPolicy?.block_old_index_refs,
    target.permissionBlockOldIndexRefs,
  );
  target.permissionFailClosed = asBoolean(tighteningPolicy?.fail_closed, target.permissionFailClosed);
  target.securityRequireCitation = asBoolean(security?.require_citation, target.securityRequireCitation);
  target.securityBlockInternalPromptLeakage = asBoolean(
    promptLeakagePolicy?.block_internal_prompt_leakage,
    target.securityBlockInternalPromptLeakage,
  );
  target.securityBlockSecretRefLeakage = asBoolean(
    promptLeakagePolicy?.block_secret_ref_leakage,
    target.securityBlockSecretRefLeakage,
  );
  target.securityPiiRedactionEnabled = asBoolean(piiRedactionPolicy?.enabled, target.securityPiiRedactionEnabled);
  target.securityRedactLogs = asBoolean(piiRedactionPolicy?.redact_logs, target.securityRedactLogs);
  target.securityRedactAuditSummary = asBoolean(
    piiRedactionPolicy?.redact_audit_summary,
    target.securityRedactAuditSummary,
  );
  target.timeoutQueryTotalMs = asNumber(timeout?.query_total_ms, target.timeoutQueryTotalMs);
  target.timeoutAuthPermissionMs = asNumber(timeout?.auth_permission_ms, target.timeoutAuthPermissionMs);
  target.timeoutRewriteMs = asNumber(timeout?.rewrite_ms, target.timeoutRewriteMs);
  target.timeoutEmbeddingMs = asNumber(timeout?.embedding_ms, target.timeoutEmbeddingMs);
  target.timeoutVectorSearchMs = asNumber(timeout?.vector_search_ms, target.timeoutVectorSearchMs);
  target.timeoutKeywordSearchMs = asNumber(timeout?.keyword_search_ms, target.timeoutKeywordSearchMs);
  target.timeoutRerankMs = asNumber(timeout?.rerank_ms, target.timeoutRerankMs);
  target.timeoutContextMs = asNumber(timeout?.context_ms, target.timeoutContextMs);
  target.timeoutPostprocessMs = asNumber(timeout?.postprocess_ms, target.timeoutPostprocessMs);
  target.degradeRewriteTimeout = asString(degrade?.rewrite_timeout, target.degradeRewriteTimeout);
  target.degradeEmbeddingTimeout = asString(degrade?.embedding_timeout, target.degradeEmbeddingTimeout);
  target.degradeVectorUnavailable = asString(degrade?.vector_unavailable, target.degradeVectorUnavailable);
  target.degradeKeywordUnavailable = asString(degrade?.keyword_unavailable, target.degradeKeywordUnavailable);
  target.degradeRerankTimeout = asString(degrade?.rerank_timeout, target.degradeRerankTimeout);
  target.degradeLlmTimeout = asString(degrade?.llm_timeout, target.degradeLlmTimeout);
  target.degradeModelPoolOverloaded = asString(
    degrade?.model_pool_overloaded,
    target.degradeModelPoolOverloaded,
  );
  target.degradeImportBacklog = asString(degrade?.import_backlog, target.degradeImportBacklog);
  target.observabilityMetricsEnabled = asBoolean(
    observability?.metrics_enabled,
    target.observabilityMetricsEnabled,
  );
  target.observabilityTraceEnabled = asBoolean(observability?.trace_enabled, target.observabilityTraceEnabled);
  target.alertActiveConfigLoadFailed = asNumber(
    alertThresholds?.active_config_load_failed,
    target.alertActiveConfigLoadFailed,
  );
  target.alertPermissionViolationRate = asNumber(
    alertThresholds?.permission_violation_rate,
    target.alertPermissionViolationRate,
  );
  target.alertDraftIndexExposureCount = asNumber(
    alertThresholds?.draft_index_exposure_count,
    target.alertDraftIndexExposureCount,
  );
  target.alertImportFailureRate = asNumber(alertThresholds?.import_failure_rate, target.alertImportFailureRate);
  target.alertWorkerQueueBacklog = asNumber(alertThresholds?.worker_queue_backlog, target.alertWorkerQueueBacklog);
  target.alertLlmTimeoutRate = asNumber(alertThresholds?.llm_timeout_rate, target.alertLlmTimeoutRate);
}

function buildCurrentConfigBundle(preferredItem: ConfigItemData | null = null): Record<string, unknown> {
  const config: Record<string, unknown> = activeConfigVersionRecord.value?.config
    ? cloneJsonRecord(activeConfigVersionRecord.value.config)
    : {
        schema_version: 1,
        config_version: activeConfigVersion.value,
        scope: {
          type: "global",
          id: "global",
        },
      };
  for (const item of activeConfigItems.value) {
    config[item.key] = cloneJsonRecord(item.value_json);
  }
  if (preferredItem) {
    config[preferredItem.key] = cloneJsonRecord(preferredItem.value_json);
  }
  return config;
}

function buildEditedActiveConfigBundle(): Record<string, unknown> | null {
  const baseConfig = currentEditableConfigBundle();
  const config = cloneJsonRecord(baseConfig);
  const formConfig = buildSetupPayload(configForm).config;
  for (const definition of configSectionDefinitions) {
    const formValue = asRecord(formConfig[definition.key]);
    if (!formValue) {
      continue;
    }
    config[definition.key] = mergeConfigSectionValue(
      definition.key,
      asRecord(config[definition.key]) ?? {},
      formValue,
    );
  }
  config.schema_version = asNumber(config.schema_version, 1);
  config.config_version = selectedConfigVersionNumber.value ?? activeConfigVersion.value;
  if (!isRecord(config.scope)) {
    config.scope = { type: "global", id: "global" };
  }
  return config;
}

function buildSelectedConfigSectionValue(): Record<string, unknown> | null {
  const definition = selectedConfigDefinition.value;
  const key = definition?.key;
  if (!definition || !key) {
    return null;
  }
  if (definition.fields.length === 0) {
    return parseConfigJsonText();
  }
  const baseValue = selectedConfigItem.value?.value_json ?? activeConfigItems.value.find((item) => item.key === key)?.value_json;
  const bundle = buildSetupPayload(configForm).config;
  const value = bundle[key];
  if (!isRecord(value)) {
    return null;
  }
  return mergeConfigSectionValue(key, baseValue, value);
}

function mergeConfigSectionValue(
  key: string,
  baseValue: Record<string, unknown> | undefined,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const base = baseValue ? cloneJsonRecord(baseValue) : {};
  if (key === "model_gateway") {
    return mergeModelGatewayConfig(base, formValue);
  }
  if (key === "model") {
    return mergeModelConfig(base, formValue);
  }
  if (key === "cache") {
    return mergeCacheConfig(base, formValue);
  }
  return deepMerge(base, formValue);
}

function mergeModelGatewayConfig(
  base: Record<string, unknown>,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const merged = deepMerge(base, formValue);
  preserveOptionalSecretRef(merged, base, formValue, "auth_token_ref");
  const formProviders = asRecord(formValue.providers);
  const providers = asRecord(merged.providers);
  const baseProviders = asRecord(base.providers);
  for (const key of ["embedding", "rerank", "llm"]) {
    const provider = asRecord(providers?.[key]);
    const formProvider = asRecord(formProviders?.[key]);
    const baseProvider = asRecord(baseProviders?.[key]);
    if (provider && formProvider) {
      preserveOptionalSecretRef(provider, baseProvider, formProvider, "auth_token_ref");
      provider.base_url = formProvider.base_url;
    }
  }
  const routes = asRecord(merged.routes);
  const formRoutes = asRecord(formValue.routes);
  const embeddingRoute = asRecord(routes?.embedding);
  const formEmbeddingRoute = asRecord(formRoutes?.embedding);
  if (embeddingRoute && formEmbeddingRoute) {
    embeddingRoute.online_default = formEmbeddingRoute.online_default;
    embeddingRoute.batch_default = formEmbeddingRoute.batch_default;
  }
  const rerankRoute = asRecord(routes?.rerank);
  const formRerankRoute = asRecord(formRoutes?.rerank);
  if (rerankRoute && formRerankRoute) {
    rerankRoute.default = formRerankRoute.default;
  }
  const llmRoute = asRecord(routes?.llm);
  const formLlmRoute = asRecord(formRoutes?.llm);
  if (llmRoute && formLlmRoute) {
    llmRoute.default = formLlmRoute.default;
    llmRoute.fallback = formLlmRoute.fallback;
  }
  return merged;
}

function preserveOptionalSecretRef(
  target: Record<string, unknown>,
  base: Record<string, unknown> | null,
  patch: Record<string, unknown> | null,
  key: string,
): void {
  const baseValue = base?.[key];
  const patchValue = patch?.[key];
  if (
    typeof baseValue === "string" &&
    baseValue.trim().length > 0 &&
    (patchValue === null || patchValue === undefined || patchValue === "")
  ) {
    target[key] = baseValue;
  }
}

function mergeModelConfig(
  base: Record<string, unknown>,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const merged = deepMerge(base, formValue);
  for (const key of [
    "embedding_model",
    "embedding_dimension",
    "rerank_model",
    "llm_model",
    "llm_fallback_model",
  ]) {
    merged[key] = formValue[key];
  }
  return merged;
}

function mergeCacheConfig(
  base: Record<string, unknown>,
  formValue: Record<string, unknown>,
): Record<string, unknown> {
  const merged = deepMerge(base, formValue);
  merged.final_answer_ttl_seconds = formValue.final_answer_enabled === true ? 300 : 0;
  return merged;
}

function deepMerge(
  base: Record<string, unknown>,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const result = cloneJsonRecord(base);
  for (const [key, value] of Object.entries(patch)) {
    const baseChild = asRecord(result[key]);
    if (baseChild && isRecord(value) && !Array.isArray(value)) {
      result[key] = deepMerge(baseChild, value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

function cloneJsonRecord(value: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
}

function validateConfigForm(): string | null {
  for (const field of configEditableFields()) {
    const value = configForm[field.key];
    if (field.required && isBlankFieldValue(value)) {
      return `${field.label} 为必填项。`;
    }
    if (field.input === "number") {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return `${field.label} 必须是有效数字。`;
      }
      if (field.min !== undefined && numberValue < field.min) {
        return `${field.label} 不能小于 ${field.min}。`;
      }
    }
  }
  return null;
}

function updateConfigJsonText(value: string): void {
  configJsonText.value = value;
  resetConfigValidationState();
}

function parseConfigJsonText(): Record<string, unknown> | null {
  const text = configJsonText.value.trim();
  if (!text) {
    return null;
  }
  try {
    const parsed = JSON.parse(text);
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function configFormSignature(): string {
  const value = buildEditedActiveConfigBundle();
  return JSON.stringify(
    {
      version: selectedConfigVersionNumber.value,
      value,
    },
    null,
    2,
  );
}

function currentEditableConfigBundle(): Record<string, unknown> {
  const source =
    selectedConfigVersionNumber.value === null
      ? activeConfigVersionRecord.value?.config
      : configVersionDetails.value[selectedConfigVersionNumber.value]?.config;
  return source ? cloneJsonRecord(source) : {};
}

function configEditableFields(): FieldDefinition[] {
  return configSectionDefinitions.flatMap((definition) => definition.fields);
}

function configNormalFields(definition: ConfigSectionFormDefinition): FieldDefinition[] {
  return definition.fields.filter((field) => field.input !== "checkbox");
}

function configCheckboxFields(definition: ConfigSectionFormDefinition): FieldDefinition[] {
  return definition.fields.filter((field) => field.input === "checkbox");
}

function isBlankFieldValue(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === "string" && value.trim() === "");
}

function configVersionPreview(version: ConfigVersionData | ConfigVersionListItemData): string {
  const config = "config" in version ? version.config : null;
  if (!config) {
    return "配置详情按需加载";
  }
  const keys = Object.keys(config).filter(
    (key) => !["schema_version", "config_version", "scope"].includes(key),
  );
  const head = keys.slice(0, 6).join(" / ");
  return keys.length > 6 ? `${head} / 等 ${keys.length} 项` : head || "无配置项";
}

function isEditableConfigVersion(version: ConfigVersionData | ConfigVersionListItemData): boolean {
  return version.status !== "archived";
}

function isActivatableConfigVersion(version: ConfigVersionData | ConfigVersionListItemData): boolean {
  return version.status !== "active" && version.status !== "archived";
}

function isArchivableConfigVersion(version: ConfigVersionData | ConfigVersionListItemData): boolean {
  return version.status !== "active" && version.status !== "archived";
}

function formatDateTime(value: string | null): string {
  return formatAuditTime(value);
}

function configSectionLabel(key: string): string {
  return configDefinitionForKey(key)?.label ?? key;
}

function configSectionDescription(key: string): string {
  return configDefinitionForKey(key)?.description ?? "当前配置项来自 active_config 顶层分组。";
}

function configStatusTone(status: string): Tone {
  if (status === "active") {
    return "success";
  }
  if (status === "failed") {
    return "error";
  }
  if (status === "draft" || status === "validating") {
    return "warning";
  }
  return "neutral";
}

function asString(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asVectorDistance(value: unknown, fallback: SetupFormModel["vectorDistance"]): SetupFormModel["vectorDistance"] {
  return value === "cosine" || value === "dot" || value === "euclidean" ? value : fallback;
}

function asModelGatewayMode(value: unknown, fallback: SetupFormModel["modelGatewayMode"]): SetupFormModel["modelGatewayMode"] {
  return value === "external" ? value : fallback;
}

function asChunkStrategyMode(value: unknown, fallback: SetupFormModel["chunkStrategyMode"]): SetupFormModel["chunkStrategyMode"] {
  return value === "heading_paragraph" || value === "fixed_tokens" ? value : fallback;
}

function asAuditQueryTextMode(value: unknown, fallback: SetupFormModel["auditQueryTextMode"]): SetupFormModel["auditQueryTextMode"] {
  return value === "none" || value === "hash" || value === "plain" ? value : fallback;
}

function asPermissionVisibility(
  value: unknown,
  fallback: SetupFormModel["permissionDefaultVisibility"],
): SetupFormModel["permissionDefaultVisibility"] {
  return value === "department" || value === "enterprise" ? value : fallback;
}

function formatAuditTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function parseBooleanFilter(value: string): boolean | null {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return null;
}

function resetDiagnosticsFilters(): void {
  queryLogSearchForm.userId = "";
  queryLogSearchForm.kbId = "";
  queryLogSearchForm.status = "";
  queryLogSearchForm.degraded = "";
  queryLogSearchForm.degradeReason = "";
  queryLogSearchForm.requestId = "";
  queryLogSearchForm.traceId = "";
  queryLogSearchForm.errorCode = "";
  modelCallSearchForm.model = "";
  modelCallSearchForm.modelType = "";
  modelCallSearchForm.caller = "";
  modelCallSearchForm.status = "";
  modelCallSearchForm.degraded = "";
  modelCallSearchForm.requestId = "";
  modelCallSearchForm.traceId = "";
  modelCallSearchForm.errorCode = "";
  queryLogPagination.page = 1;
  modelCallLogPagination.page = 1;
  queryLogDetailModalOpen.value = false;
  modelCallLogDetailModalOpen.value = false;
}

function queryLogStatusTone(log: QueryLogDisplayData): Tone {
  if (log.status === "success" && !log.degraded) {
    return "success";
  }
  if (log.status === "denied" || log.degraded) {
    return "warning";
  }
  return "error";
}

function modelCallStatusTone(log: ModelCallLogDisplayData): Tone {
  if (log.status === "success" && !log.degraded) {
    return "success";
  }
  if (log.status === "degraded" || log.degraded) {
    return "warning";
  }
  return "error";
}

function indexHealthTone(item: IndexCollectionHealthData): Tone {
  if (item.issues.length === 0) {
    return "success";
  }
  if (
    item.issues.some((issue) =>
      [
        "qdrant_unreachable",
        "qdrant_collection_missing",
        "qdrant_vector_size_mismatch",
        "qdrant_points_less_than_active_refs",
        "active_index_ref_count_mismatch",
      ].includes(issue),
    )
  ) {
    return "error";
  }
  return "warning";
}

function formatIssueList(issues: string[]): string {
  return issues.length ? issues.join(" / ") : "无";
}

function formatLatency(value: number): string {
  return `${value} ms`;
}

function formatShortIdentifier(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function formatQueryLogTitle(log: QueryLogDisplayData): string {
  return `${formatAuditTime(log.created_at)} / ${formatQueryLogStatus(log)}`;
}

function formatQueryLogUser(log: QueryLogDisplayData): string {
  return log.user_display_name || "未知用户";
}

function formatQueryLogKnowledgeBases(log: QueryLogDisplayData): string {
  if (log.knowledge_base_names.length) {
    return log.knowledge_base_names.join("，");
  }
  if ("kb_ids" in log && log.kb_ids.length) {
    return `${log.kb_ids.length} 个知识库`;
  }
  return "-";
}

function formatTokenUsage(value: Record<string, unknown> | null): string {
  if (!value) {
    return "-";
  }
  const entries = Object.entries(value).slice(0, 4);
  return entries.map(([key, entryValue]) => `${key}: ${String(entryValue)}`).join(" / ");
}

function auditSummaryPreview(log: AuditLogListItemData): string {
  const version = log.config_version ? `v${log.config_version}` : "";
  const permissionVersion = log.permission_version ? `权限 v${log.permission_version}` : "";
  const resource = log.resource_type ? formatStatusText(log.resource_type) : "";
  const action = log.action ? formatStatusText(log.action) : "";
  return [version, permissionVersion, resource, action].filter(Boolean).join(" / ") || "-";
}

function normalizeIssueCode(issue: SetupIssue): string {
  return issue.error_code ?? issue.code ?? "ISSUE";
}

function normalizeErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const code = error.payload?.error_code ? `${error.payload.error_code}: ` : "";
    return `${code}${error.payload?.message ?? error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function extractStructuredIssues(payload: ApiErrorPayload | null): SetupIssue[] {
  // 后端校验错误放在 details.errors 中，页面只消费结构化数组，避免解析自由文本。
  const details = asRecord(payload?.details);
  const errors = details?.errors;
  return Array.isArray(errors) ? errors.filter((item): item is SetupIssue => isRecord(item)) : [];
}

function extractBootstrapChecks(payload: ApiErrorPayload | null): BootstrapCheckIssue[] {
  // 初始化失败时后端会返回依赖检查详情，用于定位 Redis/MinIO/Qdrant/模型服务问题。
  const details = asRecord(payload?.details);
  const checks = details?.checks;
  if (!Array.isArray(checks)) {
    return [];
  }
  return checks
    .filter((item): item is Record<string, unknown> => isRecord(item))
    .map((item) => ({
      name: typeof item.name === "string" ? item.name : "unknown",
      status: typeof item.status === "string" ? item.status : "unknown",
      message: typeof item.message === "string" ? item.message : "",
      required: item.required !== false,
      latency_ms: typeof item.latency_ms === "number" ? item.latency_ms : undefined,
    }));
}

function extractDatabaseError(payload: ApiErrorPayload | null): DatabaseErrorIssue | null {
  // 数据库异常单独抽取，方便页面展示表、列、约束等诊断信息。
  const details = asRecord(payload?.details);
  const databaseError = details?.database_error;
  if (!isRecord(databaseError)) {
    return null;
  }
  return {
    type: asOptionalString(databaseError.type),
    driver_type: asOptionalString(databaseError.driver_type),
    message: asOptionalString(databaseError.message),
    sqlstate: asOptionalString(databaseError.sqlstate),
    constraint: asOptionalString(databaseError.constraint),
    table: asOptionalString(databaseError.table),
    column: asOptionalString(databaseError.column),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function validateLocalForm(
  current: SetupFormModel,
  currentSetupState: SetupStateData | null,
): LocalValidationIssue[] {
  // 本地校验只处理确定性规则；服务连通性、配置契约和权限状态由后端再次校验。
  const issues: LocalValidationIssue[] = [];
  const add = (
    tone: LocalIssueTone,
    section: string,
    message: string,
    field?: keyof SetupFormModel,
  ) => {
    issues.push({ tone, section, message, field });
  };

  if (currentSetupState?.initialized && currentSetupState.recovery_setup_allowed !== true) {
    add("error", "访问凭证", "系统已初始化，不能再次提交初始化。");
  }
  if (!current.setupToken.trim()) {
    add("error", "访问凭证", "必须填写启动日志中打印的初始化 JWT。", "setupToken");
  } else if (!looksLikeJwt(current.setupToken)) {
    add("warning", "访问凭证", "初始化令牌不是标准 JWT 三段格式。", "setupToken");
  }

  if (!/^[A-Za-z0-9._-]{3,64}$/.test(current.adminUsername)) {
    add("error", "首个管理员", "登录名只能包含字母、数字、点、下划线或连字符，长度 3 到 64。", "adminUsername");
  }
  if (!current.adminDisplayName.trim()) {
    add("error", "首个管理员", "管理员显示名不能为空。", "adminDisplayName");
  }
  if (current.adminPassword.length < current.passwordMinLength) {
    add("error", "首个管理员", "初始密码长度不能小于密码策略。", "adminPassword");
  }
  if (!/[A-Z]/.test(current.adminPassword) || !/[a-z]/.test(current.adminPassword) || !/\d/.test(current.adminPassword)) {
    add("error", "首个管理员", "初始密码必须同时包含大写字母、小写字母和数字。", "adminPassword");
  }
  if (!current.adminPasswordConfirm) {
    add("error", "首个管理员", "请再次输入初始密码。", "adminPasswordConfirm");
  } else if (current.adminPasswordConfirm !== current.adminPassword) {
    add("error", "首个管理员", "两次输入的管理员密码不一致。", "adminPasswordConfirm");
  }
  if (current.adminPassword === "ChangeMe_123456") {
    add("warning", "首个管理员", "当前仍是本地默认密码。", "adminPassword");
  }
  if (current.adminEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(current.adminEmail)) {
    add("error", "首个管理员", "邮箱格式不合法。", "adminEmail");
  }
  if (current.adminPhone.length > 32) {
    add("error", "首个管理员", "手机号长度不能超过 32。", "adminPhone");
  }

  validateRequiredCode(current.enterpriseCode, "企业编码", "enterpriseCode", "组织初始化", add);
  validateRequiredCode(current.departmentCode, "默认部门编码", "departmentCode", "组织初始化", add);
  if (!current.enterpriseName.trim()) {
    add("error", "组织初始化", "企业名称不能为空。", "enterpriseName");
  }
  if (!current.departmentName.trim()) {
    add("error", "组织初始化", "默认部门名称不能为空。", "departmentName");
  }

  if (!current.secretProviderEndpoint.trim()) {
    add("error", "基础设施", "密钥服务地址不能为空。", "secretProviderEndpoint");
  }
  if (!current.redisUrl.startsWith("redis://")) {
    add("error", "基础设施", "Redis 地址必须以 redis:// 开头。", "redisUrl");
  }
  validateHttpUrl(current.minioEndpoint, "MinIO 地址", "minioEndpoint", "基础设施", add);
  validateHttpUrl(current.qdrantBaseUrl, "Qdrant 地址", "qdrantBaseUrl", "基础设施", add);
  validateOptionalSecretRef(current.qdrantApiKeyRef, "Qdrant API Key 引用", "qdrantApiKeyRef", "基础设施", add);
  if (!/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(current.minioBucket)) {
    add("error", "基础设施", "存储桶名称需符合 S3 命名规则。", "minioBucket");
  }
  if (!current.minioRegion.trim()) {
    add("error", "基础设施", "存储区域不能为空。", "minioRegion");
  }
  if (current.objectKeyPrefix.startsWith("/")) {
    add("error", "基础设施", "对象路径前缀不能以 / 开头。", "objectKeyPrefix");
  }
  if (!current.objectKeyPrefix.endsWith("/")) {
    add("warning", "基础设施", "对象路径前缀建议以 / 结尾。", "objectKeyPrefix");
  }
  validateSecretRef(current.minioAccessKeyRef, "MinIO 访问密钥引用", "minioAccessKeyRef", "基础设施", add);
  validateSecretRef(current.minioSecretKeyRef, "MinIO 私有密钥引用", "minioSecretKeyRef", "基础设施", add);
  validateCollectionPrefix(current.collectionPrefix, add);

  if (current.modelGatewayMode !== "external") {
    add("error", "模型与检索", "模型服务模式必须为外部服务。", "modelGatewayMode");
  }
  validateHttpUrl(current.embeddingProviderBaseUrl, "向量模型服务地址", "embeddingProviderBaseUrl", "模型与检索", add);
  validateHttpUrl(current.rerankProviderBaseUrl, "重排模型服务地址", "rerankProviderBaseUrl", "模型与检索", add);
  if (!current.llmProviderBaseUrl.trim()) {
    add("error", "模型与检索", "当前 compose 未创建大模型服务，必须填写真实大模型服务地址。", "llmProviderBaseUrl");
  } else {
    validateHttpUrl(current.llmProviderBaseUrl, "大模型服务地址", "llmProviderBaseUrl", "模型与检索", add);
  }
  if (isComposeDemoProvider(current.embeddingProviderBaseUrl) || isComposeDemoProvider(current.rerankProviderBaseUrl)) {
    add("warning", "模型与检索", "当前 TEI 容器服务仅适合本地演示，生产应替换为真实模型服务。");
  }
  if (!Number.isInteger(current.embeddingDimension) || current.embeddingDimension <= 0) {
    add("error", "模型与检索", "向量维度必须是正整数。", "embeddingDimension");
  }
  validateNonEmpty(current.embeddingModel, "向量模型", "embeddingModel", "模型与检索", add);
  validateNonEmpty(current.rerankModel, "重排模型", "rerankModel", "模型与检索", add);
  validateNonEmpty(current.llmModel, "主大模型", "llmModel", "模型与检索", add);
  validateNonEmpty(current.llmFallbackModel, "回退大模型", "llmFallbackModel", "模型与检索", add);
  if (current.finalContextTopK > current.rerankInputTopK) {
    add("error", "模型与检索", "最终上下文数量不能大于重排输入数量。", "finalContextTopK");
  }
  if (current.rerankInputTopK > current.vectorTopK + current.keywordTopK) {
    add("warning", "模型与检索", "重排输入数量大于向量和关键词召回总量。", "rerankInputTopK");
  }
  if (!Number.isFinite(current.rerankMinScore) || current.rerankMinScore < 0) {
    add("error", "模型与检索", "重排最低分必须是非负数字。", "rerankMinScore");
  }

  if (!Number.isInteger(current.chunkDefaultSizeTokens) || current.chunkDefaultSizeTokens <= 0) {
    add("error", "文档切片策略", "切片大小 Token 数必须是正整数。", "chunkDefaultSizeTokens");
  }
  if (!Number.isInteger(current.chunkOverlapTokens) || current.chunkOverlapTokens < 0) {
    add("error", "文档切片策略", "切片重叠 Token 数必须是非负整数。", "chunkOverlapTokens");
  }
  if (current.chunkOverlapTokens >= current.chunkDefaultSizeTokens) {
    add("error", "文档切片策略", "切片重叠 Token 数必须小于切片大小 Token 数。", "chunkOverlapTokens");
  }
  if (!["heading_paragraph", "fixed_tokens"].includes(current.chunkStrategyMode)) {
    add("error", "文档切片策略", "切片策略必须是 heading_paragraph 或 fixed_tokens。", "chunkStrategyMode");
  }
  if (current.chunkDefaultSizeTokens > 1200) {
    add("warning", "文档切片策略", "切片过大会降低细粒度召回效果，并增加上下文裁剪压力。", "chunkDefaultSizeTokens");
  }

  if (current.passwordMinLength < 12) {
    add("warning", "认证与运行策略", "生产环境建议密码最小长度不低于 12。", "passwordMinLength");
  }
  if (current.refreshTokenTtlMinutes <= current.accessTokenTtlMinutes) {
    add("error", "认证与运行策略", "刷新令牌有效期必须大于访问令牌有效期。", "refreshTokenTtlMinutes");
  }
  validateNonEmpty(current.jwtIssuer, "JWT 签发方", "jwtIssuer", "认证与运行策略", add);
  validateNonEmpty(current.jwtAudience, "JWT 受众", "jwtAudience", "认证与运行策略", add);
  validateSecretRef(current.jwtSigningKeyRef, "JWT 签名密钥引用", "jwtSigningKeyRef", "认证与运行策略", add);
  if (current.auditQueryTextMode === "plain") {
    add("warning", "认证与运行策略", "记录明文会保存查询原文，需确认审计和隐私策略。", "auditQueryTextMode");
  }

  if (current.finalAnswerEnabled) {
    add("warning", "缓存开关", "最终答案缓存会放大权限变更后的风险，P0 默认应关闭。", "finalAnswerEnabled");
  }
  if (current.crossUserFinalAnswerAllowed) {
    add("error", "缓存开关", "不允许跨用户复用最终答案缓存。", "crossUserFinalAnswerAllowed");
  }

  return issues;
}

function validateRequiredCode(
  value: string,
  label: string,
  field: keyof SetupFormModel,
  section: string,
  add: (tone: LocalIssueTone, section: string, message: string, field?: keyof SetupFormModel) => void,
): void {
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(value)) {
    add("error", section, `${label}只能包含字母、数字、下划线或连字符，长度 1 到 64。`, field);
  }
}

function validateHttpUrl(
  value: string,
  label: string,
  field: keyof SetupFormModel,
  section: string,
  add: (tone: LocalIssueTone, section: string, message: string, field?: keyof SetupFormModel) => void,
): void {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      add("error", section, `${label} 必须使用 http:// 或 https://。`, field);
    }
  } catch {
    add("error", section, `${label} 不是合法 URL。`, field);
  }
}

function validateSecretRef(
  value: string,
  label: string,
  field: keyof SetupFormModel,
  section: string,
  add: (tone: LocalIssueTone, section: string, message: string, field?: keyof SetupFormModel) => void,
): void {
  if (!/^secret:\/\/rag\/[A-Za-z0-9._-]+\/[A-Za-z0-9._/-]+$/.test(value)) {
    add("error", section, `${label} 必须使用 secret://rag/... 引用。`, field);
  }
}

function validateOptionalSecretRef(
  value: string,
  label: string,
  field: keyof SetupFormModel,
  section: string,
  add: (tone: LocalIssueTone, section: string, message: string, field?: keyof SetupFormModel) => void,
): void {
  if (value.trim()) {
    validateSecretRef(value, label, field, section, add);
  }
}

function validateCollectionPrefix(
  value: string,
  add: (tone: LocalIssueTone, section: string, message: string, field?: keyof SetupFormModel) => void,
): void {
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value)) {
    add("error", "基础设施", "向量集合前缀必须以字母开头，只能包含字母、数字、下划线或连字符。", "collectionPrefix");
  }
}

function validateNonEmpty(
  value: string,
  label: string,
  field: keyof SetupFormModel,
  section: string,
  add: (tone: LocalIssueTone, section: string, message: string, field?: keyof SetupFormModel) => void,
): void {
  if (!value.trim()) {
    add("error", section, `${label}不能为空。`, field);
  }
}

function looksLikeJwt(value: string): boolean {
  return value.split(".").length === 3;
}

function isComposeDemoProvider(value: string): boolean {
  return value.includes("tei-embedding") || value.includes("tei-rerank");
}
</script>

<template>
  <main v-if="activeView === 'loading'" class="auth-screen">
    <section class="login-card">
      <p class="brand">Little Bear 管理后台</p>
      <h1 class="title">正在检查系统状态</h1>
      <p class="auth-copy">正在读取初始化状态和本地登录态。</p>
    </section>
  </main>

  <main v-else-if="activeView === 'login'" class="auth-screen">
    <section class="login-card">
      <div class="login-card__header">
        <p class="brand">Little Bear 管理后台</p>
        <h1 class="title">登录管理后台</h1>
        <p class="auth-copy">当前为单企业部署，请使用系统管理员账号进入管理后台。</p>
      </div>

      <form class="login-form" @submit.prevent="submitLogin">
        <label class="field field--full">
          <span class="field__label">登录名</span>
          <p class="field__hint">请输入初始化时创建的管理员登录名。</p>
          <input
            v-model.trim="loginForm.username"
            class="control"
            type="text"
            autocomplete="username"
            required
          />
        </label>
        <label class="field field--full">
          <span class="field__label">密码</span>
          <p class="field__hint">密码只用于本次登录请求，不会保存在前端状态中。</p>
          <input
            v-model="loginForm.password"
            class="control"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>

        <div v-if="authFeedback" :class="['feedback', `feedback--${authFeedback.tone}`]">
          {{ authFeedback.message }}
        </div>

        <button class="button" type="submit" :disabled="authBusy.loggingIn">
          {{ authBusy.loggingIn ? "登录中..." : "登录" }}
        </button>
      </form>
    </section>
  </main>

  <main v-else-if="activeView === 'dashboard'" class="admin-shell">
    <aside class="admin-sidebar">
      <div class="sidebar__block">
        <p class="brand">Little Bear 管理后台</p>
        <h1 class="title">运行控制台</h1>
      </div>
      <nav class="admin-nav" aria-label="管理后台导航">
        <button
          v-for="tab in visibleAdminTabs"
          :key="tab.key"
          :class="['admin-nav__item', { 'admin-nav__item--active': selectedAdminTab === tab.key }]"
          type="button"
          @click="switchAdminTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </nav>
    </aside>

    <section class="admin-workspace">
      <header class="admin-toolbar">
        <div>
          <p class="eyebrow">/admin</p>
          <h2>管理后台</h2>
        </div>
        <div class="user-menu">
          <div>
            <strong>{{ userDisplayName }}</strong>
            <span>{{ userRoleLabels }}</span>
          </div>
          <button class="button button--secondary" type="button" @click="logout" :disabled="authBusy.loggingOut">
            {{ authBusy.loggingOut ? "退出中..." : "退出登录" }}
          </button>
        </div>
      </header>

      <section class="dashboard-grid">
        <section v-if="selectedAdminTab === 'config' && canAccessAdminTab('config')" class="panel">
          <header class="panel__header">
            <h3>当前用户</h3>
            <span :class="toneClass(authenticated ? 'success' : 'neutral')">
              {{ authenticated ? "已登录" : "未登录" }}
            </span>
          </header>
          <dl v-if="currentUser" class="summary">
            <div class="summary__row">
              <dt>登录名</dt>
              <dd>{{ currentUser.username }}</dd>
            </div>
            <div class="summary__row">
              <dt>显示名</dt>
              <dd>{{ currentUser.name }}</dd>
            </div>
            <div class="summary__row">
              <dt>账号状态</dt>
              <dd>{{ formatStatusText(currentUser.status) }}</dd>
            </div>
            <div class="summary__row">
              <dt>角色</dt>
              <dd>{{ userRoleLabels }}</dd>
            </div>
          </dl>
        </section>

        <section
          v-if="selectedAdminTab === 'departments' && canAccessAdminTab('departments')"
          class="panel panel--wide"
        >
          <header class="panel__header">
            <div>
              <h3>部门管理</h3>
              <p :class="toneClass(canLoadDepartmentAdmin ? 'success' : 'warning')">
                {{
                  canManageDepartments
                    ? "可创建、修改和删除部门"
                    : canReadDepartments
                      ? "可读取部门"
                      : "缺少组织权限"
                }}
              </p>
            </div>
            <div class="panel__actions">
              <button
                class="button button--secondary"
                type="button"
                @click="refreshDepartmentAdminState"
                :disabled="departmentAdminBusy.loading || !canLoadDepartmentAdmin"
              >
                {{ departmentAdminBusy.loading ? "刷新中" : "刷新部门" }}
              </button>
              <button
                class="button"
                type="button"
                @click="openCreateDepartmentModal"
                :disabled="!canManageDepartments"
              >
                新增部门
              </button>
            </div>
          </header>

          <div class="admin-list-panel">
            <div
              v-if="departmentAdminFeedback"
              :class="['feedback feedback--wide', `feedback--${departmentAdminFeedback.tone}`]"
            >
              {{ departmentAdminFeedback.message }}
            </div>

            <form class="list-filter" @submit.prevent="refreshFirstPage(departmentPagination, refreshDepartmentAdminState)">
              <label class="field">
                <span class="field__label">关键词</span>
                <p class="field__hint">按部门名称过滤。</p>
                <input v-model.trim="departmentSearchForm.keyword" class="control" type="text" />
              </label>
              <label class="field">
                <span class="field__label">部门状态</span>
                <p class="field__hint">留空时显示全部未删除部门。</p>
                <select v-model="departmentSearchForm.status" class="control">
                  <option value="">全部</option>
                  <option value="active">{{ formatStatusOption("active") }}</option>
                  <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                </select>
              </label>
              <button class="button button--secondary" type="submit" :disabled="departmentAdminBusy.loading">
                查询
              </button>
            </form>

            <div v-if="adminDepartments.length" class="entity-table entity-table--departments">
              <div class="entity-table__row entity-table__row--header">
                <span>部门</span>
                <span>状态</span>
                <span>默认部门</span>
                <span>操作</span>
              </div>
              <article v-for="department in adminDepartments" :key="department.id" class="entity-table__row">
                <div class="entity-main">
                  <strong>{{ department.name }}</strong>
                  <span>{{ department.is_default ? "默认组织部门" : "普通部门" }}</span>
                </div>
                <div class="entity-cell">
                  <span :class="toneClass(department.status === 'active' ? 'success' : 'neutral')">
                    {{ formatStatusText(department.status) }}
                  </span>
                </div>
                <div class="entity-cell">{{ department.is_default ? "是" : "否" }}</div>
                <div class="row-actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openEditDepartmentModal(department)"
                    :disabled="!canManageDepartments"
                  >
                    编辑
                  </button>
                  <button
                    class="button button--danger button--small"
                    type="button"
                    @click="openDeleteDepartmentModal(department)"
                    :disabled="!canManageDepartments || department.is_default"
                  >
                    删除
                  </button>
                </div>
              </article>
            </div>
            <p v-else class="empty-state empty-state--plain">当前尚未读取到部门。</p>
            <div v-if="departmentPagination.total > 0" class="pagination-bar" aria-label="部门列表分页">
              <span>
                第 {{ departmentPagination.page }} / {{ paginationTotalPages(departmentPagination) }} 页，
                {{ paginationStart(departmentPagination) }}-{{ paginationEnd(departmentPagination) }} /
                {{ departmentPagination.total }} 条
              </span>
              <label>
                每页
                <select
                  v-model.number="departmentPagination.pageSize"
                  class="control control--compact"
                  :disabled="departmentAdminBusy.loading"
                  @change="changePaginationPageSize(departmentPagination, refreshDepartmentAdminState)"
                >
                  <option v-for="size in pageSizeOptions" :key="`department-page-size-${size}`" :value="size">
                    {{ size }}
                  </option>
                </select>
              </label>
              <div class="pagination-bar__actions">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="departmentAdminBusy.loading || departmentPagination.page <= 1"
                  @click="changePaginationPage(departmentPagination, refreshDepartmentAdminState, departmentPagination.page - 1)"
                >
                  上一页
                </button>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="departmentAdminBusy.loading || departmentPagination.page >= paginationTotalPages(departmentPagination)"
                  @click="changePaginationPage(departmentPagination, refreshDepartmentAdminState, departmentPagination.page + 1)"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </section>

        <section v-if="selectedAdminTab === 'users' && canAccessAdminTab('users')" class="panel panel--wide">
          <header class="panel__header">
            <div>
              <h3>用户管理</h3>
              <p :class="toneClass(canLoadUserAdmin ? 'success' : 'warning')">
                {{
                  canManageUsers && canManageRoles
                    ? "可管理用户、部门归属和角色绑定"
                    : canReadUsers || canReadRoles
                      ? "可读取用户信息"
                      : "缺少用户或角色权限"
                }}
              </p>
            </div>
            <div class="panel__actions">
              <button
                class="button button--secondary"
                type="button"
                @click="refreshUserRoleAdminState"
                :disabled="userAdminBusy.loading || !canLoadUserAdmin"
              >
                {{ userAdminBusy.loading ? "刷新中" : "刷新用户" }}
              </button>
              <button class="button" type="button" @click="openCreateUserModal" :disabled="!canManageUsers">
                新增用户
              </button>
            </div>
          </header>

          <div class="admin-list-panel">
            <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
              {{ userAdminFeedback.message }}
            </div>

            <form class="list-filter" @submit.prevent="refreshFirstPage(userPagination, refreshUserRoleAdminState)">
              <label class="field">
                <span class="field__label">关键词</span>
                <p class="field__hint">按登录名或显示名过滤用户。</p>
                <input v-model.trim="userSearchForm.keyword" class="control" type="text" />
              </label>
              <label class="field">
                <span class="field__label">账号状态</span>
                <p class="field__hint">留空时显示全部未删除用户。</p>
                <select v-model="userSearchForm.status" class="control">
                  <option value="">全部</option>
                  <option value="active">{{ formatStatusOption("active") }}</option>
                  <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                  <option value="locked">{{ formatStatusOption("locked") }}</option>
                </select>
              </label>
              <button class="button button--secondary" type="submit" :disabled="userAdminBusy.loading">
                查询
              </button>
            </form>

            <div v-if="adminUsers.length" class="entity-table entity-table--users">
              <div class="entity-table__row entity-table__row--header">
                <span>用户</span>
                <span>状态</span>
                <span>部门</span>
                <span>角色</span>
                <span>操作</span>
              </div>
              <article v-for="user in adminUsers" :key="user.id" class="entity-table__row">
                <div class="entity-main">
                  <strong>{{ user.name || user.username }}</strong>
                  <span>{{ user.username }}</span>
                </div>
                <div class="entity-cell">
                  <span :class="toneClass(user.status === 'active' ? 'success' : user.status === 'locked' ? 'warning' : 'neutral')">
                    {{ formatStatusText(user.status) }}
                  </span>
                </div>
                <div class="badge-list">
                  <span v-for="departmentName in user.department_names" :key="departmentName" class="badge">
                    {{ departmentName }}
                  </span>
                  <span v-if="!user.department_names.length" class="empty-inline">-</span>
                </div>
                <div class="badge-list">
                  <span v-for="roleName in user.role_names" :key="roleName" class="badge">
                    {{ roleName }}
                  </span>
                  <span v-if="!user.role_names.length" class="empty-inline">-</span>
                </div>
                <div class="row-actions row-actions--dense row-actions--knowledge">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openEditUserModal(user)"
                    :disabled="!canManageUsers"
                  >
                    编辑
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openUserDepartmentsModal(user)"
                    :disabled="!canReadDepartments"
                  >
                    部门
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openUserRolesModal(user)"
                    :disabled="!canReadRoles"
                  >
                    角色
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openPasswordResetModal(user)"
                    :disabled="!canManageUsers"
                  >
                    密码
                  </button>
                  <button
                    class="button button--danger button--small"
                    type="button"
                    @click="openDeleteUserModal(user)"
                    :disabled="!canManageUsers"
                  >
                    删除
                  </button>
                </div>
              </article>
            </div>
            <p v-else class="empty-state empty-state--plain">当前尚未读取到用户。</p>
            <div v-if="userPagination.total > 0" class="pagination-bar" aria-label="用户列表分页">
              <span>
                第 {{ userPagination.page }} / {{ paginationTotalPages(userPagination) }} 页，
                {{ paginationStart(userPagination) }}-{{ paginationEnd(userPagination) }} /
                {{ userPagination.total }} 条
              </span>
              <label>
                每页
                <select
                  v-model.number="userPagination.pageSize"
                  class="control control--compact"
                  :disabled="userAdminBusy.loading"
                  @change="changePaginationPageSize(userPagination, refreshUserRoleAdminState)"
                >
                  <option v-for="size in pageSizeOptions" :key="`user-page-size-${size}`" :value="size">
                    {{ size }}
                  </option>
                </select>
              </label>
              <div class="pagination-bar__actions">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="userAdminBusy.loading || userPagination.page <= 1"
                  @click="changePaginationPage(userPagination, refreshUserRoleAdminState, userPagination.page - 1)"
                >
                  上一页
                </button>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="userAdminBusy.loading || userPagination.page >= paginationTotalPages(userPagination)"
                  @click="changePaginationPage(userPagination, refreshUserRoleAdminState, userPagination.page + 1)"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="selectedAdminTab === 'knowledge' && canAccessAdminTab('knowledge')"
          class="panel panel--wide"
        >
          <header class="panel__header">
            <div>
              <h3>知识库管理</h3>
              <p :class="toneClass(canLoadImportAdmin ? 'success' : 'warning')">
                {{
                  canManageKnowledgeBases
                    ? "可管理知识库并添加文档"
                    : canImportDocuments
                      ? "可向指定知识库添加文档"
                      : canReadImportJobs
                        ? "可读取导入任务"
                        : "缺少知识库或导入权限"
                }}
              </p>
            </div>
            <div class="panel__actions">
              <button
                class="button button--secondary"
                type="button"
                @click="refreshKnowledgeBaseAdminState"
                :disabled="importAdminBusy.loading || !canLoadImportAdmin"
              >
                {{ importAdminBusy.loading ? "刷新中" : "刷新知识库" }}
              </button>
              <button
                class="button"
                type="button"
                @click="openCreateKnowledgeBaseModal"
                :disabled="!canManageKnowledgeBases"
              >
                新增知识库
              </button>
            </div>
          </header>

          <div class="admin-list-panel">
            <div
              v-if="importAdminFeedback"
              :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]"
            >
              {{ importAdminFeedback.message }}
            </div>

            <form class="list-filter list-filter--knowledge" @submit.prevent="refreshFirstPage(knowledgeBasePagination, refreshKnowledgeBaseAdminState)">
              <label class="field">
                <span class="field__label">关键词</span>
                <p class="field__hint">按知识库名称过滤。</p>
                <input v-model.trim="knowledgeBaseSearchForm.keyword" class="control" type="text" />
              </label>
              <label class="field">
                <span class="field__label">知识库状态</span>
                <p class="field__hint">留空时显示全部未删除知识库。</p>
                <select v-model="knowledgeBaseSearchForm.status" class="control">
                  <option value="">全部</option>
                  <option value="active">{{ formatStatusOption("active") }}</option>
                  <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                  <option value="archived">{{ formatStatusOption("archived") }}</option>
                </select>
              </label>
              <button class="button button--secondary" type="submit" :disabled="importAdminBusy.loading">
                查询
              </button>
            </form>

            <div v-if="canManageKnowledgeBases && adminKnowledgeBases.length" class="entity-table entity-table--knowledge">
              <div class="entity-table__row entity-table__row--header">
                <span>知识库</span>
                <span>状态</span>
                <span>可见性</span>
                <span>所属部门</span>
                <span>操作</span>
              </div>
              <article v-for="knowledgeBase in adminKnowledgeBases" :key="knowledgeBase.id" class="entity-table__row">
                <div class="entity-main">
                  <strong>{{ knowledgeBase.name }}</strong>
                </div>
                <div class="entity-cell">
                  <span :class="toneClass(knowledgeBaseStatusTone(knowledgeBase.status))">
                    {{ formatStatusText(knowledgeBase.status) }}
                  </span>
                </div>
                <div class="entity-cell">
                  {{ knowledgeBaseVisibilityLabel(knowledgeBase.kb_visibility) }} /
                  默认文档{{ documentVisibilityLabel(knowledgeBase.default_document_visibility) }}
                </div>
                <div class="entity-cell">{{ formatDepartmentById(knowledgeBase.owner_department_id) }}</div>
                <div class="row-actions row-actions--dense">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openKnowledgeBaseDocumentManagerModal(knowledgeBase)"
                    :disabled="!canManageDocuments || importAdminBusy.loadingDocuments"
                  >
                    文档
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openUploadKnowledgeBaseModal(knowledgeBase)"
                    :disabled="!canImportDocuments || knowledgeBase.status !== 'active'"
                  >
                    添加文件
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openKnowledgeBasePermissionsModal(knowledgeBase)"
                    :disabled="!canManagePermissions"
                  >
                    权限
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openRebuildKnowledgeBaseIndexModal(knowledgeBase)"
                    :disabled="!canIndexDocuments || knowledgeBase.status !== 'active'"
                  >
                    重建索引
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openEditKnowledgeBaseModal(knowledgeBase)"
                    :disabled="!canManageKnowledgeBases"
                  >
                    编辑
                  </button>
                  <button
                    class="button button--danger button--small"
                    type="button"
                    @click="openDeleteKnowledgeBaseModal(knowledgeBase)"
                    :disabled="!canManageKnowledgeBases"
                  >
                    删除
                  </button>
                </div>
              </article>
            </div>
            <p v-else-if="canManageKnowledgeBases" class="empty-state empty-state--plain">
              当前尚未读取到知识库。
            </p>
            <p v-else class="empty-state empty-state--plain">
              当前账号缺少 knowledge_base:manage，无法读取知识库列表；如需上传，请使用具备知识库管理权限的账号。
            </p>
            <div v-if="canManageKnowledgeBases && knowledgeBasePagination.total > 0" class="pagination-bar" aria-label="知识库列表分页">
              <span>
                第 {{ knowledgeBasePagination.page }} / {{ paginationTotalPages(knowledgeBasePagination) }} 页，
                {{ paginationStart(knowledgeBasePagination) }}-{{ paginationEnd(knowledgeBasePagination) }} /
                {{ knowledgeBasePagination.total }} 条
              </span>
              <label>
                每页
                <select
                  v-model.number="knowledgeBasePagination.pageSize"
                  class="control control--compact"
                  :disabled="importAdminBusy.loading"
                  @change="changePaginationPageSize(knowledgeBasePagination, refreshKnowledgeBaseAdminState)"
                >
                  <option v-for="size in pageSizeOptions" :key="`knowledge-base-page-size-${size}`" :value="size">
                    {{ size }}
                  </option>
                </select>
              </label>
              <div class="pagination-bar__actions">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="importAdminBusy.loading || knowledgeBasePagination.page <= 1"
                  @click="changePaginationPage(knowledgeBasePagination, refreshKnowledgeBaseAdminState, knowledgeBasePagination.page - 1)"
                >
                  上一页
                </button>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="importAdminBusy.loading || knowledgeBasePagination.page >= paginationTotalPages(knowledgeBasePagination)"
                  @click="changePaginationPage(knowledgeBasePagination, refreshKnowledgeBaseAdminState, knowledgeBasePagination.page + 1)"
                >
                  下一页
                </button>
              </div>
            </div>

            <div
              v-if="documentManagerModalOpen"
              class="modal-backdrop"
              role="presentation"
              @click.self="closeKnowledgeBaseDocumentManagerModal"
            >
              <section class="modal modal--workspace" role="dialog" aria-modal="true" aria-labelledby="document-manager-modal-title">
                <header class="modal__header">
                  <div>
                    <p class="eyebrow">知识库管理</p>
                    <h3 id="document-manager-modal-title">文档管理</h3>
                    <p>{{ selectedKnowledgeBase ? formatKnowledgeBaseLabel(selectedKnowledgeBase) : "请选择知识库" }}</p>
                  </div>
                  <button class="button button--secondary button--small" type="button" @click="closeKnowledgeBaseDocumentManagerModal">
                    关闭
                  </button>
                </header>
                <div class="modal__body modal__body--documents">
                  <section
                    v-if="selectedKnowledgeBase && (canManageFolders || canManageDocuments)"
                    class="resource-section resource-section--document-manager"
                  >
              <section v-if="canManageFolders" class="resource-block">
                <header class="resource-section__header">
                  <div>
                    <h4>文件夹管理</h4>
                    <p>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</p>
                  </div>
                  <div class="panel__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      @click="refreshSelectedKnowledgeBaseFolders()"
                      :disabled="importAdminBusy.loadingFolders"
                    >
                      {{ importAdminBusy.loadingFolders ? "刷新中" : "刷新文件夹" }}
                    </button>
                    <button class="button button--small" type="button" @click="openCreateFolderModal">
                      新增文件夹
                    </button>
                  </div>
                </header>

                <div v-if="adminFolders.length" class="entity-table entity-table--folders">
                  <div class="entity-table__row entity-table__row--header">
                    <span>文件夹</span>
                    <span>状态</span>
                    <span>上级</span>
                    <span>操作</span>
                  </div>
                  <article
                    v-for="folder in adminFolders"
                    :key="folder.id"
                    :class="['entity-table__row', { 'entity-table__row--selected': folder.id === selectedFolderId }]"
                  >
                    <div class="entity-main">
                      <strong>{{ formatFolderLabel(folder) }}</strong>
                    </div>
                    <div class="entity-cell">
                      <span :class="toneClass(folderStatusTone(folder.status))">
                        {{ formatStatusText(folder.status) }}
                      </span>
                    </div>
                    <div class="entity-cell">{{ formatFolderById(folder.parent_id) }}</div>
                    <div class="row-actions row-actions--dense">
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        @click="openEditFolderModal(folder)"
                      >
                        编辑
                      </button>
                      <button
                        class="button button--danger button--small"
                        type="button"
                        @click="openDeleteFolderModal(folder)"
                      >
                        删除
                      </button>
                    </div>
                  </article>
                </div>
                <p v-else class="empty-state empty-state--plain">当前知识库尚未创建文件夹。</p>
                <div v-if="folderPagination.total > 0" class="pagination-bar" aria-label="文件夹列表分页">
                  <span>
                    第 {{ folderPagination.page }} / {{ paginationTotalPages(folderPagination) }} 页，
                    {{ paginationStart(folderPagination) }}-{{ paginationEnd(folderPagination) }} /
                    {{ folderPagination.total }} 个文件夹
                  </span>
                  <label>
                    每页
                    <select
                      v-model.number="folderPagination.pageSize"
                      class="control control--compact"
                      :disabled="importAdminBusy.loadingFolders"
                      @change="changePaginationPageSize(folderPagination, () => refreshSelectedKnowledgeBaseFolders())"
                    >
                      <option v-for="size in pageSizeOptions" :key="`folder-page-size-${size}`" :value="size">
                        {{ size }}
                      </option>
                    </select>
                  </label>
                  <div class="pagination-bar__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="importAdminBusy.loadingFolders || folderPagination.page <= 1"
                      @click="changePaginationPage(folderPagination, () => refreshSelectedKnowledgeBaseFolders(), folderPagination.page - 1)"
                    >
                      上一页
                    </button>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="importAdminBusy.loadingFolders || folderPagination.page >= paginationTotalPages(folderPagination)"
                      @click="changePaginationPage(folderPagination, () => refreshSelectedKnowledgeBaseFolders(), folderPagination.page + 1)"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </section>

              <p v-else class="empty-state empty-state--plain">
                当前账号缺少 folder:manage，无法管理该知识库下的文件夹。
              </p>

              <section v-if="canManageDocuments" class="resource-block">
                <header class="resource-section__header">
                  <div>
                    <h4>文档管理</h4>
                    <p>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</p>
                  </div>
                  <div class="panel__actions">
                    <span v-if="canIndexDocuments">
                      已选 {{ selectedBatchRebuildDocumentIds.length }} / 可重建 {{ batchRebuildEligibleDocuments.length }}
                    </span>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      @click="refreshSelectedKnowledgeBaseDocuments()"
                      :disabled="importAdminBusy.loadingDocuments"
                    >
                      {{ importAdminBusy.loadingDocuments ? "刷新中" : "刷新文档" }}
                    </button>
                  </div>
                </header>

                <form
                  class="list-filter list-filter--documents"
                  @submit.prevent="refreshFirstPage(documentPagination, refreshSelectedKnowledgeBaseDocuments)"
                >
                  <label class="field">
                    <span class="field__label">文档状态</span>
                    <p class="field__hint">留空时显示当前知识库下全部未删除文档。</p>
                    <select v-model="documentSearchForm.status" class="control">
                      <option value="">全部</option>
                      <option value="draft">{{ formatStatusOption("draft") }}</option>
                      <option value="active">{{ formatStatusOption("active") }}</option>
                      <option value="archived">{{ formatStatusOption("archived") }}</option>
                    </select>
                  </label>
                  <button class="button button--secondary" type="submit" :disabled="importAdminBusy.loadingDocuments">
                    查询文档
                  </button>
                </form>

                <div v-if="canIndexDocuments" class="batch-action-bar">
                  <label class="confirm confirm--inline">
                    <input
                      v-model="documentIndexForm.confirmedBatchRebuild"
                      type="checkbox"
                      :disabled="selectedBatchRebuildDocumentIds.length === 0"
                    />
                    <span>确认重建选中文档索引</span>
                  </label>
                  <button
                    class="button"
                    type="button"
                    @click="rebuildSelectedDocumentsIndex"
                    :disabled="!canRebuildSelectedDocumentsIndex"
                  >
                    {{ importAdminBusy.rebuildingBatchIndex ? "创建中..." : "批量重建索引" }}
                  </button>
                </div>

                <div
                  v-if="adminDocuments.length"
                  :class="[
                    'entity-table',
                    'entity-table--documents',
                    { 'entity-table--documents-selectable': canIndexDocuments },
                  ]"
                >
                  <div class="entity-table__row entity-table__row--header">
                    <span v-if="canIndexDocuments">
                      <input
                        type="checkbox"
                        :checked="allBatchRebuildEligibleDocumentsSelected"
                        :disabled="batchRebuildEligibleDocuments.length === 0"
                        @change="onAllBatchDocumentsToggle"
                      />
                    </span>
                    <span>文档</span>
                    <span>文件夹</span>
                    <span>生命周期</span>
                    <span>索引</span>
                    <span>可见性</span>
                    <span>当前版本</span>
                    <span>操作</span>
                  </div>
                  <article
                    v-for="document in adminDocuments"
                    :key="document.id"
                    :class="['entity-table__row', { 'entity-table__row--selected': document.id === selectedDocumentId }]"
                  >
                    <div v-if="canIndexDocuments" class="entity-cell">
                      <input
                        type="checkbox"
                        :checked="selectedBatchDocumentSet.has(document.id)"
                        :disabled="!isDocumentBatchRebuildEligible(document)"
                        @change="onBatchDocumentSelectionToggle(document.id, $event)"
                      />
                    </div>
                    <div class="entity-main">
                      <strong>{{ document.title || "未命名文档" }}</strong>
                    </div>
                    <div class="entity-cell">{{ document.folder_name ?? "-" }}</div>
                    <div class="entity-cell">
                      <span :class="toneClass(documentLifecycleStatusTone(document.lifecycle_status))">
                        {{ formatStatusText(document.lifecycle_status) }}
                      </span>
                    </div>
                    <div class="entity-cell">
                      <span :class="toneClass(documentIndexStatusTone(document.index_status))">
                        {{ formatStatusText(document.index_status) }}
                      </span>
                    </div>
                    <div class="entity-cell">
                      {{ documentVisibilityLabel(document.visibility) }} /
                      {{ document.owner_department_name ?? "-" }}
                    </div>
                    <div class="entity-cell">{{ formatDocumentCurrentVersion(document) }}</div>
                    <div class="row-actions row-actions--dense">
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        @click="openDocumentDetailsModal(document)"
                        :disabled="importAdminBusy.loadingDocumentDetails"
                      >
                        版本与片段
                      </button>
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        @click="openDocumentPermissionsModal(document)"
                        :disabled="!canManagePermissions"
                      >
                        权限
                      </button>
                    </div>
                  </article>
                </div>
                <p v-else class="empty-state empty-state--plain">当前知识库尚未读取到文档。</p>
                <div v-if="documentPagination.total > 0" class="pagination-bar" aria-label="文档列表分页">
                  <span>
                    第 {{ documentPagination.page }} / {{ paginationTotalPages(documentPagination) }} 页，
                    {{ paginationStart(documentPagination) }}-{{ paginationEnd(documentPagination) }} /
                    {{ documentPagination.total }} 个文档
                  </span>
                  <label>
                    每页
                    <select
                      v-model.number="documentPagination.pageSize"
                      class="control control--compact"
                      :disabled="importAdminBusy.loadingDocuments"
                      @change="changePaginationPageSize(documentPagination, () => refreshSelectedKnowledgeBaseDocuments())"
                    >
                      <option v-for="size in pageSizeOptions" :key="`document-page-size-${size}`" :value="size">
                        {{ size }}
                      </option>
                    </select>
                  </label>
                  <div class="pagination-bar__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="importAdminBusy.loadingDocuments || documentPagination.page <= 1"
                      @click="changePaginationPage(documentPagination, () => refreshSelectedKnowledgeBaseDocuments(), documentPagination.page - 1)"
                    >
                      上一页
                    </button>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="importAdminBusy.loadingDocuments || documentPagination.page >= paginationTotalPages(documentPagination)"
                      @click="changePaginationPage(documentPagination, () => refreshSelectedKnowledgeBaseDocuments(), documentPagination.page + 1)"
                    >
                      下一页
                    </button>
                  </div>
                </div>

              </section>

              <p v-else class="empty-state empty-state--plain">
                当前账号缺少 document:manage，无法查看该知识库下的文档管理数据。
              </p>
                  </section>
                  <p v-else-if="selectedKnowledgeBase" class="empty-state empty-state--plain">
                    当前账号缺少 folder:manage 和 document:manage，无法查看该知识库下的文件夹或文档管理数据。
                  </p>
                  <p v-else class="empty-state empty-state--plain">请选择一个知识库查看文档管理数据。</p>
                </div>
                <footer class="modal__footer">
                  <button class="button button--secondary" type="button" @click="closeKnowledgeBaseDocumentManagerModal">
                    关闭
                  </button>
                </footer>
              </section>
            </div>

            <form
              v-if="canReadImportJobs"
              class="list-filter list-filter--imports"
              @submit.prevent="refreshImportTaskFilters"
            >
              <label class="field">
                <span class="field__label">任务所属知识库</span>
                <p class="field__hint">过滤导入、索引重建和权限刷新任务；这不是查询日志。</p>
                <div class="selector-search">
                  <input
                    v-model.trim="optionSearchForm.knowledgeBaseKeyword"
                    class="control control--compact"
                    type="search"
                    placeholder="搜索知识库"
                  />
                  <button class="button button--secondary button--small" type="button" @click="refreshKnowledgeBaseOptionsFromSearch">
                    查询知识库
                  </button>
                </div>
                <select v-if="activeKnowledgeBases.length" v-model="importSearchForm.kbId" class="control">
                  <option value="">全部</option>
                  <option
                    v-for="knowledgeBase in activeKnowledgeBases"
                    :key="knowledgeBase.id"
                    :value="knowledgeBase.id"
                  >
                    {{ formatKnowledgeBaseLabel(knowledgeBase) }}
                  </option>
                </select>
                <input v-else v-model.trim="importSearchForm.kbId" class="control" type="text" />
              </label>
              <label class="field">
                <span class="field__label">状态</span>
                <p class="field__hint">按任务运行状态过滤。</p>
                <select v-model="importSearchForm.status" class="control">
                  <option value="">全部</option>
                  <option value="queued">{{ formatStatusOption("queued") }}</option>
                  <option value="running">{{ formatStatusOption("running") }}</option>
                  <option value="retrying">{{ formatStatusOption("retrying") }}</option>
                  <option value="partial_success">{{ formatStatusOption("partial_success") }}</option>
                  <option value="success">{{ formatStatusOption("success") }}</option>
                  <option value="failed">{{ formatStatusOption("failed") }}</option>
                  <option value="cancelled">{{ formatStatusOption("cancelled") }}</option>
                </select>
              </label>
              <label class="field">
                <span class="field__label">任务类型</span>
                <p class="field__hint">按导入或索引任务类型过滤。</p>
                <select v-model="importSearchForm.jobType" class="control">
                  <option value="">全部</option>
                  <option value="upload">{{ formatStatusOption("upload") }}</option>
                  <option value="url">{{ formatStatusOption("url") }}</option>
                  <option value="metadata_batch">{{ formatStatusOption("metadata_batch") }}</option>
                  <option value="index_rebuild">{{ formatStatusOption("index_rebuild") }}</option>
                  <option value="permission_refresh">{{ formatStatusOption("permission_refresh") }}</option>
                </select>
              </label>
              <label class="field">
                <span class="field__label">阶段</span>
                <p class="field__hint">按导入阶段过滤。</p>
                <select v-model="importSearchForm.stage" class="control">
                  <option value="">全部</option>
                  <option value="validate">{{ importJobStageLabel("validate") }}</option>
                  <option value="parse">{{ importJobStageLabel("parse") }}</option>
                  <option value="clean">{{ importJobStageLabel("clean") }}</option>
                  <option value="chunk">{{ importJobStageLabel("chunk") }}</option>
                  <option value="embed">{{ importJobStageLabel("embed") }}</option>
                  <option value="index">{{ importJobStageLabel("index") }}</option>
                  <option value="publish">{{ importJobStageLabel("publish") }}</option>
                  <option value="cleanup">{{ importJobStageLabel("cleanup") }}</option>
                  <option value="finished">{{ importJobStageLabel("finished") }}</option>
                </select>
              </label>
              <button class="button button--secondary" type="submit" :disabled="importAdminBusy.loading">
                查询任务
              </button>
            </form>

            <section v-if="canReadImportJobs" class="resource-block">
              <header class="resource-section__header">
                <div>
                  <h4>失败索引任务</h4>
                  <p>
                    {{ paginationStart(failedIndexJobPagination) }}-{{ paginationEnd(failedIndexJobPagination) }} /
                    {{ failedIndexJobPagination.total }} 个失败任务，
                    当前页 {{ failedIndexJobDocumentCount }} 个文档 /
                    {{ failedIndexJobStageSummary.length ? failedIndexJobStageSummary.join("，") : "无失败阶段" }}
                  </p>
                </div>
                <div class="panel__actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="refreshFailedIndexJobs()"
                    :disabled="importAdminBusy.loadingFailedIndexJobs"
                  >
                    {{ importAdminBusy.loadingFailedIndexJobs ? "刷新中" : "刷新失败任务" }}
                  </button>
                  <button
                    class="button button--small"
                    type="button"
                    @click="retrySelectedFailedIndexJobs"
                    :disabled="!canRetrySelectedFailedIndexJobs"
                  >
                    {{ importAdminBusy.retryingIndexJobs ? "创建中..." : "批量重试" }}
                  </button>
                </div>
              </header>
              <label class="confirm confirm--inline">
                <input
                  v-model="indexRetryForm.confirmedRetry"
                  type="checkbox"
                  :disabled="!selectedFailedIndexJobIds.length || !canIndexDocuments"
                />
                <span>确认重试选中的失败索引任务</span>
              </label>
              <div v-if="failedIndexJobs.length" class="entity-table entity-table--index-jobs">
                <div class="entity-table__row entity-table__row--header">
                  <span>
                    <input
                      type="checkbox"
                      :checked="selectedFailedIndexJobIds.length === failedIndexJobs.length"
                      @change="onAllFailedIndexJobsToggle"
                    />
                  </span>
                  <span>任务</span>
                  <span>知识库</span>
                  <span>阶段</span>
                  <span>文档</span>
                  <span>错误</span>
                </div>
                <article v-for="job in failedIndexJobs" :key="job.id" class="entity-table__row">
                  <div class="entity-cell">
                    <input
                      type="checkbox"
                      :checked="selectedFailedIndexJobSet.has(job.id)"
                      @change="onFailedIndexJobToggle(job.id, $event)"
                    />
                  </div>
                  <div class="entity-main">
                    <strong>{{ formatImportJobTitle(job) }}</strong>
                    <span>{{ formatStatusText(job.job_type) }}</span>
                  </div>
                  <div class="entity-cell">{{ formatImportJobKnowledgeBase(job) }}</div>
                  <div class="entity-cell">{{ importJobStageLabel(job.stage) }}</div>
                  <div class="entity-cell">{{ formatDocumentCount(job.document_count) }}</div>
                  <div class="entity-cell">{{ job.error_summary ?? "-" }}</div>
                </article>
              </div>
              <p v-else class="empty-state empty-state--plain">当前没有失败的索引重建任务。</p>
              <div
                v-if="failedIndexJobPagination.total > 0"
                class="pagination-bar"
                aria-label="失败索引任务分页"
              >
                <span>
                  第 {{ failedIndexJobPagination.page }} / {{ paginationTotalPages(failedIndexJobPagination) }} 页，
                  {{ paginationStart(failedIndexJobPagination) }}-{{ paginationEnd(failedIndexJobPagination) }} /
                  {{ failedIndexJobPagination.total }} 个失败任务
                </span>
                <label>
                  每页
                  <select
                    v-model.number="failedIndexJobPagination.pageSize"
                    class="control control--compact"
                    :disabled="importAdminBusy.loadingFailedIndexJobs"
                    @change="changePaginationPageSize(failedIndexJobPagination, refreshFailedIndexJobsPage)"
                  >
                    <option v-for="size in pageSizeOptions" :key="`failed-index-job-page-size-${size}`" :value="size">
                      {{ size }}
                    </option>
                  </select>
                </label>
                <div class="pagination-bar__actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    :disabled="importAdminBusy.loadingFailedIndexJobs || failedIndexJobPagination.page <= 1"
                    @click="changePaginationPage(failedIndexJobPagination, refreshFailedIndexJobsPage, failedIndexJobPagination.page - 1)"
                  >
                    上一页
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    :disabled="importAdminBusy.loadingFailedIndexJobs || failedIndexJobPagination.page >= paginationTotalPages(failedIndexJobPagination)"
                    @click="changePaginationPage(failedIndexJobPagination, refreshFailedIndexJobsPage, failedIndexJobPagination.page + 1)"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </section>

            <div v-if="canReadImportJobs && adminImportJobs.length" class="entity-table entity-table--imports">
              <div class="entity-table__row entity-table__row--header">
                <span>任务</span>
                <span>类型</span>
                <span>知识库</span>
                <span>状态</span>
                <span>阶段</span>
                <span>文档</span>
                <span>错误</span>
              </div>
              <article v-for="job in adminImportJobs" :key="job.id" class="entity-table__row">
                <div class="entity-main">
                  <strong>{{ formatImportJobTitle(job) }}</strong>
                  <span>{{ formatDocumentCount(job.document_count) }}</span>
                </div>
                <div class="entity-cell">{{ formatStatusText(job.job_type) }}</div>
                <div class="entity-cell">{{ formatImportJobKnowledgeBase(job) }}</div>
                <div class="entity-cell">
                  <span :class="toneClass(importJobStatusTone(job.status))">
                    {{ formatStatusText(job.status) }}
                  </span>
                </div>
                <div class="entity-cell">{{ importJobStageLabel(job.stage) }}</div>
                <div class="entity-cell">{{ formatDocumentCount(job.document_count) }}</div>
                <div class="entity-cell">{{ job.error_summary ?? "-" }}</div>
              </article>
            </div>
            <p v-else-if="canReadImportJobs" class="empty-state empty-state--plain">当前尚未读取到导入任务。</p>
            <p v-else class="empty-state empty-state--plain">当前账号缺少 import_job:read，上传后只能看到本次创建结果。</p>
            <div v-if="canReadImportJobs && importJobPagination.total > 0" class="pagination-bar" aria-label="知识库任务列表分页">
              <span>
                第 {{ importJobPagination.page }} / {{ paginationTotalPages(importJobPagination) }} 页，
                {{ paginationStart(importJobPagination) }}-{{ paginationEnd(importJobPagination) }} /
                {{ importJobPagination.total }} 条
              </span>
              <label>
                每页
                <select
                  v-model.number="importJobPagination.pageSize"
                  class="control control--compact"
                  :disabled="importAdminBusy.loading"
                  @change="changePaginationPageSize(importJobPagination, refreshKnowledgeBaseAdminState)"
                >
                  <option v-for="size in pageSizeOptions" :key="`import-job-page-size-${size}`" :value="size">
                    {{ size }}
                  </option>
                </select>
              </label>
              <div class="pagination-bar__actions">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="importAdminBusy.loading || importJobPagination.page <= 1"
                  @click="changePaginationPage(importJobPagination, refreshKnowledgeBaseAdminState, importJobPagination.page - 1)"
                >
                  上一页
                </button>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="importAdminBusy.loading || importJobPagination.page >= paginationTotalPages(importJobPagination)"
                  @click="changePaginationPage(importJobPagination, refreshKnowledgeBaseAdminState, importJobPagination.page + 1)"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="selectedAdminTab === 'diagnostics' && canAccessAdminTab('diagnostics')"
          class="panel panel--wide"
        >
          <header class="panel__header">
            <div>
              <h3>诊断与索引运维</h3>
              <p :class="toneClass(canLoadDiagnostics || canLoadIndexOps ? 'success' : 'warning')">
                {{
                  canLoadDiagnostics && canLoadIndexOps
                    ? "可读取查询日志、模型调用日志与索引健康"
                    : canLoadDiagnostics
                      ? "可读取查询日志与模型调用日志，缺少 document:index"
                      : canLoadIndexOps
                        ? "可读取索引健康，缺少 audit:read"
                        : "缺少 audit:read 和 document:index"
                }}
              </p>
            </div>
            <div class="panel__actions">
              <button
                class="button button--secondary"
                type="button"
                @click="refreshDiagnosticsState"
                :disabled="(!canLoadDiagnostics && !canLoadIndexOps) || diagnosticsBusy.loadingQueryLogs || diagnosticsBusy.loadingModelCallLogs || diagnosticsBusy.loadingIndexHealth"
              >
                {{ diagnosticsBusy.loadingQueryLogs || diagnosticsBusy.loadingModelCallLogs || diagnosticsBusy.loadingIndexHealth ? "刷新中" : "刷新诊断" }}
              </button>
            </div>
          </header>

          <div class="admin-list-panel">
            <div v-if="diagnosticsFeedback" :class="['feedback feedback--wide', `feedback--${diagnosticsFeedback.tone}`]">
              {{ diagnosticsFeedback.message }}
            </div>

            <section class="diagnostics-pane">
              <header class="resource-section__header">
                <div>
                  <h4>索引运维</h4>
                  <p>对比 PostgreSQL 索引账本与 Qdrant collection 状态，暴露 pending_delete、维度和引用数量异常。</p>
                </div>
                <div class="panel__actions">
                  <span>{{ diagnosticsBusy.loadingIndexHealth ? "读取中" : `${indexHealthPagination.total} 个集合` }}</span>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="refreshIndexHealth()"
                    :disabled="!canLoadIndexOps || diagnosticsBusy.loadingIndexHealth"
                  >
                    {{ diagnosticsBusy.loadingIndexHealth ? "刷新中" : "刷新索引" }}
                  </button>
                </div>
              </header>

              <template v-if="indexHealth.length">
                <div class="index-health-list">
                  <article
                    v-for="item in indexHealth"
                    :key="item.collection_name"
                    class="index-health-card"
                    :class="{ 'index-health-card--selected': item.collection_name === indexCollectionOpsForm.selectedCollectionName }"
                  >
                    <header class="index-health-card__header">
                      <div>
                        <strong>{{ item.collection_name }}</strong>
                        <span>期望维度 {{ item.expected_dimension ?? "-" }}</span>
                      </div>
                      <span :class="toneClass(indexHealthTone(item))">
                        {{
                          item.qdrant_reachable
                            ? `${formatStatusText(item.qdrant_status ?? "unknown")} / ${item.qdrant_vector_size ?? "-"}d`
                            : formatStatusText("unreachable")
                        }}
                      </span>
                    </header>
                    <dl class="index-health-metrics">
                      <div class="index-health-metric">
                        <dt>Qdrant</dt>
                        <dd>points {{ item.qdrant_points_count ?? "-" }}</dd>
                        <dd>exists {{ item.qdrant_exists === null ? "-" : formatBoolean(item.qdrant_exists) }}</dd>
                      </div>
                      <div class="index-health-metric">
                        <dt>索引版本</dt>
                        <dd>active {{ item.active_index_version_count }}</dd>
                        <dd>pending {{ item.pending_delete_index_version_count }} / failed {{ item.failed_index_version_count }}</dd>
                      </div>
                      <div class="index-health-metric">
                        <dt>引用</dt>
                        <dd>active {{ item.active_ref_count }} / draft {{ item.draft_ref_count }}</dd>
                        <dd>deleted {{ item.deleted_ref_count }} / pending {{ item.pending_delete_ref_count }}</dd>
                      </div>
                      <div class="index-health-metric">
                        <dt>问题</dt>
                        <dd>{{ formatIssueList(item.issues) }}</dd>
                      </div>
                    </dl>
                  </article>
                </div>
                <div v-if="indexHealthPagination.total > 0" class="pagination-bar" aria-label="索引集合分页">
                  <span>
                    第 {{ indexHealthPagination.page }} / {{ paginationTotalPages(indexHealthPagination) }} 页，
                    {{ paginationStart(indexHealthPagination) }}-{{ paginationEnd(indexHealthPagination) }} /
                    {{ indexHealthPagination.total }} 个集合
                  </span>
                  <label>
                    每页
                    <select
                      v-model.number="indexHealthPagination.pageSize"
                      class="control control--compact"
                      :disabled="diagnosticsBusy.loadingIndexHealth"
                      @change="changePaginationPageSize(indexHealthPagination, () => refreshIndexHealth())"
                    >
                      <option v-for="size in pageSizeOptions" :key="`index-health-page-size-${size}`" :value="size">
                        {{ size }}
                      </option>
                    </select>
                  </label>
                  <div class="pagination-bar__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="diagnosticsBusy.loadingIndexHealth || indexHealthPagination.page <= 1"
                      @click="changePaginationPage(indexHealthPagination, () => refreshIndexHealth(), indexHealthPagination.page - 1)"
                    >
                      上一页
                    </button>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="diagnosticsBusy.loadingIndexHealth || indexHealthPagination.page >= paginationTotalPages(indexHealthPagination)"
                      @click="changePaginationPage(indexHealthPagination, () => refreshIndexHealth(), indexHealthPagination.page + 1)"
                    >
                      下一页
                    </button>
                  </div>
                </div>

                <section class="resource-block index-ops-panel">
                  <header class="resource-section__header">
                    <div>
                      <h4>Qdrant 恢复入口</h4>
                      <p>对选中的 collection 创建快照、从快照恢复，或把该 collection 的 active 文档重新排入索引重建任务。</p>
                    </div>
                    <span>{{ diagnosticsBusy.loadingIndexSnapshots ? "读取快照中" : `${indexSnapshotPagination.total} 个快照` }}</span>
                  </header>

	                  <div class="index-ops-layout">
	                    <div class="index-ops-composite">
	                      <form class="index-ops-selector" @submit.prevent="refreshIndexCollectionSnapshots()">
	                        <header>
	                          <div>
	                            <h5>Collection 选择</h5>
	                            <p>切换后会读取对应 Qdrant 快照列表。</p>
	                          </div>
	                        </header>
	                        <div class="index-ops-row">
	                          <label class="field">
	                            <span class="field__label">Collection</span>
	                            <select
	                              v-model="indexCollectionOpsForm.selectedCollectionName"
	                              class="control"
	                              @change="onIndexCollectionSelectionChange"
	                            >
	                              <option
	                                v-for="item in indexHealth"
	                                :key="item.collection_name"
	                                :value="item.collection_name"
	                              >
	                                {{ item.collection_name }}
	                              </option>
	                            </select>
	                          </label>
	                          <button
	                            class="button button--secondary"
	                            type="submit"
	                            :disabled="!canLoadIndexOps || diagnosticsBusy.loadingIndexSnapshots"
	                          >
	                            {{ diagnosticsBusy.loadingIndexSnapshots ? "刷新中" : "刷新快照" }}
	                          </button>
	                        </div>
	                      </form>

	                      <div class="index-ops-actions-stack">
	                        <section class="index-ops-action-panel">
	                          <header>
	                            <div>
	                              <h5>创建快照</h5>
	                              <p>为当前 collection 创建 Qdrant 快照。</p>
	                            </div>
	                          </header>
	                          <div class="index-ops-action-row">
	                            <label class="confirm confirm--inline">
	                              <input
	                                v-model="indexCollectionOpsForm.confirmedSnapshot"
	                                type="checkbox"
	                                :disabled="!selectedIndexCollectionHealth"
	                              />
	                              <span>确认创建快照</span>
	                            </label>
	                            <button
	                              class="button"
	                              type="button"
	                              @click="createSelectedIndexCollectionSnapshot"
	                              :disabled="!canCreateIndexCollectionSnapshot"
	                            >
	                              {{ diagnosticsBusy.creatingIndexSnapshot ? "创建中..." : "创建快照" }}
	                            </button>
	                          </div>
	                        </section>

	                        <section class="index-ops-action-panel">
	                          <header>
	                            <div>
	                              <h5>重建索引</h5>
	                              <p>把 active 文档重新排入索引任务。</p>
	                            </div>
	                          </header>
	                          <div class="index-ops-action-row">
	                            <label class="confirm confirm--inline">
	                              <input
	                                v-model="indexCollectionOpsForm.confirmedRebuild"
	                                type="checkbox"
	                                :disabled="!selectedIndexCollectionHealth"
	                              />
	                              <span>确认重建索引</span>
	                            </label>
	                            <button
	                              class="button"
	                              type="button"
	                              @click="rebuildSelectedIndexCollection"
	                              :disabled="!canRebuildIndexCollection"
	                            >
	                              {{ diagnosticsBusy.rebuildingIndexCollection ? "创建中..." : "重建索引" }}
	                            </button>
	                          </div>
	                        </section>
	                      </div>
	                    </div>

	                    <form class="index-ops-card index-ops-card--restore" @submit.prevent="recoverSelectedIndexCollectionSnapshot">
                      <header>
                        <div>
                          <h5>从快照恢复</h5>
                          <p>恢复会覆盖当前 Qdrant collection 数据。</p>
                        </div>
                      </header>
                      <label class="field">
                        <span class="field__label">Snapshot URL / File URI</span>
                        <input
                          v-model.trim="indexCollectionOpsForm.snapshotLocation"
                          class="control"
                          type="text"
                          placeholder="https://example.com/snapshot.snapshot 或 file:///qdrant/snapshots/name.snapshot"
                        />
                      </label>
                      <div class="index-ops-row">
                        <label class="field">
                          <span class="field__label">Priority</span>
                          <select v-model="indexCollectionOpsForm.recoverPriority" class="control">
                            <option value="Snapshot">Snapshot</option>
                            <option value="Replica">Replica</option>
                          </select>
                        </label>
                        <label class="field">
                          <span class="field__label">Checksum</span>
                          <input v-model.trim="indexCollectionOpsForm.snapshotChecksum" class="control" type="text" />
                        </label>
                      </div>
                      <div class="index-ops-row index-ops-row--actions">
                        <label class="confirm confirm--inline">
                          <input
                            v-model="indexCollectionOpsForm.confirmedRestore"
                            type="checkbox"
                            :disabled="!selectedIndexCollectionHealth || !indexCollectionOpsForm.snapshotLocation.trim()"
                          />
                          <span>确认覆盖当前数据</span>
                        </label>
                        <button
                          class="button button--danger"
                          type="submit"
                          :disabled="!canRecoverIndexCollectionSnapshot"
                        >
                          {{ diagnosticsBusy.recoveringIndexSnapshot ? "恢复中..." : "恢复快照" }}
                        </button>
                      </div>
                    </form>
                  </div>

                  <div v-if="indexCollectionSnapshots.length" class="entity-table entity-table--snapshots">
                    <div class="entity-table__row entity-table__row--header">
                      <span>快照</span>
                      <span>大小</span>
                      <span>创建时间</span>
                      <span>Checksum</span>
                    </div>
                    <article v-for="snapshot in indexCollectionSnapshots" :key="snapshot.name" class="entity-table__row">
                      <div class="entity-main">
                        <strong>{{ snapshot.name }}</strong>
                        <span>{{ snapshot.collection_name }}</span>
                      </div>
                      <div class="entity-cell">{{ snapshot.size ?? "-" }}</div>
                      <div class="entity-cell">{{ snapshot.creation_time ?? "-" }}</div>
                      <div class="entity-cell">{{ snapshot.checksum ?? "-" }}</div>
                    </article>
                  </div>
                  <p v-else class="empty-state empty-state--plain">当前 collection 尚未读取到 Qdrant 快照。</p>
                  <div v-if="indexSnapshotPagination.total > 0" class="pagination-bar" aria-label="Qdrant 快照分页">
                    <span>
                      第 {{ indexSnapshotPagination.page }} / {{ paginationTotalPages(indexSnapshotPagination) }} 页，
                      {{ paginationStart(indexSnapshotPagination) }}-{{ paginationEnd(indexSnapshotPagination) }} /
                      {{ indexSnapshotPagination.total }} 个快照
                    </span>
                    <label>
                      每页
                      <select
                        v-model.number="indexSnapshotPagination.pageSize"
                        class="control control--compact"
                        :disabled="diagnosticsBusy.loadingIndexSnapshots"
                        @change="changePaginationPageSize(indexSnapshotPagination, () => refreshIndexCollectionSnapshots())"
                      >
                        <option v-for="size in pageSizeOptions" :key="`index-snapshot-page-size-${size}`" :value="size">
                          {{ size }}
                        </option>
                      </select>
                    </label>
                    <div class="pagination-bar__actions">
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="diagnosticsBusy.loadingIndexSnapshots || indexSnapshotPagination.page <= 1"
                        @click="changePaginationPage(indexSnapshotPagination, () => refreshIndexCollectionSnapshots(), indexSnapshotPagination.page - 1)"
                      >
                        上一页
                      </button>
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="diagnosticsBusy.loadingIndexSnapshots || indexSnapshotPagination.page >= paginationTotalPages(indexSnapshotPagination)"
                        @click="changePaginationPage(indexSnapshotPagination, () => refreshIndexCollectionSnapshots(), indexSnapshotPagination.page + 1)"
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                </section>
              </template>
              <p v-else-if="canLoadIndexOps" class="empty-state empty-state--plain">当前尚未读取到索引 collection。</p>
              <p v-else class="empty-state empty-state--plain">当前账号缺少 document:index，无法查看索引运维诊断。</p>
            </section>

            <section class="diagnostics-pane">
              <header class="resource-section__header">
                <div>
                  <h4>查询日志</h4>
                  <p>按 request、trace、用户、知识库和降级原因定位一次问答。</p>
                </div>
                <span>{{ diagnosticsBusy.loadingQueryLogs ? "读取中" : `${queryLogPagination.total} 条` }}</span>
              </header>

                <form class="list-filter list-filter--diagnostics" @submit.prevent="refreshFirstPage(queryLogPagination, refreshQueryLogs)">
                  <label class="field">
                    <span class="field__label">Trace ID</span>
                    <input v-model.trim="queryLogSearchForm.traceId" class="control" type="text" />
                  </label>
                  <label class="field">
                    <span class="field__label">Request ID</span>
                    <input v-model.trim="queryLogSearchForm.requestId" class="control" type="text" />
                  </label>
                  <label class="field">
                    <span class="field__label">用户 ID</span>
                    <input v-model.trim="queryLogSearchForm.userId" class="control" type="text" />
                  </label>
                  <label class="field">
                    <span class="field__label">知识库 ID</span>
                    <input v-model.trim="queryLogSearchForm.kbId" class="control" type="text" />
                  </label>
                  <label class="field">
                    <span class="field__label">状态</span>
                    <select v-model="queryLogSearchForm.status" class="control">
                      <option value="">全部</option>
                      <option value="success">{{ formatStatusOption("success") }}</option>
                      <option value="failed">{{ formatStatusOption("failed") }}</option>
                      <option value="denied">{{ formatStatusOption("denied") }}</option>
                    </select>
                  </label>
                  <label class="field">
                    <span class="field__label">是否降级</span>
                    <select v-model="queryLogSearchForm.degraded" class="control">
                      <option value="">全部</option>
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </label>
                  <label class="field">
                    <span class="field__label">降级原因</span>
                    <input v-model.trim="queryLogSearchForm.degradeReason" class="control" type="text" />
                  </label>
                  <label class="field">
                    <span class="field__label">错误码</span>
                    <input v-model.trim="queryLogSearchForm.errorCode" class="control" type="text" />
                  </label>
                  <button class="button button--secondary" type="submit" :disabled="!canLoadDiagnostics || diagnosticsBusy.loadingQueryLogs">
                    查询
                  </button>
                </form>

                <div v-if="queryLogs.length" class="entity-table entity-table--query-logs">
                  <div class="entity-table__row entity-table__row--header">
                    <span>请求</span>
                    <span>状态</span>
                    <span>召回</span>
                    <span>耗时</span>
                    <span>时间</span>
                    <span>操作</span>
                  </div>
                  <article v-for="log in queryLogs" :key="log.id" class="entity-table__row">
                    <div class="entity-main">
                      <strong>{{ formatQueryLogUser(log) }}</strong>
                      <span>知识库：{{ formatQueryLogKnowledgeBases(log) }}</span>
                    </div>
                    <div class="entity-cell">
                      <span :class="toneClass(queryLogStatusTone(log))">
                        {{ formatQueryLogStatus(log) }}
                      </span>
                      <span v-if="log.degrade_reason || log.error_code">
                        {{ formatDiagnosticReasonList(log.degrade_reason ?? log.error_code, "") }}
                      </span>
                    </div>
                    <div class="entity-cell">{{ log.candidate_count }} 候选 / {{ log.citation_count }} 引用</div>
                    <div class="entity-cell">{{ formatLatency(log.latency_ms) }}</div>
                    <div class="entity-cell">{{ formatAuditTime(log.created_at) }}</div>
                    <div class="row-actions row-actions--dense">
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        @click="selectQueryLog(log.id)"
                        :disabled="diagnosticsBusy.loadingQueryDetail"
                      >
                        详情
                      </button>
                    </div>
                  </article>
                </div>
                <p v-else-if="canLoadDiagnostics" class="empty-state empty-state--plain">当前尚未读取到查询日志。</p>
                <div v-if="queryLogPagination.total > 0" class="pagination-bar" aria-label="查询日志分页">
                  <span>
                    第 {{ queryLogPagination.page }} / {{ paginationTotalPages(queryLogPagination) }} 页，
                    {{ paginationStart(queryLogPagination) }}-{{ paginationEnd(queryLogPagination) }} /
                    {{ queryLogPagination.total }} 条
                  </span>
                  <label>
                    每页
                    <select
                      v-model.number="queryLogPagination.pageSize"
                      class="control control--compact"
                      :disabled="diagnosticsBusy.loadingQueryLogs"
                      @change="changePaginationPageSize(queryLogPagination, refreshQueryLogs)"
                    >
                      <option v-for="size in pageSizeOptions" :key="`query-log-page-size-${size}`" :value="size">
                        {{ size }}
                      </option>
                    </select>
                  </label>
                  <div class="pagination-bar__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="diagnosticsBusy.loadingQueryLogs || queryLogPagination.page <= 1"
                      @click="changePaginationPage(queryLogPagination, refreshQueryLogs, queryLogPagination.page - 1)"
                    >
                      上一页
                    </button>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="diagnosticsBusy.loadingQueryLogs || queryLogPagination.page >= paginationTotalPages(queryLogPagination)"
                      @click="changePaginationPage(queryLogPagination, refreshQueryLogs, queryLogPagination.page + 1)"
                    >
                      下一页
                    </button>
                  </div>
                </div>
            </section>

            <section class="diagnostics-pane">
              <header class="resource-section__header">
                <div>
                  <h4>模型调用日志</h4>
                  <p>展示模型路由、调用方、耗时、token 摘要和错误码，不展示 prompt 或文档原文。</p>
                </div>
                <span>{{ diagnosticsBusy.loadingModelCallLogs ? "读取中" : `${modelCallLogPagination.total} 条` }}</span>
              </header>

              <form class="list-filter list-filter--model-calls" @submit.prevent="refreshFirstPage(modelCallLogPagination, refreshModelCallLogs)">
                <label class="field">
                  <span class="field__label">Trace ID</span>
                  <input v-model.trim="modelCallSearchForm.traceId" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">模型</span>
                  <input v-model.trim="modelCallSearchForm.model" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">类型</span>
                  <select v-model="modelCallSearchForm.modelType" class="control">
                    <option value="">全部</option>
                    <option value="llm">{{ formatStatusOption("llm") }}</option>
                    <option value="rerank">{{ formatStatusOption("rerank") }}</option>
                    <option value="embedding">{{ formatStatusOption("embedding") }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">调用方</span>
                  <input v-model.trim="modelCallSearchForm.caller" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">状态</span>
                  <select v-model="modelCallSearchForm.status" class="control">
                    <option value="">全部</option>
                    <option value="success">{{ formatStatusOption("success") }}</option>
                    <option value="failed">{{ formatStatusOption("failed") }}</option>
                    <option value="degraded">{{ formatStatusOption("degraded") }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">是否降级</span>
                  <select v-model="modelCallSearchForm.degraded" class="control">
                    <option value="">全部</option>
                    <option value="true">是</option>
                    <option value="false">否</option>
                  </select>
                </label>
                <button class="button button--secondary" type="submit" :disabled="!canLoadDiagnostics || diagnosticsBusy.loadingModelCallLogs">
                  查询调用
                </button>
              </form>

              <div v-if="modelCallLogs.length" class="entity-table entity-table--model-calls">
                <div class="entity-table__row entity-table__row--header">
                  <span>模型</span>
                  <span>调用方</span>
                  <span>状态</span>
                  <span>耗时</span>
                  <span>时间</span>
                  <span>操作</span>
                </div>
                <article v-for="log in modelCallLogs" :key="log.id" class="entity-table__row">
                  <div class="entity-main">
                    <strong>{{ log.model_name }}</strong>
                    <span>{{ formatStatusText(log.model_type) }} / {{ log.model_version ?? "-" }}</span>
                  </div>
                  <div class="entity-cell">{{ log.caller }}</div>
                  <div class="entity-cell">
                    <span :class="toneClass(modelCallStatusTone(log))">
                      {{ formatModelCallStatus(log) }}
                    </span>
                  </div>
                  <div class="entity-cell">{{ formatLatency(log.latency_ms) }}</div>
                  <div class="entity-cell">{{ formatAuditTime(log.created_at) }}</div>
                  <div class="row-actions row-actions--dense">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      @click="openModelCallLogDetail(log)"
                      :disabled="diagnosticsBusy.loadingModelCallDetail"
                    >
                      详情
                    </button>
                  </div>
                </article>
              </div>
              <p v-else-if="canLoadDiagnostics" class="empty-state empty-state--plain">当前尚未读取到模型调用日志。</p>
              <div v-if="modelCallLogPagination.total > 0" class="pagination-bar" aria-label="模型调用日志分页">
                <span>
                  第 {{ modelCallLogPagination.page }} / {{ paginationTotalPages(modelCallLogPagination) }} 页，
                  {{ paginationStart(modelCallLogPagination) }}-{{ paginationEnd(modelCallLogPagination) }} /
                  {{ modelCallLogPagination.total }} 条
                </span>
                <label>
                  每页
                  <select
                    v-model.number="modelCallLogPagination.pageSize"
                    class="control control--compact"
                    :disabled="diagnosticsBusy.loadingModelCallLogs"
                    @change="changePaginationPageSize(modelCallLogPagination, refreshModelCallLogs)"
                  >
                    <option v-for="size in pageSizeOptions" :key="`model-call-log-page-size-${size}`" :value="size">
                      {{ size }}
                    </option>
                  </select>
                </label>
                <div class="pagination-bar__actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    :disabled="diagnosticsBusy.loadingModelCallLogs || modelCallLogPagination.page <= 1"
                    @click="changePaginationPage(modelCallLogPagination, refreshModelCallLogs, modelCallLogPagination.page - 1)"
                  >
                    上一页
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    :disabled="diagnosticsBusy.loadingModelCallLogs || modelCallLogPagination.page >= paginationTotalPages(modelCallLogPagination)"
                    @click="changePaginationPage(modelCallLogPagination, refreshModelCallLogs, modelCallLogPagination.page + 1)"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </section>
          </div>
        </section>

        <section v-if="selectedAdminTab === 'config' && canAccessAdminTab('config')" class="panel panel--wide">
          <header class="panel__header">
            <div>
              <h3>配置管理</h3>
              <p :class="toneClass(canReadConfig || canManageConfig ? 'success' : 'warning')">
                {{ canManageConfig ? "可管理配置" : canReadConfig ? "可读取配置" : "缺少配置权限" }}
              </p>
            </div>
            <div class="panel__actions">
              <button
                class="button button--secondary"
                type="button"
                @click="refreshConfigAdminState"
                :disabled="configBusy.loading || (!canReadConfig && !canManageConfig)"
              >
                {{ configBusy.loading ? "刷新中" : "刷新配置" }}
              </button>
              <button class="button" type="button" @click="openCreateConfigModal" :disabled="!canManageConfig">
                新建版本
              </button>
            </div>
          </header>
          <div class="admin-list-panel">
            <div v-if="configFeedback" :class="['feedback feedback--wide', `feedback--${configFeedback.tone}`]">
              {{ configFeedback.message }}
            </div>

            <section class="config-version-strip">
              <article class="config-version-card">
                <span>当前配置版本</span>
                <strong>v{{ activeConfigVersion }}</strong>
              </article>
              <article class="config-version-card">
                <span>版本数量</span>
                <strong>{{ configVersionPagination.total }}</strong>
              </article>
              <article class="config-version-card">
                <span>本页可激活</span>
                <strong>{{ configDraftItems.length }}</strong>
              </article>
            </section>

            <div v-if="configVersions.length" class="entity-table entity-table--configs">
              <div class="entity-table__row entity-table__row--header">
                <span>版本</span>
                <span>状态</span>
                <span>创建时间</span>
                <span>更新时间</span>
                <span>内容摘要</span>
                <span>操作</span>
              </div>
              <article
                v-for="version in paginatedConfigVersions"
                :key="`config-version-${version.version}`"
                class="entity-table__row"
              >
                <div class="entity-main">
                  <strong>v{{ version.version }}</strong>
                  <span>{{ configVersionPreview(version) }}</span>
                </div>
                <div class="entity-cell">
                  <span :class="toneClass(configStatusTone(version.status))">
                    {{ formatStatusText(version.status) }}
                  </span>
                </div>
                <div class="entity-cell">{{ formatDateTime(version.created_at) }}</div>
                <div class="entity-cell">{{ formatDateTime(version.updated_at) }}</div>
                <div class="entity-cell">
                  <span>{{ riskLevelText(version.risk_level) }}风险</span>
                </div>
                <div class="row-actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openEditConfigVersion(version)"
                    :disabled="!canManageConfig || !isEditableConfigVersion(version)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="isActivatableConfigVersion(version)"
                    class="button button--secondary button--small"
                    type="button"
                    @click="publishDraftVersion(version.version)"
                    :disabled="!canManageConfig || configBusy.publishing"
                  >
                    激活
                  </button>
                  <button
                    v-if="isArchivableConfigVersion(version)"
                    class="button button--danger button--small"
                    type="button"
                    @click="archiveConfigVersionFromUi(version)"
                    :disabled="!canManageConfig || configBusy.deleting"
                  >
                    归档
                  </button>
                </div>
              </article>
            </div>
            <p v-else class="empty-state empty-state--plain">当前尚未读取到配置版本。</p>
            <div v-if="configVersionPagination.total > 0" class="pagination-bar" aria-label="配置列表分页">
              <span>
                第 {{ configVersionPagination.page }} / {{ paginationTotalPages(configVersionPagination) }} 页，
                {{ paginationStart(configVersionPagination) }}-{{ paginationEnd(configVersionPagination) }} /
                {{ configVersionPagination.total }} 条
              </span>
              <label>
                每页
                <select
                  v-model.number="configVersionPagination.pageSize"
                  class="control control--compact"
                  :disabled="configBusy.loading"
                  @change="changePaginationPageSize(configVersionPagination, refreshConfigAdminState)"
                >
                  <option v-for="size in pageSizeOptions" :key="`config-version-page-size-${size}`" :value="size">
                    {{ size }}
                  </option>
                </select>
              </label>
              <div class="pagination-bar__actions">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="configBusy.loading || configVersionPagination.page <= 1"
                  @click="changePaginationPage(configVersionPagination, refreshConfigAdminState, configVersionPagination.page - 1)"
                >
                  上一页
                </button>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  :disabled="configBusy.loading || configVersionPagination.page >= paginationTotalPages(configVersionPagination)"
                  @click="changePaginationPage(configVersionPagination, refreshConfigAdminState, configVersionPagination.page + 1)"
                >
                  下一页
                </button>
              </div>
            </div>

            <section class="config-secondary-grid config-secondary-grid--single">
              <div class="config-versions" aria-label="配置审计">
                <details class="config-audit-details">
                  <summary>配置变更日志</summary>
                  <p v-if="auditFeedback" :class="toneClass(auditFeedback.tone)">
                    {{ auditFeedback.message }}
                  </p>
                  <div v-if="auditLogs.length" class="audit-list">
                    <article v-for="log in auditLogs" :key="log.id" class="audit-row">
                      <header>
                        <strong>{{ log.event_name }}</strong>
                        <span :class="toneClass(log.result === 'success' ? 'success' : 'error')">
                          {{ formatStatusText(log.result) }}
                        </span>
                      </header>
                      <p>{{ formatAuditTime(log.created_at) }}</p>
                      <p>{{ auditSummaryPreview(log) }}</p>
                      <p v-if="log.error_code" class="audit-row__error">{{ log.error_code }}</p>
                    </article>
                  </div>
                  <p v-else-if="canReadAudit" class="empty-state">当前尚未读取到配置变更日志。</p>
                  <p v-else class="empty-state">当前账号缺少审计读取权限。</p>
                  <div v-if="auditLogPagination.total > 0" class="pagination-bar" aria-label="配置变更日志分页">
                    <span>
                      第 {{ auditLogPagination.page }} / {{ paginationTotalPages(auditLogPagination) }} 页，
                      {{ paginationStart(auditLogPagination) }}-{{ paginationEnd(auditLogPagination) }} /
                      {{ auditLogPagination.total }} 条
                    </span>
                    <label>
                      每页
                      <select
                        v-model.number="auditLogPagination.pageSize"
                        class="control control--compact"
                        :disabled="configBusy.loading"
                        @change="changePaginationPageSize(auditLogPagination, refreshConfigAdminState)"
                      >
                        <option v-for="size in pageSizeOptions" :key="`audit-log-page-size-${size}`" :value="size">
                          {{ size }}
                        </option>
                      </select>
                    </label>
                    <div class="pagination-bar__actions">
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="configBusy.loading || auditLogPagination.page <= 1"
                        @click="changePaginationPage(auditLogPagination, refreshConfigAdminState, auditLogPagination.page - 1)"
                      >
                        上一页
                      </button>
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="configBusy.loading || auditLogPagination.page >= paginationTotalPages(auditLogPagination)"
                        @click="changePaginationPage(auditLogPagination, refreshConfigAdminState, auditLogPagination.page + 1)"
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                </details>
              </div>
            </section>
          </div>
        </section>
      </section>

      <div
        v-if="queryLogDetailModalOpen && selectedQueryLog"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeQueryLogDetailModal"
      >
        <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="query-log-detail-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">查询诊断</p>
              <h3 id="query-log-detail-modal-title">查询详情</h3>
              <p>{{ formatQueryLogTitle(selectedQueryLog) }}</p>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeQueryLogDetailModal">
              关闭
            </button>
          </header>
          <div class="modal__body">
            <dl class="summary summary--compact modal-summary">
              <div class="summary__row">
                <dt>查询时间</dt>
                <dd>{{ formatAuditTime(selectedQueryLog.created_at) }}</dd>
              </div>
              <div class="summary__row">
                <dt>查询结果</dt>
                <dd>{{ formatQueryLogStatus(selectedQueryLog) }}</dd>
              </div>
              <div class="summary__row">
                <dt>用户</dt>
                <dd>{{ formatQueryLogUser(selectedQueryLog) }}</dd>
              </div>
              <div class="summary__row">
                <dt>知识库</dt>
                <dd>{{ formatQueryLogKnowledgeBases(selectedQueryLog) }}</dd>
              </div>
              <div class="summary__row">
                <dt>召回结果</dt>
                <dd>{{ selectedQueryLog.candidate_count }} 个候选 / {{ selectedQueryLog.citation_count }} 个引用</dd>
              </div>
              <div class="summary__row">
                <dt>耗时</dt>
                <dd>{{ formatLatency(selectedQueryLog.latency_ms) }}</dd>
              </div>
              <div class="summary__row">
                <dt>降级原因</dt>
                <dd>{{ formatDiagnosticReasonList(selectedQueryLog.degrade_reason) }}</dd>
              </div>
              <div class="summary__row">
                <dt>错误码</dt>
                <dd>{{ formatDiagnosticReasonList(selectedQueryLog.error_code, "-") }}</dd>
              </div>
              <div class="summary__row">
                <dt>配置版本</dt>
                <dd>v{{ selectedQueryLog.config_version }}</dd>
              </div>
              <div class="summary__row">
                <dt>权限版本</dt>
                <dd>{{ selectedQueryLog.permission_version }}</dd>
              </div>
            </dl>

            <section class="modal-pane">
              <h4>技术追踪</h4>
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>请求编号</dt>
                  <dd>{{ formatShortIdentifier(selectedQueryLog.request_id) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>追踪编号</dt>
                  <dd>{{ formatShortIdentifier(selectedQueryLog.trace_id) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>查询摘要</dt>
                  <dd>{{ formatShortIdentifier(selectedQueryLog.query_hash) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>权限过滤</dt>
                  <dd>{{ formatShortIdentifier(selectedQueryLog.permission_filter_hash) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>索引版本</dt>
                  <dd>{{ formatShortIdentifier(selectedQueryLog.index_version_hash) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>模型路由</dt>
                  <dd>{{ formatShortIdentifier(selectedQueryLog.model_route_hash) }}</dd>
                </div>
              </dl>
            </section>
          </div>
          <footer class="modal__footer">
            <button class="button button--secondary" type="button" @click="closeQueryLogDetailModal">
              关闭
            </button>
          </footer>
        </section>
      </div>

      <div
        v-if="modelCallLogDetailModalOpen && selectedModelCallLog"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeModelCallLogDetailModal"
      >
        <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="model-call-log-detail-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">查询诊断</p>
              <h3 id="model-call-log-detail-modal-title">模型调用详情</h3>
              <p>{{ formatModelCallTitle(selectedModelCallLog) }}</p>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeModelCallLogDetailModal">
              关闭
            </button>
          </header>
          <div class="modal__body">
            <dl class="summary summary--compact modal-summary">
              <div class="summary__row">
                <dt>模型</dt>
                <dd>{{ selectedModelCallLog.model_name }}</dd>
              </div>
              <div class="summary__row">
                <dt>类型</dt>
                <dd>{{ formatStatusText(selectedModelCallLog.model_type) }}</dd>
              </div>
              <div class="summary__row">
                <dt>版本</dt>
                <dd>{{ selectedModelCallLog.model_version ?? "-" }}</dd>
              </div>
              <div class="summary__row">
                <dt>调用方</dt>
                <dd>{{ selectedModelCallLog.caller }}</dd>
              </div>
              <div class="summary__row">
                <dt>状态</dt>
                <dd>{{ formatModelCallStatus(selectedModelCallLog) }}</dd>
              </div>
              <div class="summary__row">
                <dt>耗时</dt>
                <dd>{{ formatLatency(selectedModelCallLog.latency_ms) }}</dd>
              </div>
              <div class="summary__row">
                <dt>调用时间</dt>
                <dd>{{ formatAuditTime(selectedModelCallLog.created_at) }}</dd>
              </div>
              <div class="summary__row">
                <dt>配置版本</dt>
                <dd>{{ selectedModelCallLog.config_version === null ? "-" : `v${selectedModelCallLog.config_version}` }}</dd>
              </div>
              <div class="summary__row">
                <dt>错误码</dt>
                <dd>{{ formatDiagnosticReasonList(selectedModelCallLog.error_code, "-") }}</dd>
              </div>
              <div class="summary__row">
                <dt>Token</dt>
                <dd>{{ formatTokenUsage(selectedModelCallLog.token_usage_json) }}</dd>
              </div>
            </dl>

            <section class="modal-pane">
              <h4>技术追踪</h4>
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>请求编号</dt>
                  <dd>{{ formatShortIdentifier(selectedModelCallLog.request_id) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>追踪编号</dt>
                  <dd>{{ formatShortIdentifier(selectedModelCallLog.trace_id) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>模型路由</dt>
                  <dd>{{ formatShortIdentifier(selectedModelCallLog.model_route_hash) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>Prompt 摘要</dt>
                  <dd>{{ formatShortIdentifier(selectedModelCallLog.prompt_hash) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>输入摘要</dt>
                  <dd>{{ formatShortIdentifier(selectedModelCallLog.input_hash) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>输出摘要</dt>
                  <dd>{{ formatShortIdentifier(selectedModelCallLog.output_hash) }}</dd>
                </div>
              </dl>
            </section>
          </div>
          <footer class="modal__footer">
            <button class="button button--secondary" type="button" @click="closeModelCallLogDetailModal">
              关闭
            </button>
          </footer>
        </section>
      </div>

      <div v-if="configModalMode" class="modal-backdrop" role="presentation" @click.self="closeConfigModal">
        <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="config-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">配置管理</p>
              <h3 id="config-modal-title">{{ configModalTitle() }}</h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeConfigModal">
              关闭
            </button>
          </header>

          <form v-if="configModalMode === 'create' || configModalMode === 'edit'" @submit.prevent="saveSelectedDraft">
            <div class="modal__body">
              <div v-if="configFeedback" :class="['feedback feedback--wide', `feedback--${configFeedback.tone}`]">
                {{ configFeedback.message }}
              </div>
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>{{ configModalMode === "create" ? "基线版本" : "编辑版本" }}</dt>
                  <dd>
                    {{
                      configModalMode === "create"
                        ? `当前 active_config v${activeConfigVersion}`
                        : `v${selectedConfigVersionRecord?.version ?? "-"} / ${formatStatusText(selectedConfigVersionRecord?.status)}`
                    }}
                  </dd>
                </div>
                <div class="summary__row">
                  <dt>创建时间</dt>
                  <dd>
                    {{
                      configModalMode === "create"
                        ? formatDateTime(activeConfigVersionRecord?.created_at ?? null)
                        : formatDateTime(selectedConfigVersionRecord?.created_at ?? null)
                    }}
                  </dd>
                </div>
                <div class="summary__row">
                  <dt>更新时间</dt>
                  <dd>
                    {{
                      configModalMode === "create"
                        ? formatDateTime(activeConfigVersionRecord?.updated_at ?? null)
                        : formatDateTime(selectedConfigVersionRecord?.updated_at ?? null)
                    }}
                  </dd>
                </div>
              </dl>
              <div class="config-form-sections">
                <section
                  v-for="section in configSectionDefinitions"
                  :key="`config-form-${section.key}`"
                  class="config-form-section"
                >
                  <header>
                    <div>
                      <h4>{{ section.label }}</h4>
                      <p>{{ section.description }}</p>
                    </div>
                    <span>{{ section.key }}</span>
                  </header>
                  <div class="form-grid form-grid--compact form-grid--modal">
                    <label
                      v-for="field in configNormalFields(section)"
                      :key="`config-field-${String(field.key)}`"
                      class="field"
                      :class="{ 'field--full': field.span === 'full' }"
                    >
                      <span class="field__label">
                        {{ field.label }}
                        <span v-if="field.required" class="required-mark">必填</span>
                      </span>
                      <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
                        {{ field.hint }}
                      </p>
                      <select
                        v-if="field.input === 'select'"
                        class="control"
                        :value="String(configForm[field.key])"
                        @change="updateConfigFieldFromSelect(field, ($event.target as HTMLSelectElement).value)"
                      >
                        <option v-for="option in field.options ?? []" :key="option.value" :value="option.value">
                          {{ option.label }}
                        </option>
                      </select>
                      <input
                        v-else
                        class="control"
                        :type="field.input"
                        :min="field.min"
                        :step="field.step"
                        :placeholder="field.placeholder"
                        :value="String(configForm[field.key] ?? '')"
                        @input="updateConfigFieldFromInput(field, ($event.target as HTMLInputElement).value)"
                      />
                    </label>
                  </div>
                  <div v-if="configCheckboxFields(section).length" class="checkbox-grid">
                    <label
                      v-for="field in configCheckboxFields(section)"
                      :key="`config-field-${String(field.key)}`"
                      class="field field--checkbox"
                    >
                      <input
                        class="checkbox"
                        type="checkbox"
                        :checked="Boolean(configForm[field.key])"
                        @change="updateConfigFieldFromCheckbox(field, ($event.target as HTMLInputElement).checked)"
                      />
                      <span>{{ field.label }}</span>
                      <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
                        {{ field.hint }}
                      </p>
                    </label>
                  </div>
                </section>
              </div>
              <p v-if="configEditorParseError" class="field-issue field-issue--error">
                {{ configEditorParseError }}
              </p>
              <div class="config-actions">
                <button
                  class="button button--secondary"
                  type="button"
                  @click="validateSelectedConfig"
                  :disabled="!canValidateSelectedConfig"
                >
                  {{ configBusy.validating ? "校验中..." : "校验配置" }}
                </button>
                <button class="button" type="submit" :disabled="!canSaveSelectedConfigDraft">
                  {{ configBusy.saving ? "保存中..." : "保存配置" }}
                </button>
              </div>
              <div v-if="configValidationResult" class="result-block result-block--compact">
                <p :class="toneClass(configValidationResult.valid ? 'success' : 'error')">
                  {{ configValidationResult.valid ? "后端校验通过" : "后端校验未通过" }}
                </p>
                <ul v-if="configValidationResult.errors.length" class="issue-list">
                  <li
                    v-for="issue in configValidationResult.errors"
                    :key="`${issue.error_code ?? issue.code}-${issue.path}`"
                  >
                    <strong>{{ normalizeIssueCode(issue) }}</strong>
                    <span>{{ issue.path }}</span>
                    <p>{{ issue.message }}</p>
                  </li>
                </ul>
                <ul v-if="configValidationResult.warnings.length" class="issue-list issue-list--warning">
                  <li
                    v-for="issue in configValidationResult.warnings"
                    :key="`${issue.error_code ?? issue.code}-${issue.path}`"
                  >
                    <strong>{{ normalizeIssueCode(issue) }}</strong>
                    <span>{{ issue.path }}</span>
                    <p>{{ issue.message }}</p>
                  </li>
                </ul>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeConfigModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canSaveSelectedConfigDraft">
                {{ configBusy.saving ? "保存中..." : "保存配置" }}
              </button>
            </footer>
          </form>

        </section>
      </div>

      <div
        v-if="knowledgeBaseModalMode"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeKnowledgeBaseModal"
      >
        <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="knowledge-base-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">知识库管理</p>
              <h3 id="knowledge-base-modal-title">
                {{
                  knowledgeBaseModalMode === "create"
                    ? "新增知识库"
                    : knowledgeBaseModalMode === "edit"
                      ? "编辑知识库"
                      : knowledgeBaseModalMode === "permissions"
                        ? "权限策略"
                        : knowledgeBaseModalMode === "upload"
                          ? "添加文件"
                          : knowledgeBaseModalMode === "rebuildIndex"
                            ? "重建索引"
                            : "删除知识库"
                }}
              </h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeKnowledgeBaseModal">
              关闭
            </button>
          </header>

          <form v-if="knowledgeBaseModalMode === 'create'" @submit.prevent="submitCreateKnowledgeBase">
            <div class="modal__body">
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <div class="field field--full">
                  <span class="field__label">部门选项</span>
                  <p class="field__hint">按部门名称搜索，当前已选部门会保留在列表中。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                </div>
                <label class="field">
                  <span class="field__label">知识库名称</span>
                  <p class="field__hint">用于管理后台和用户查询入口展示。</p>
                  <input v-model.trim="knowledgeBaseCreateForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">管理部门</span>
                  <p class="field__hint">仅表示管理归属，不等于访问边界。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBaseCreateForm.ownerDepartmentId"
                    class="control"
                    required
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBaseCreateForm.ownerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                    required
                  />
                </label>
                <label class="field">
                  <span class="field__label">知识库可见性</span>
                  <p class="field__hint">董事会、法务等敏感知识库应使用指定部门可见。</p>
                  <select v-model="knowledgeBaseCreateForm.kbVisibility" class="control">
                    <option value="enterprise">企业可见</option>
                    <option value="department_acl">指定部门可见</option>
                    <option value="private">私密可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档权限</span>
                  <p class="field__hint">新导入文件默认使用该文档权限，可在导入后单独调整。</p>
                  <select v-model="knowledgeBaseCreateForm.defaultDocumentVisibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档所属部门</span>
                  <p class="field__hint">当默认文档权限为 department 时，该部门必须能查询此知识库。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <fieldset
                  v-if="knowledgeBaseCreateForm.kbVisibility !== 'enterprise'"
                  class="field field--full checkbox-list"
                >
                  <legend class="field__label">可访问部门</legend>
                  <label v-for="department in activeDepartments" :key="department.id" class="check-row">
                    <input
                      type="checkbox"
                      :checked="knowledgeBaseCreateForm.accessDepartmentIds.includes(department.id)"
                      @change="onKnowledgeBaseCreateAccessDepartmentChange(department.id, $event)"
                    />
                    <span>{{ formatDepartmentLabel(department) }}</span>
                  </label>
                </fieldset>
                <label class="field">
                  <span class="field__label">配置作用域</span>
                  <p class="field__hint">可留空；后续用于按知识库覆盖模型或索引配置。</p>
                  <input v-model.trim="knowledgeBaseCreateForm.configScopeId" class="control" type="text" />
                </label>
                <label
                  v-if="knowledgeBaseCreateForm.kbVisibility === 'enterprise'"
                  class="confirm confirm--inline modal-confirm"
                >
                  <input v-model="knowledgeBaseCreateForm.confirmedEnterpriseVisibility" type="checkbox" />
                  <span>确认创建企业可见知识库</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canCreateKnowledgeBase">
                {{ importAdminBusy.creating ? "创建中..." : "创建知识库" }}
              </button>
            </footer>
          </form>

          <form v-else-if="knowledgeBaseModalMode === 'edit' && selectedKnowledgeBase" @submit.prevent="submitPatchKnowledgeBase">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>所属部门</dt>
                  <dd>{{ formatDepartmentById(selectedKnowledgeBase.owner_department_id) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <div class="field field--full">
                  <span class="field__label">部门选项</span>
                  <p class="field__hint">按部门名称搜索，当前已选部门会保留在列表中。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                </div>
                <label class="field">
                  <span class="field__label">知识库名称</span>
                  <p class="field__hint">修改不会影响已有文档内容和索引版本。</p>
                  <input v-model.trim="knowledgeBaseEditForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">状态</span>
                  <p class="field__hint">禁用或归档会影响后续查询和导入可用性。</p>
                  <select v-model="knowledgeBaseEditForm.status" class="control">
                    <option value="active">{{ formatStatusOption("active") }}</option>
                    <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                    <option value="archived">{{ formatStatusOption("archived") }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">知识库可见性</span>
                  <p class="field__hint">从受限可见扩大到 enterprise 需要显式确认。</p>
                  <select v-model="knowledgeBaseEditForm.kbVisibility" class="control">
                    <option value="enterprise">企业可见</option>
                    <option value="department_acl">指定部门可见</option>
                    <option value="private">私密可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档权限</span>
                  <p class="field__hint">只影响后续导入文件，不批量修改已有文档。</p>
                  <select v-model="knowledgeBaseEditForm.defaultDocumentVisibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档所属部门</span>
                  <p class="field__hint">默认文档权限为 department 时使用。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <label class="field">
                  <span class="field__label">配置作用域</span>
                  <p class="field__hint">可留空；仅保存配置作用域，不直接发布配置。</p>
                  <input v-model.trim="knowledgeBaseEditForm.configScopeId" class="control" type="text" />
                </label>
                <label
                  v-if="
                    selectedKnowledgeBase.kb_visibility !== 'enterprise' &&
                    knowledgeBaseEditForm.kbVisibility === 'enterprise'
                  "
                  class="confirm confirm--inline modal-confirm"
                >
                  <input v-model="knowledgeBaseEditForm.confirmedVisibilityExpand" type="checkbox" />
                  <span>确认将知识库可见性扩大到企业</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUpdateSelectedKnowledgeBase">
                {{ importAdminBusy.updating ? "保存中..." : "保存知识库" }}
              </button>
            </footer>
          </form>

          <form
            v-else-if="knowledgeBaseModalMode === 'permissions' && selectedKnowledgeBase"
            @submit.prevent="submitKnowledgeBasePermissions"
          >
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前策略</dt>
                  <dd>
                    {{ knowledgeBaseVisibilityLabel(selectedKnowledgeBase.kb_visibility) }} /
                    默认文档{{ documentVisibilityLabel(selectedKnowledgeBase.default_document_visibility) }} /
                    {{ formatDepartmentById(selectedKnowledgeBase.default_document_owner_department_id) }}
                  </dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <div class="field field--full">
                  <span class="field__label">部门选项</span>
                  <p class="field__hint">按部门名称搜索，当前已选部门会保留在列表中。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                </div>
                <label class="field">
                  <span class="field__label">知识库可见性</span>
                  <p class="field__hint">控制知识库是否出现在用户列表中，以及是否可被选择查询。</p>
                  <select v-model="knowledgeBasePermissionForm.kbVisibility" class="control">
                    <option value="enterprise">企业可见</option>
                    <option value="department_acl">指定部门可见</option>
                    <option value="private">私密可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档权限</span>
                  <p class="field__hint">只影响后续导入文件；已有文档权限请在文档权限弹窗中修改。</p>
                  <select v-model="knowledgeBasePermissionForm.defaultDocumentVisibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">默认文档所属部门</span>
                  <p class="field__hint">当默认文档权限为 department 时，该部门必须具备知识库查询权限。</p>
                  <select
                    v-if="activeDepartments.length"
                    v-model="knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <fieldset
                  v-if="knowledgeBasePermissionForm.kbVisibility !== 'enterprise'"
                  class="field field--full checkbox-list"
                >
                  <legend class="field__label">可访问部门</legend>
                  <label v-for="department in activeDepartments" :key="department.id" class="check-row">
                    <input
                      type="checkbox"
                      :checked="knowledgeBasePermissionForm.accessDepartmentIds.includes(department.id)"
                      @change="onKnowledgeBasePermissionAccessDepartmentChange(department.id, $event)"
                    />
                    <span>{{ formatDepartmentLabel(department) }}</span>
                  </label>
                </fieldset>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="knowledgeBasePermissionForm.confirmedReplace" type="checkbox" />
                  <span>确认替换知识库权限策略</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canReplaceSelectedKnowledgeBasePermissions">
                {{ importAdminBusy.updatingPermissions ? "保存中..." : "保存权限" }}
              </button>
            </footer>
          </form>

          <div v-else-if="knowledgeBaseModalMode === 'rebuildIndex' && selectedKnowledgeBase">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前策略</dt>
                  <dd>
                    {{ knowledgeBaseVisibilityLabel(selectedKnowledgeBase.kb_visibility) }} /
                    默认文档{{ documentVisibilityLabel(selectedKnowledgeBase.default_document_visibility) }}
                  </dd>
                </div>
              </dl>
              <div class="danger-panel">
                <h4>确认重建知识库索引</h4>
                <p>
                  将为该知识库下 active 且已有当前版本的文档创建批量 index_rebuild 任务。任务会从 embed 阶段重新生成向量并发布新索引版本。
                </p>
                <label class="confirm confirm--inline">
                  <input v-model="knowledgeBaseIndexForm.confirmedRebuild" type="checkbox" />
                  <span>确认重建该知识库索引</span>
                </label>
              </div>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button
                class="button"
                type="button"
                @click="rebuildSelectedKnowledgeBaseIndex"
                :disabled="!canRebuildSelectedKnowledgeBaseIndex"
              >
                {{ importAdminBusy.rebuildingIndex ? "创建中..." : "创建重建任务" }}
              </button>
            </footer>
          </div>

	          <form v-else-if="knowledgeBaseModalMode === 'upload' && selectedImportKnowledgeBase" @submit.prevent="submitDocumentUpload">
	            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>目标知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedImportKnowledgeBase) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>默认文档部门</dt>
                  <dd>{{ formatDepartmentById(selectedImportKnowledgeBase.default_document_owner_department_id) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="upload-panel upload-panel--modal">
                <section class="upload-panel__main">
                  <label class="field">
                    <span class="field__label">文档可见性</span>
                    <p class="field__hint">默认继承知识库的默认文档权限；department 会按默认文档所属部门可见。</p>
                    <select
                      v-model="importUploadForm.visibility"
                      class="control"
                      :disabled="!canImportDocuments || importAdminBusy.uploading"
                    >
                      <option value="department">部门可见</option>
                      <option value="enterprise">企业可见</option>
                    </select>
                    <p v-if="importUploadPermissionParentConflict" :class="toneClass('warning')">
                      {{ importUploadPermissionParentConflict }}
                    </p>
                  </label>
                  <label class="field">
                    <span class="field__label">目标文件夹</span>
                    <p class="field__hint">留空表示导入到根目录；文件夹需要先在当前知识库中创建。</p>
                    <div class="selector-search">
                      <input
                        v-model.trim="optionSearchForm.folderKeyword"
                        class="control control--compact"
                        type="search"
                        placeholder="搜索文件夹"
                        :disabled="!canImportDocuments || importAdminBusy.uploading"
                      />
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="!canImportDocuments || importAdminBusy.uploading"
                        @click="refreshFolderOptionsFromSearch"
                      >
                        查询文件夹
                      </button>
                    </div>
                    <select
                      v-if="activeFolders.length"
                      v-model="importUploadForm.folderId"
                      class="control"
                      :disabled="!canImportDocuments || importAdminBusy.uploading"
                    >
                      <option value="">根目录</option>
                      <option v-for="folder in activeFolders" :key="folder.id" :value="folder.id">
                        {{ formatFolderLabel(folder) }}
                      </option>
                    </select>
                    <input
                      v-else
                      v-model.trim="importUploadForm.folderId"
                      class="control"
                      type="text"
                      placeholder="可选目标文件夹"
                      :disabled="!canImportDocuments || importAdminBusy.uploading"
                    />
                  </label>
                  <label class="field">
                    <span class="field__label">幂等键</span>
                    <p class="field__hint">重复测试同一文件时可留空；需要防重提交时填写稳定键。</p>
                    <input
                      v-model.trim="importUploadForm.idempotencyKey"
                      class="control"
                      type="text"
                      :disabled="!canImportDocuments || importAdminBusy.uploading"
                    />
                  </label>
                  <label class="field field--full">
                    <span class="field__label">选择文件</span>
                    <p class="field__hint">支持 PDF、DOCX、UTF-8 文本和 Markdown；大小限制由 active_config.import 控制。</p>
                    <input
                      :key="importFileInputKey"
                      class="control control--file"
                      type="file"
                      multiple
                      accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                      :disabled="!canImportDocuments || importAdminBusy.uploading"
                      @change="onImportFilesChange"
                    />
                  </label>
                </section>

                <section class="upload-panel__side">
                  <h4>待上传文件</h4>
                  <div v-if="selectedImportFiles.length" class="file-list">
                    <article
                      v-for="file in selectedImportFiles"
                      :key="`${file.name}-${file.size}-${file.lastModified}`"
                      class="file-row"
                    >
                      <strong>{{ file.name }}</strong>
                      <span>{{ formatFileSize(file.size) }}</span>
                    </article>
                  </div>
                  <p v-else class="empty-state empty-state--plain">尚未选择文件。</p>
                  <dl class="summary summary--compact upload-summary">
                    <div class="summary__row">
                      <dt>文件数</dt>
                      <dd>{{ selectedImportFiles.length }}</dd>
                    </div>
                  </dl>
                  <div class="upload-actions">
                    <button
                      class="button button--secondary"
                      type="button"
                      @click="clearImportFiles"
                      :disabled="!selectedImportFiles.length || importAdminBusy.uploading"
                    >
                      清空文件
                    </button>
                    <button class="button" type="submit" :disabled="!canUploadImportFiles">
                      {{ importAdminBusy.uploading ? "上传中..." : "创建导入任务" }}
                    </button>
                  </div>
                </section>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUploadImportFiles">
                {{ importAdminBusy.uploading ? "上传中..." : "创建导入任务" }}
              </button>
            </footer>
          </form>

          <div v-else-if="knowledgeBaseModalMode === 'delete' && selectedKnowledgeBase">
            <div class="modal__body">
              <div class="danger-panel">
                <h4>确认删除知识库</h4>
                <p>
                  将删除 {{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}，并写入 access block，后续由索引清理任务处理相关索引。
                </p>
                <label class="confirm confirm--inline">
                  <input v-model="knowledgeBaseDangerForm.confirmedDelete" type="checkbox" />
                  <span>确认删除该知识库</span>
                </label>
              </div>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeKnowledgeBaseModal">
                取消
              </button>
              <button
                class="button button--danger"
                type="button"
                @click="deleteSelectedKnowledgeBase"
                :disabled="!canDeleteSelectedKnowledgeBase"
              >
                {{ importAdminBusy.deleting ? "删除中..." : "删除知识库" }}
              </button>
            </footer>
          </div>
        </section>
      </div>

      <div
        v-if="folderModalMode"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeFolderModal"
      >
        <section class="modal" role="dialog" aria-modal="true" aria-labelledby="folder-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">文件夹管理</p>
              <h3 id="folder-modal-title">
                {{
                  folderModalMode === "create"
                    ? "新增文件夹"
                    : folderModalMode === "edit"
                      ? "编辑文件夹"
                      : "删除文件夹"
                }}
              </h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeFolderModal">
              关闭
            </button>
          </header>

          <form v-if="folderModalMode === 'create' && selectedKnowledgeBase" @submit.prevent="submitCreateFolder">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>知识库</dt>
                  <dd>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">文件夹名称</span>
                  <p class="field__hint">同一父级下不能创建重名文件夹。</p>
                  <input v-model.trim="folderCreateForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">上级文件夹</span>
                  <p class="field__hint">留空表示根目录。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.folderKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索文件夹"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshFolderOptionsFromSearch">
                      查询文件夹
                    </button>
                  </div>
                  <select v-model="folderCreateForm.parentId" class="control">
                    <option value="">根目录</option>
                    <option v-for="folder in activeFolders" :key="folder.id" :value="folder.id">
                      {{ formatFolderLabel(folder) }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeFolderModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canCreateFolder">
                {{ importAdminBusy.managingFolder ? "创建中..." : "创建文件夹" }}
              </button>
            </footer>
          </form>

          <form v-else-if="folderModalMode === 'edit' && selectedFolder" @submit.prevent="submitPatchFolder">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>文件夹</dt>
                  <dd>{{ formatFolderLabel(selectedFolder) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前上级</dt>
                  <dd>{{ formatFolderById(selectedFolder.parent_id) }}</dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">文件夹名称</span>
                  <p class="field__hint">重命名不会改变已导入文档内容。</p>
                  <input v-model.trim="folderEditForm.name" class="control" type="text" required />
                </label>
                <label class="field">
                  <span class="field__label">状态</span>
                  <p class="field__hint">禁用或归档会阻止后续文档导入到该目录。</p>
                  <select v-model="folderEditForm.status" class="control">
                    <option value="active">{{ formatStatusOption("active") }}</option>
                    <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                    <option value="archived">{{ formatStatusOption("archived") }}</option>
                  </select>
                </label>
                <label class="field field--full">
                  <span class="field__label">上级文件夹</span>
                  <p class="field__hint">不能移动到自身或自身的子目录；后端会再次校验。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.folderKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索文件夹"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshFolderOptionsFromSearch">
                      查询文件夹
                    </button>
                  </div>
                  <select v-model="folderEditForm.parentId" class="control">
                    <option value="">根目录</option>
                    <option v-for="folder in folderParentOptions" :key="folder.id" :value="folder.id">
                      {{ formatFolderLabel(folder) }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeFolderModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUpdateSelectedFolder">
                {{ importAdminBusy.managingFolder ? "保存中..." : "保存文件夹" }}
              </button>
            </footer>
          </form>

          <div v-else-if="folderModalMode === 'delete' && selectedFolder">
            <div class="modal__body">
              <div class="danger-panel">
                <h4>确认删除文件夹</h4>
                <p>
                  将删除 {{ formatFolderLabel(selectedFolder) }}，并写入 access block；该文件夹下文档的清理影响由后端任务处理。
                </p>
                <label class="confirm confirm--inline">
                  <input v-model="folderDangerForm.confirmedDelete" type="checkbox" />
                  <span>确认删除该文件夹</span>
                </label>
              </div>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeFolderModal">
                取消
              </button>
              <button
                class="button button--danger"
                type="button"
                @click="deleteSelectedFolder"
                :disabled="!canDeleteSelectedFolder"
              >
                {{ importAdminBusy.managingFolder ? "删除中..." : "删除文件夹" }}
              </button>
            </footer>
          </div>
        </section>
      </div>

      <div
        v-if="documentModalMode"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeDocumentModal"
      >
        <section
          :class="['modal', documentModalMode === 'details' ? 'modal--document-details' : 'modal--wide']"
          role="dialog"
          aria-modal="true"
          aria-labelledby="document-modal-title"
        >
          <header class="modal__header">
            <div>
              <p class="eyebrow">文档管理</p>
              <h3 id="document-modal-title">
                {{ documentModalMode === "details" ? "版本与片段" : "文档权限策略" }}
              </h3>
              <p v-if="selectedDocumentForDisplay">{{ selectedDocumentForDisplay.title || "未命名文档" }}</p>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeDocumentModal">
              关闭
            </button>
          </header>

          <form v-if="documentModalMode === 'permissions' && selectedAdminDocument" @submit.prevent="submitDocumentPermissions">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>文档</dt>
                  <dd>{{ selectedAdminDocument.title }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前策略</dt>
                  <dd>
                    {{ documentVisibilityLabel(selectedAdminDocument.visibility) }} /
                    {{ formatDepartmentById(selectedAdminDocument.owner_department_id) }}
                  </dd>
                </div>
                <div v-if="selectedDocumentParentKnowledgeBase" class="summary__row">
                  <dt>父知识库</dt>
                  <dd>
                    {{ formatKnowledgeBaseLabel(selectedDocumentParentKnowledgeBase) }}，
                    {{ knowledgeBaseVisibilityLabel(selectedDocumentParentKnowledgeBase.kb_visibility) }} /
                    默认文档{{ documentVisibilityLabel(selectedDocumentParentKnowledgeBase.default_document_visibility) }}
                  </dd>
                </div>
              </dl>
              <div v-if="importAdminFeedback" :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]">
                {{ importAdminFeedback.message }}
              </div>
              <p v-if="documentPermissionParentConflict" :class="toneClass('warning')">
                {{ documentPermissionParentConflict }}
              </p>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">可见性</span>
                  <p class="field__hint">修改文档权限会触发权限快照更新；收紧时会写 access block。</p>
                  <select v-model="documentPermissionForm.visibility" class="control">
                    <option value="department">部门可见</option>
                    <option value="enterprise">企业可见</option>
                  </select>
                </label>
                <label class="field">
                  <span class="field__label">所属部门</span>
                  <p class="field__hint">部门可见时只有该部门成员可检索。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                  <select
                    v-if="activeDepartments.length"
                    v-model="documentPermissionForm.ownerDepartmentId"
                    class="control"
                  >
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model.trim="documentPermissionForm.ownerDepartmentId"
                    class="control"
                    type="text"
                    placeholder="请选择或输入部门"
                  />
                </label>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="documentPermissionForm.confirmedReplace" type="checkbox" />
                  <span>确认替换文档权限策略</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeDocumentModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canReplaceSelectedDocumentPermissions">
                {{ importAdminBusy.updatingPermissions ? "保存中..." : "保存权限" }}
              </button>
            </footer>
          </form>

          <p v-else-if="documentModalMode === 'permissions'" class="empty-state empty-state--plain">
            正在读取文档权限详情。
          </p>

          <div v-else-if="documentModalMode === 'details' && selectedDocumentForDisplay">
            <div class="modal__body modal__body--document-details">
              <dl class="summary summary--compact modal-summary document-detail-summary">
                <div class="summary__row">
                  <dt>文档</dt>
                  <dd>{{ selectedDocumentForDisplay.title || "未命名文档" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前版本</dt>
                  <dd>{{ formatDocumentCurrentVersion(selectedDocumentForDisplay) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>生命周期</dt>
                  <dd>{{ formatStatusText(selectedDocumentForDisplay.lifecycle_status) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>索引状态</dt>
                  <dd>{{ formatStatusText(selectedDocumentForDisplay.index_status) }}</dd>
                </div>
              </dl>

              <section class="document-version-index-grid">
                <div class="document-detail-pane document-detail-pane--versions">
                  <header class="document-detail-pane__header">
                    <h4>文档版本</h4>
                    <span>
                      {{
                        importAdminBusy.loadingDocumentVersions
                          ? "读取中"
                          : `${paginationStart(documentVersionPagination)}-${paginationEnd(documentVersionPagination)} / ${documentVersionPagination.total} 个版本`
                      }}
                    </span>
                  </header>
                  <div v-if="selectedDocumentVersions.length" class="document-version-list">
                    <article v-for="version in selectedDocumentVersions" :key="version.id" class="document-version-row">
                      <strong>{{ formatDocumentVersion(version) }}</strong>
                      <span :class="toneClass(documentVersionStatusTone(version.status))">
                        {{ formatStatusText(version.status) }}
                      </span>
                    </article>
                  </div>
                  <p v-else class="empty-state empty-state--plain">当前文档尚未读取到版本。</p>
                  <div v-if="documentVersionPagination.total > 0" class="pagination-bar pagination-bar--compact" aria-label="文档版本分页">
                    <span>
                      第 {{ documentVersionPagination.page }} / {{ paginationTotalPages(documentVersionPagination) }} 页，
                      {{ paginationStart(documentVersionPagination) }}-{{ paginationEnd(documentVersionPagination) }} /
                      {{ documentVersionPagination.total }} 个版本
                    </span>
                    <label>
                      每页
                      <select
                        v-model.number="documentVersionPagination.pageSize"
                        class="control control--small"
                        @change="changePaginationPageSize(documentVersionPagination, () => refreshSelectedDocumentVersions())"
                      >
                        <option v-for="size in pageSizeOptions" :key="`document-version-page-size-${size}`" :value="size">
                          {{ size }}
                        </option>
                      </select>
                    </label>
                    <div class="pagination-bar__actions">
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="importAdminBusy.loadingDocumentVersions || documentVersionPagination.page <= 1"
                        @click="changePaginationPage(documentVersionPagination, () => refreshSelectedDocumentVersions(), documentVersionPagination.page - 1)"
                      >
                        上一页
                      </button>
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        :disabled="importAdminBusy.loadingDocumentVersions || documentVersionPagination.page >= paginationTotalPages(documentVersionPagination)"
                        @click="changePaginationPage(documentVersionPagination, () => refreshSelectedDocumentVersions(), documentVersionPagination.page + 1)"
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                </div>

                <div class="document-detail-pane document-detail-pane--index">
                  <header class="document-detail-pane__header">
                    <div>
                      <h4>索引版本</h4>
                      <p>
                        {{
                          importAdminBusy.loadingIndexVersions
                            ? "读取中"
                            : `${paginationStart(documentIndexVersionPagination)}-${paginationEnd(documentIndexVersionPagination)} / ${documentIndexVersionPagination.total} 个索引版本`
                        }}
                      </p>
                    </div>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      @click="refreshSelectedDocumentIndexVersions()"
                      :disabled="!canIndexDocuments || importAdminBusy.loadingIndexVersions"
                    >
                      {{ importAdminBusy.loadingIndexVersions ? "刷新中" : "刷新索引" }}
                    </button>
                  </header>
                  <p v-if="!canIndexDocuments" class="empty-state empty-state--plain">
                    当前账号缺少 document:index，无法查看或重建索引。
                  </p>
                  <template v-else>
                    <div v-if="cleanupEligibleIndexVersions.length" class="batch-action-bar">
                      <label class="confirm confirm--inline">
                        <input
                          type="checkbox"
                          :checked="allCleanupEligibleIndexVersionsSelected"
                          @change="onAllIndexVersionsForCleanupToggle"
                        />
                        <span>
                          已选 {{ selectedCleanupPendingDeleteIndexVersionIds.length }} /
                          可清理 {{ cleanupEligibleIndexVersions.length }}
                        </span>
                      </label>
                      <label class="confirm confirm--inline">
                        <input
                          v-model="documentIndexForm.confirmedCleanup"
                          type="checkbox"
                          :disabled="selectedCleanupPendingDeleteIndexVersionIds.length === 0"
                        />
                        <span>确认清理选中索引版本</span>
                      </label>
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        @click="cleanupSelectedIndexVersions"
                        :disabled="!canCleanupSelectedIndexVersions"
                      >
                        {{ importAdminBusy.cleaningIndexVersions ? "创建中..." : "清理索引" }}
                      </button>
                    </div>
                    <div v-if="selectedDocumentIndexVersions.length" class="index-version-list">
                      <article
                        v-for="(version, index) in selectedDocumentIndexVersions"
                        :key="version.id"
                        :class="[
                          'index-version-row',
                          { 'index-version-row--selectable': version.status === 'pending_delete' },
                        ]"
                      >
                        <input
                          v-if="version.status === 'pending_delete'"
                          class="index-version-row__selector"
                          type="checkbox"
                          :checked="selectedCleanupIndexVersionSet.has(version.id)"
                          @change="onIndexVersionCleanupSelectionToggle(version.id, $event)"
                        />
                        <div class="index-version-row__body">
                          <header>
                            <strong>{{ formatIndexVersionLabel(index) }}</strong>
                            <span :class="toneClass(indexVersionStatusTone(version.status))">
                              {{ formatStatusText(version.status) }}
                            </span>
                          </header>
                          <dl>
                            <div>
                              <dt>模型</dt>
                              <dd>{{ version.embedding_model }} / {{ version.model_version }}</dd>
                            </div>
                            <div>
                              <dt>维度</dt>
                              <dd>{{ version.dimension }}</dd>
                            </div>
                            <div>
                              <dt>片段</dt>
                              <dd>{{ version.chunk_count }}</dd>
                            </div>
                            <div>
                              <dt>集合</dt>
                              <dd>{{ version.collection_name }}</dd>
                            </div>
                            <div>
                              <dt>创建</dt>
                              <dd>{{ formatAuditTime(version.created_at) }}</dd>
                            </div>
                            <div>
                              <dt>激活</dt>
                              <dd>{{ formatAuditTime(version.activated_at) }}</dd>
                            </div>
                          </dl>
                        </div>
                      </article>
                    </div>
                    <p v-else class="empty-state empty-state--plain">当前文档尚未读取到索引版本。</p>
                    <div
                      v-if="documentIndexVersionPagination.total > 0"
                      class="pagination-bar pagination-bar--compact"
                      aria-label="索引版本分页"
                    >
                      <span>
                        第 {{ documentIndexVersionPagination.page }} / {{ paginationTotalPages(documentIndexVersionPagination) }} 页，
                        {{ paginationStart(documentIndexVersionPagination) }}-{{ paginationEnd(documentIndexVersionPagination) }} /
                        {{ documentIndexVersionPagination.total }} 个索引版本
                      </span>
                      <label>
                        每页
                        <select
                          v-model.number="documentIndexVersionPagination.pageSize"
                          class="control control--small"
                          @change="changePaginationPageSize(documentIndexVersionPagination, () => refreshSelectedDocumentIndexVersions())"
                        >
                          <option v-for="size in pageSizeOptions" :key="`document-index-version-page-size-${size}`" :value="size">
                            {{ size }}
                          </option>
                        </select>
                      </label>
                      <div class="pagination-bar__actions">
                        <button
                          class="button button--secondary button--small"
                          type="button"
                          :disabled="importAdminBusy.loadingIndexVersions || documentIndexVersionPagination.page <= 1"
                          @click="changePaginationPage(documentIndexVersionPagination, () => refreshSelectedDocumentIndexVersions(), documentIndexVersionPagination.page - 1)"
                        >
                          上一页
                        </button>
                        <button
                          class="button button--secondary button--small"
                          type="button"
                          :disabled="importAdminBusy.loadingIndexVersions || documentIndexVersionPagination.page >= paginationTotalPages(documentIndexVersionPagination)"
                          @click="changePaginationPage(documentIndexVersionPagination, () => refreshSelectedDocumentIndexVersions(), documentIndexVersionPagination.page + 1)"
                        >
                          下一页
                        </button>
                      </div>
                    </div>
                    <div class="index-rebuild-panel">
                      <label class="confirm confirm--inline">
                        <input v-model="documentIndexForm.confirmedRebuild" type="checkbox" />
                        <span>确认为当前文档重建索引</span>
                      </label>
                      <button
                        class="button button--secondary button--small"
                        type="button"
                        @click="rebuildSelectedDocumentIndex"
                        :disabled="!canRebuildSelectedDocumentIndex"
                      >
                        {{ importAdminBusy.rebuildingIndex ? "创建中..." : "重建索引" }}
                      </button>
                    </div>
                  </template>
                </div>
              </section>

              <section class="document-detail-pane document-detail-pane--chunks">
                <header class="document-detail-pane__header">
                  <h4>Chunk 预览</h4>
                  <span>
                    {{
                      importAdminBusy.loadingDocumentDetails
                        ? "读取中"
                        : `${paginationStart(documentChunkPagination)}-${paginationEnd(documentChunkPagination)} / ${documentChunkPagination.total} 个片段`
                    }}
                  </span>
                </header>
                <div v-if="selectedDocumentChunks.length" class="chunk-preview-list chunk-preview-list--table">
                  <button
                    v-for="(chunk, index) in selectedDocumentChunks"
                    :key="chunk.id"
                    class="chunk-preview-row chunk-preview-row--button"
                    :class="{ 'chunk-preview-row--active': chunk.id === highlightedDocumentChunkId }"
                    type="button"
                    @click="selectDocumentChunk(chunk.id)"
                  >
                    <header>
                      <strong>{{ formatChunkOrdinal(chunk, index) }}</strong>
                      <span :class="toneClass(chunk.status === 'active' ? 'success' : 'neutral')">
                        {{ formatStatusText(chunk.status) }}
                      </span>
                      <span>页码 {{ formatChunkPageRange(chunk) }}</span>
                    </header>
                    <p>{{ chunk.text_preview }}</p>
                  </button>
                </div>
                <p v-else class="empty-state empty-state--plain">当前文档尚未读取到 chunk。</p>
                <div v-if="documentChunkPagination.total > 0" class="pagination-bar" aria-label="Chunk 预览分页">
                  <span>
                    第 {{ documentChunkPagination.page }} / {{ paginationTotalPages(documentChunkPagination) }} 页，
                    {{ paginationStart(documentChunkPagination) }}-{{ paginationEnd(documentChunkPagination) }} /
                    {{ documentChunkPagination.total }} 个片段
                  </span>
                  <label>
                    每页
                    <select
                      v-model.number="documentChunkPagination.pageSize"
                      class="control control--small"
                      @change="changePaginationPageSize(documentChunkPagination, () => refreshSelectedDocumentDetails())"
                    >
                      <option v-for="size in pageSizeOptions" :key="`document-chunk-page-size-${size}`" :value="size">
                        {{ size }}
                      </option>
                    </select>
                  </label>
                  <div class="pagination-bar__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="importAdminBusy.loadingDocumentDetails || documentChunkPagination.page <= 1"
                      @click="changePaginationPage(documentChunkPagination, () => refreshSelectedDocumentDetails(), documentChunkPagination.page - 1)"
                    >
                      上一页
                    </button>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="importAdminBusy.loadingDocumentDetails || documentChunkPagination.page >= paginationTotalPages(documentChunkPagination)"
                      @click="changePaginationPage(documentChunkPagination, () => refreshSelectedDocumentDetails(), documentChunkPagination.page + 1)"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </section>

            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeDocumentModal">
                关闭
              </button>
            </footer>
          </div>
        </section>
      </div>

      <div
        v-if="departmentModalMode"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeDepartmentModal"
      >
        <section class="modal" role="dialog" aria-modal="true" aria-labelledby="department-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">部门管理</p>
              <h3 id="department-modal-title">
                {{
                  departmentModalMode === "create"
                    ? "新增部门"
                    : departmentModalMode === "edit"
                      ? "编辑部门"
                      : "删除部门"
                }}
              </h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeDepartmentModal">
              关闭
            </button>
          </header>

          <form v-if="departmentModalMode === 'create'" @submit.prevent="submitCreateDepartment">
            <div class="modal__body">
              <div
                v-if="departmentAdminFeedback"
                :class="['feedback feedback--wide', `feedback--${departmentAdminFeedback.tone}`]"
              >
                {{ departmentAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">部门编码</span>
                  <p class="field__hint">企业内唯一，建议使用字母、数字、下划线或连字符。</p>
                  <input v-model.trim="departmentCreateForm.code" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">部门名称</span>
                  <p class="field__hint">用于用户归属、权限范围和管理后台展示。</p>
                  <input v-model.trim="departmentCreateForm.name" class="control" type="text" />
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeDepartmentModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canCreateDepartment">
                {{ departmentAdminBusy.creating ? "创建中..." : "创建部门" }}
              </button>
            </footer>
          </form>

          <form v-else-if="departmentModalMode === 'edit' && selectedDepartment" @submit.prevent="submitPatchDepartment">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>默认部门</dt>
                  <dd>{{ selectedDepartment.is_default ? "是" : "否" }}</dd>
                </div>
              </dl>
              <div
                v-if="departmentAdminFeedback"
                :class="['feedback feedback--wide', `feedback--${departmentAdminFeedback.tone}`]"
              >
                {{ departmentAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">部门名称</span>
                  <p class="field__hint">修改后会刷新组织版本和权限版本。</p>
                  <input v-model.trim="departmentEditForm.name" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">部门状态</span>
                  <p class="field__hint">默认部门不能禁用；禁用会影响用户权限上下文。</p>
                  <select
                    v-model="departmentEditForm.status"
                    class="control"
                    :disabled="selectedDepartment.is_default"
                  >
                    <option value="active">{{ formatStatusOption("active") }}</option>
                    <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                  </select>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeDepartmentModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUpdateSelectedDepartment">
                {{ departmentAdminBusy.updating ? "保存中..." : "保存修改" }}
              </button>
            </footer>
          </form>

          <div v-else-if="departmentModalMode === 'delete' && selectedDepartment">
            <div class="modal__body">
              <div class="danger-panel">
                <h4>确认删除部门</h4>
                <p>
                  将删除部门 {{ formatDepartmentLabel(selectedDepartment) }}。默认部门不能删除，已有关联用户或权限范围时后端会阻止该操作。
                </p>
                <label class="confirm confirm--inline">
                  <input
                    v-model="departmentDangerForm.confirmedDelete"
                    type="checkbox"
                    :disabled="selectedDepartment.is_default"
                  />
                  <span>确认删除该部门</span>
                </label>
              </div>
              <div
                v-if="departmentAdminFeedback"
                :class="['feedback feedback--wide', `feedback--${departmentAdminFeedback.tone}`]"
              >
                {{ departmentAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeDepartmentModal">
                取消
              </button>
              <button
                class="button button--danger"
                type="button"
                @click="deleteSelectedDepartment"
                :disabled="!canDeleteSelectedDepartment"
              >
                {{ departmentAdminBusy.deleting ? "删除中..." : "删除部门" }}
              </button>
            </footer>
          </div>
        </section>
      </div>

      <div v-if="userModalMode" class="modal-backdrop" role="presentation" @click.self="closeUserModal">
        <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="user-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">用户管理</p>
              <h3 id="user-modal-title">
                {{
                  userModalMode === "create"
                    ? "新增用户"
                    : userModalMode === "edit"
                      ? "编辑用户"
                      : userModalMode === "departments"
                        ? "维护部门归属"
                        : userModalMode === "roles"
                          ? "维护角色绑定"
                          : userModalMode === "password"
                            ? "重置密码"
                            : "删除用户"
                }}
              </h3>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeUserModal">
              关闭
            </button>
          </header>

          <form v-if="userModalMode === 'create'" @submit.prevent="submitCreateAdminUser">
            <div class="modal__body">
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">登录名</span>
                  <p class="field__hint">用户的唯一登录标识。</p>
                  <input v-model.trim="userCreateForm.username" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">显示名</span>
                  <p class="field__hint">用于页面展示和审计摘要。</p>
                  <input v-model.trim="userCreateForm.name" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">初始密码</span>
                  <p class="field__hint">创建后将强制用户首次登录修改密码。</p>
                  <input v-model="userCreateForm.initialPassword" class="control" type="password" />
                </label>
                <label class="field">
                  <span class="field__label">确认密码</span>
                  <p class="field__hint">两次密码必须完全一致。</p>
                  <input v-model="userCreateForm.passwordConfirm" class="control" type="password" />
                </label>
                <div class="option-picker">
                  <span class="field__label">归属部门</span>
                  <p class="field__hint">至少选择一个部门；第一个选中的部门会作为用户主部门。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                  <div class="option-picker__grid">
                    <label v-for="department in createUserDepartmentOptions" :key="department.id" class="option-card">
                      <input
                        type="checkbox"
                        :checked="userCreateForm.departmentIds.includes(department.id)"
                        @change="toggleCreateDepartment(department.id, ($event.target as HTMLInputElement).checked)"
                      />
                      <span>{{ formatDepartmentLabel(department) }}</span>
                    </label>
                  </div>
                  <p v-if="!createUserDepartmentOptions.length" class="empty-state empty-state--plain">
                    当前账号没有可用于创建用户的部门。
                  </p>
                </div>
                <div v-if="canReadRoles" class="role-picker">
                  <span class="field__label">初始角色</span>
                  <p class="field__hint">未选择时后端会尝试授予普通员工默认角色。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.roleKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索角色"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshAssignableRoleOptionsFromSearch">
                      查询角色
                    </button>
                  </div>
                  <div class="option-picker__grid">
                    <label v-for="role in initialAssignableRoles" :key="role.id" class="option-card">
                      <input
                        type="checkbox"
                        :checked="userCreateForm.roleIds.includes(role.id)"
                        @change="toggleCreateRole(role.id, ($event.target as HTMLInputElement).checked)"
                      />
                      <span>{{ formatRoleLabel(role) }}</span>
                    </label>
                  </div>
                </div>
                <label
                  v-if="selectedCreateRoles.some(isHighRiskAdminRole)"
                  class="confirm confirm--inline modal-confirm"
                >
                  <input v-model="userCreateForm.confirmedHighRisk" type="checkbox" />
                  <span>确认授予高风险角色</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeUserModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canCreateAdminUser">
                {{ userAdminBusy.creating ? "创建中..." : "创建用户" }}
              </button>
            </footer>
          </form>

          <form v-else-if="userModalMode === 'edit' && selectedAdminUser" @submit.prevent="submitPatchSelectedAdminUser">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>登录名</dt>
                  <dd>{{ selectedAdminUser.username }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前角色</dt>
                  <dd>{{ formatRoleList(selectedAdminUser.roles) }}</dd>
                </div>
              </dl>
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">显示名</span>
                  <p class="field__hint">用于页面展示、操作记录归属和审计事件摘要。</p>
                  <input v-model.trim="userEditForm.name" class="control" type="text" />
                </label>
                <label class="field">
                  <span class="field__label">账号状态</span>
                  <p class="field__hint">禁用会吊销用户会话；锁定状态通常由登录失败策略触发。</p>
                  <select v-model="userEditForm.status" class="control">
                    <option value="active">{{ formatStatusOption("active") }}</option>
                    <option value="disabled">{{ formatStatusOption("disabled") }}</option>
                    <option value="locked">{{ formatStatusOption("locked") }}</option>
                  </select>
                </label>
                <label
                  v-if="userEditForm.status === 'disabled' && selectedAdminUserIsSystemAdmin"
                  class="confirm confirm--inline modal-confirm"
                >
                  <input v-model="userEditForm.confirmedDisableAdmin" type="checkbox" />
                  <span>确认禁用系统管理员账号</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeUserModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canUpdateSelectedAdminUser">
                {{ userAdminBusy.updating ? "保存中..." : "保存修改" }}
              </button>
            </footer>
          </form>

          <div v-else-if="userModalMode === 'departments' && selectedAdminUser">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>用户</dt>
                  <dd>{{ selectedAdminUser.name || selectedAdminUser.username }}</dd>
                </div>
                <div class="summary__row">
                  <dt>当前部门</dt>
                  <dd>{{ formatDepartmentList(selectedUserDepartmentsForDisplay) }}</dd>
                </div>
                <div class="summary__row">
                  <dt>主部门</dt>
                  <dd>
                    {{
                      formatDepartmentLabel(
                        selectedUserDepartmentsForDisplay.find((department) => department.is_primary) ??
                          selectedUserDepartmentsForDisplay[0],
                      )
                    }}
                  </dd>
                </div>
              </dl>
              <div
                v-if="selectedUserDepartmentPagination.total > selectedUserDepartmentPagination.pageSize"
                class="pagination-bar pagination-bar--compact"
                aria-label="用户当前部门分页"
              >
                <span>
                  当前显示 {{ paginationStart(selectedUserDepartmentPagination) }}-{{
                    paginationEnd(selectedUserDepartmentPagination)
                  }} / {{ selectedUserDepartmentPagination.total }} 个部门
                </span>
                <label>
                  每页
                  <select
                    v-model.number="selectedUserDepartmentPagination.pageSize"
                    class="control control--small"
                    :disabled="userAdminBusy.loading"
                    @change="changePaginationPageSize(selectedUserDepartmentPagination, refreshSelectedUserDepartmentsPage)"
                  >
                    <option v-for="size in pageSizeOptions" :key="`selected-user-department-page-size-${size}`" :value="size">
                      {{ size }}
                    </option>
                  </select>
                </label>
                <div class="pagination-bar__actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    :disabled="selectedUserDepartmentPagination.page <= 1 || userAdminBusy.loading"
                    @click="changePaginationPage(selectedUserDepartmentPagination, refreshSelectedUserDepartmentsPage, selectedUserDepartmentPagination.page - 1)"
                  >
                    上一页
                  </button>
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    :disabled="selectedUserDepartmentPagination.page >= paginationTotalPages(selectedUserDepartmentPagination) || userAdminBusy.loading"
                    @click="changePaginationPage(selectedUserDepartmentPagination, refreshSelectedUserDepartmentsPage, selectedUserDepartmentPagination.page + 1)"
                  >
                    下一页
                  </button>
                </div>
              </div>
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
              <div class="option-picker">
                <span class="field__label">调整归属部门</span>
                <p class="field__hint">至少选择一个部门；保存时第一个被选中的部门会作为主部门。</p>
                <div class="selector-search">
                  <input
                    v-model.trim="optionSearchForm.departmentKeyword"
                    class="control control--compact"
                    type="search"
                    placeholder="搜索部门"
                  />
                  <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                    查询部门
                  </button>
                </div>
                <div class="option-picker__grid">
                  <label v-for="department in activeDepartments" :key="department.id" class="option-card">
                    <input
                      type="checkbox"
                      :checked="selectedUserDepartmentIds.has(department.id)"
                      :disabled="!canManageDepartments || userAdminBusy.updatingDepartments"
                      @change="toggleSelectedUserDepartment(department.id, ($event.target as HTMLInputElement).checked)"
                    />
                    <span>
                      {{ formatDepartmentLabel(department) }}
                      <small v-if="userDepartmentForm.departmentIds[0] === department.id">主部门</small>
                    </span>
                  </label>
                </div>
                <p v-if="!activeDepartments.length" class="empty-state empty-state--plain">当前没有可用的启用部门。</p>
              </div>
              <label v-if="selectedUserPrimaryDepartmentWillChange" class="confirm confirm--inline modal-confirm">
                <input v-model="userDepartmentForm.confirmedReplacePrimary" type="checkbox" />
                <span>确认更换该用户的主部门</span>
              </label>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeUserModal">
                取消
              </button>
              <button
                class="button"
                type="button"
                @click="saveSelectedUserDepartments"
                :disabled="!canSaveSelectedUserDepartments"
              >
                {{ userAdminBusy.updatingDepartments ? "保存中..." : "保存部门归属" }}
              </button>
            </footer>
          </div>

          <div v-else-if="userModalMode === 'roles' && selectedAdminUser">
            <div class="modal__body modal__body--split">
              <section class="modal-pane">
                <h4>当前角色</h4>
                <div v-if="selectedUserRoleBindings.length" class="role-binding-list">
                  <article v-for="binding in selectedUserRoleBindings" :key="binding.id" class="role-binding-row">
                    <div>
                      <strong>{{ formatRoleCodeLabel(binding.role_code, binding.role_name ?? binding.role_id) }}</strong>
                      <span>{{ formatRoleBindingScope(binding) }}</span>
                    </div>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      @click="revokeSelectedUserRoleBinding(binding)"
                      :disabled="!canManageRoles || userAdminBusy.updatingRoles"
                    >
                      撤销
                    </button>
                  </article>
                </div>
                <p v-else class="empty-state empty-state--plain">当前用户尚无可展示的角色绑定。</p>
                <div
                  v-if="selectedUserRoleBindingPagination.total > 0"
                  class="pagination-bar pagination-bar--compact"
                  aria-label="用户角色绑定分页"
                >
                  <span>
                    第 {{ selectedUserRoleBindingPagination.page }} /
                    {{ paginationTotalPages(selectedUserRoleBindingPagination) }} 页，
                    {{ paginationStart(selectedUserRoleBindingPagination) }}-{{
                      paginationEnd(selectedUserRoleBindingPagination)
                    }} / {{ selectedUserRoleBindingPagination.total }} 个绑定
                  </span>
                  <label>
                    每页
                    <select
                      v-model.number="selectedUserRoleBindingPagination.pageSize"
                      class="control control--small"
                      :disabled="userAdminBusy.loading || userAdminBusy.updatingRoles"
                      @change="changePaginationPageSize(selectedUserRoleBindingPagination, refreshSelectedUserRoleBindingsPage)"
                    >
                      <option v-for="size in pageSizeOptions" :key="`selected-user-role-binding-page-size-${size}`" :value="size">
                        {{ size }}
                      </option>
                    </select>
                  </label>
                  <div class="pagination-bar__actions">
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="selectedUserRoleBindingPagination.page <= 1 || userAdminBusy.loading || userAdminBusy.updatingRoles"
                      @click="changePaginationPage(selectedUserRoleBindingPagination, refreshSelectedUserRoleBindingsPage, selectedUserRoleBindingPagination.page - 1)"
                    >
                      上一页
                    </button>
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      :disabled="selectedUserRoleBindingPagination.page >= paginationTotalPages(selectedUserRoleBindingPagination) || userAdminBusy.loading || userAdminBusy.updatingRoles"
                      @click="changePaginationPage(selectedUserRoleBindingPagination, refreshSelectedUserRoleBindingsPage, selectedUserRoleBindingPagination.page + 1)"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </section>

              <section class="modal-pane">
                <h4>授予角色</h4>
                <div class="selector-search selector-search--stacked">
                  <input
                    v-model.trim="optionSearchForm.roleKeyword"
                    class="control control--compact"
                    type="search"
                    placeholder="搜索角色"
                  />
                  <button class="button button--secondary button--small" type="button" @click="refreshAssignableRoleOptionsFromSearch">
                    查询角色
                  </button>
                </div>
                <label class="field field--full modal-field">
                  <span class="field__label">角色</span>
                  <p class="field__hint">企业级角色作用于全企业；部门管理员和知识库管理员必须选择具体作用域。</p>
                  <select
                    class="control"
                    :value="roleBindingForm.roleId"
                    :disabled="!canManageRoles"
                    @change="onRoleBindingRoleChange(($event.target as HTMLSelectElement).value)"
                  >
                    <option value="">请选择角色</option>
                    <option v-for="role in assignableRoles" :key="role.id" :value="role.id">
                      {{ formatRoleLabel(role) }} / {{ formatRoleScopeType(role.scope_type) }}
                    </option>
                  </select>
                </label>
                <label
                  v-if="selectedRoleBindingScopeType === 'department'"
                  class="field field--full modal-field"
                >
                  <span class="field__label">部门作用域</span>
                  <p class="field__hint">该用户只会在选定部门范围内获得部门管理员权限。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.departmentKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索部门"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshDepartmentOptionsFromSearch">
                      查询部门
                    </button>
                  </div>
                  <select v-model="roleBindingForm.scopeId" class="control" :disabled="!canManageRoles">
                    <option value="">请选择部门</option>
                    <option v-for="department in activeDepartments" :key="department.id" :value="department.id">
                      {{ formatDepartmentLabel(department) }}
                    </option>
                  </select>
                </label>
                <label
                  v-else-if="selectedRoleBindingScopeType === 'knowledge_base'"
                  class="field field--full modal-field"
                >
                  <span class="field__label">知识库作用域</span>
                  <p class="field__hint">该用户只会在选定知识库范围内获得知识库、文档和导入管理权限。</p>
                  <div class="selector-search">
                    <input
                      v-model.trim="optionSearchForm.knowledgeBaseKeyword"
                      class="control control--compact"
                      type="search"
                      placeholder="搜索知识库"
                    />
                    <button class="button button--secondary button--small" type="button" @click="refreshKnowledgeBaseOptionsFromSearch">
                      查询知识库
                    </button>
                  </div>
                  <select v-model="roleBindingForm.scopeId" class="control" :disabled="!canManageRoles">
                    <option value="">请选择知识库</option>
                    <option
                      v-for="knowledgeBase in activeKnowledgeBases"
                      :key="knowledgeBase.id"
                      :value="knowledgeBase.id"
                    >
                      {{ formatKnowledgeBaseLabel(knowledgeBase) }}
                    </option>
                  </select>
                </label>
                <p
                  v-if="selectedRoleBindingScopeType === 'knowledge_base' && !canManageKnowledgeBases"
                  class="empty-state empty-state--plain"
                >
                  当前账号缺少 knowledge_base:manage，无法读取可绑定的知识库列表。
                </p>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="roleBindingForm.confirmedHighRisk" type="checkbox" />
                  <span>确认授予高风险角色</span>
                </label>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="roleBindingForm.confirmedRemoveAdmin" type="checkbox" />
                  <span>确认撤销系统管理员角色</span>
                </label>
                <button
                  class="button"
                  type="button"
                  @click="addSelectedUserRoleBinding"
                  :disabled="!canAddSelectedUserRole"
                >
                  {{ userAdminBusy.updatingRoles ? "处理中..." : "授予角色" }}
                </button>
                <p v-if="roleBindingDisabledReason" class="empty-state empty-state--plain">
                  {{ roleBindingDisabledReason }}
                </p>
              </section>
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeUserModal">
                完成
              </button>
            </footer>
          </div>

          <form v-else-if="userModalMode === 'password' && selectedAdminUser" @submit.prevent="submitPasswordReset">
            <div class="modal__body">
              <dl class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>用户</dt>
                  <dd>{{ selectedAdminUser.name || selectedAdminUser.username }}</dd>
                </div>
                <div class="summary__row">
                  <dt>账号状态</dt>
                  <dd>{{ formatStatusText(selectedAdminUser.status) }}</dd>
                </div>
              </dl>
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label class="field">
                  <span class="field__label">新密码</span>
                  <p class="field__hint">必须满足当前 active_config 中的密码策略。</p>
                  <input v-model="passwordResetForm.newPassword" class="control" type="password" />
                </label>
                <label class="field">
                  <span class="field__label">确认新密码</span>
                  <p class="field__hint">用于避免误输入。</p>
                  <input v-model="passwordResetForm.passwordConfirm" class="control" type="password" />
                </label>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="passwordResetForm.forceChangePassword" type="checkbox" />
                  <span>强制下次登录修改密码</span>
                </label>
                <label class="confirm confirm--inline modal-confirm">
                  <input v-model="passwordResetForm.confirmed" type="checkbox" />
                  <span>确认重置密码并吊销会话</span>
                </label>
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeUserModal">
                取消
              </button>
              <button class="button" type="submit" :disabled="!canResetSelectedUserPassword">
                {{ userAdminBusy.resettingPassword ? "重置中..." : "重置密码" }}
              </button>
            </footer>
          </form>

          <div v-else-if="userModalMode === 'delete' && selectedAdminUser">
            <div class="modal__body">
              <div class="danger-panel">
                <h4>确认删除用户</h4>
                <p>
                  将删除用户 {{ selectedAdminUser.name || selectedAdminUser.username }}，并由后端吊销相关会话。删除后该账号不能再登录。
                </p>
                <label class="confirm confirm--inline">
                  <input v-model="userDangerForm.confirmedDelete" type="checkbox" />
                  <span>确认删除该用户</span>
                </label>
              </div>
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeUserModal">
                取消
              </button>
              <button
                class="button button--danger"
                type="button"
                @click="deleteSelectedAdminUser"
                :disabled="!canDeleteSelectedAdminUser"
              >
                {{ userAdminBusy.updating ? "删除中..." : "删除用户" }}
              </button>
            </footer>
          </div>
        </section>
      </div>
    </section>
  </main>

  <main v-else class="shell">
    <aside class="sidebar">
      <div class="sidebar__block">
        <p class="brand">Little Bear 管理后台</p>
        <h1 class="title">首次初始化配置</h1>
        <p :class="toneClass(statusTone)">{{ statusLabel }}</p>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">当前摘要</h2>
        <dl class="summary">
          <div v-for="item in summaryItems" :key="item.label" class="summary__row">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">本地核查</h2>
        <div class="check-counter">
          <span :class="toneClass(localChecksPassed ? 'success' : 'error')">
            {{ localChecksPassed ? "可校验" : `${localBlockingIssues.length} 阻断` }}
          </span>
          <span :class="toneClass(localWarningIssues.length ? 'warning' : 'neutral')">
            {{ localWarningIssues.length }} 提醒
          </span>
        </div>
        <ul class="section-checks">
          <li v-for="item in sectionCheckItems" :key="item.title">
            <span>{{ item.title }}</span>
            <span :class="toneClass(item.tone)">{{ sectionToneText(item) }}</span>
          </li>
        </ul>
      </div>

      <div class="sidebar__block">
        <h2 class="section-title">接口动作</h2>
        <div class="stack">
          <button class="button button--secondary" type="button" @click="refreshState" :disabled="busy.refreshing">
            {{ busy.refreshing ? "刷新中..." : "刷新状态" }}
          </button>
          <button class="button button--secondary" type="button" @click="resetForm">
            恢复默认值
          </button>
        </div>
      </div>
    </aside>

    <section class="workspace">
      <header class="toolbar">
        <div>
          <p class="eyebrow">/admin/setup-initialization</p>
          <h2>初始化配置工作台</h2>
        </div>
        <div v-if="feedback" :class="['feedback', `feedback--${feedback.tone}`]">
          {{ feedback.message }}
        </div>
      </header>

      <section class="flow-strip">
        <div v-for="item in flowItems" :key="item.label" class="flow-step">
          <span>{{ item.label }}</span>
          <strong :class="toneClass(item.tone)">{{ item.value }}</strong>
        </div>
      </section>

      <div class="content-grid">
        <section class="editor">
	          <section v-for="section in sections" :key="section.title" class="panel">
	            <header class="panel__header">
              <h3>{{ section.title }}</h3>
              <span :class="toneClass(sectionCheckItems.find((item) => item.title === section.title)?.tone ?? 'neutral')">
                {{ sectionToneText(sectionCheckItems.find((item) => item.title === section.title) ?? { errors: 0, warnings: 0 }) }}
              </span>
	            </header>
	            <div class="form-grid">
	              <label
	                v-for="field in normalFieldsBySection.get(section.title) ?? []"
	                :key="String(field.key)"
	                class="field"
	                :class="{
	                  'field--full': field.span === 'full',
	                  'field--checkbox': field.input === 'checkbox',
	                  'field--error': hasFieldError(field.key),
	                  'field--warning': hasFieldWarning(field.key),
	                }"
	              >
                <template v-if="field.input === 'checkbox'">
                  <input
                    class="checkbox"
                    type="checkbox"
                    :checked="Boolean(form[field.key])"
                    @change="updateFieldFromCheckbox(field, ($event.target as HTMLInputElement).checked)"
                  />
                  <span>{{ field.label }}</span>
                </template>

                <template v-else>
                  <span class="field__label">
                    {{ field.label }}
                    <span v-if="field.required" class="required-mark">必填</span>
                  </span>
                  <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
                    {{ field.hint }}
                  </p>
                  <select
                    v-if="field.input === 'select'"
                    class="control"
                    :value="String(form[field.key])"
                    @change="updateFieldFromSelect(field, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in field.options" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  <input
                    v-else
                    class="control"
                    :type="field.input"
                    :min="field.min"
                    :step="field.step"
                    :placeholder="field.placeholder"
                    :value="String(form[field.key] ?? '')"
                    @input="
                      updateFieldFromInput(field, ($event.target as HTMLInputElement).value)
                    "
                  />
                </template>
                <ul v-if="fieldIssues(field.key).length" class="field-issues">
                  <li
                    v-for="issue in fieldIssues(field.key)"
                    :key="`${issue.tone}-${issue.message}`"
                    :class="`field-issue field-issue--${issue.tone}`"
                  >
                    {{ issue.message }}
                  </li>
	                </ul>
	              </label>
	            </div>
	            <div
	              v-if="(checkboxFieldsBySection.get(section.title) ?? []).length"
	              class="checkbox-grid"
	            >
	              <label
	                v-for="field in checkboxFieldsBySection.get(section.title) ?? []"
	                :key="String(field.key)"
	                class="field field--checkbox"
	                :class="{
	                  'field--error': hasFieldError(field.key),
	                  'field--warning': hasFieldWarning(field.key),
	                }"
	              >
	                <input
	                  class="checkbox"
	                  type="checkbox"
	                  :checked="Boolean(form[field.key])"
	                  @change="updateFieldFromCheckbox(field, ($event.target as HTMLInputElement).checked)"
	                />
	                <span>{{ field.label }}</span>
	                <p class="field__hint" :class="{ 'field__hint--empty': !field.hint }" :aria-hidden="!field.hint">
	                  {{ field.hint }}
	                </p>
	                <ul v-if="fieldIssues(field.key).length" class="field-issues">
	                  <li
	                    v-for="issue in fieldIssues(field.key)"
	                    :key="`${issue.tone}-${issue.message}`"
	                    :class="`field-issue field-issue--${issue.tone}`"
	                  >
	                    {{ issue.message }}
	                  </li>
	                </ul>
	              </label>
	            </div>
	          </section>

        </section>

        <aside class="rail">
          <section class="panel">
            <header class="panel__header">
              <h3>初始化状态</h3>
            </header>
            <dl v-if="setupState" class="summary">
              <div class="summary__row">
                <dt>是否已初始化</dt>
                <dd>{{ formatBoolean(setupState.initialized) }}</dd>
              </div>
              <div class="summary__row">
                <dt>初始化状态</dt>
                <dd>{{ formatSetupStatus(setupState.setup_status) }}</dd>
              </div>
              <div class="summary__row">
                <dt>当前配置版本</dt>
                <dd>{{ setupState.active_config_version ?? "-" }}</dd>
              </div>
              <div class="summary__row">
                <dt>需要初始化</dt>
                <dd>{{ formatBoolean(setupState.setup_required) }}</dd>
              </div>
              <div class="summary__row">
                <dt>配置是否存在</dt>
                <dd>{{ formatBoolean(setupState.active_config_present) }}</dd>
              </div>
              <div class="summary__row">
                <dt>允许恢复初始化</dt>
                <dd>{{ formatBoolean(setupState.recovery_setup_allowed) }}</dd>
              </div>
              <div class="summary__row">
                <dt>恢复原因</dt>
                <dd>{{ setupState.recovery_reason ?? "-" }}</dd>
              </div>
            </dl>
            <p v-else class="empty-state">尚未获取状态。</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>本地核查与后端校验</h3>
            </header>
            <div class="result-block">
              <p :class="toneClass(localChecksPassed ? 'success' : 'error')">
                {{ localChecksPassed ? "本地核查通过" : "本地核查未通过" }}
              </p>
              <ul v-if="localValidationIssues.length" class="issue-list">
                <li
                  v-for="issue in localValidationIssues"
                  :key="`${issue.section}-${issue.tone}-${issue.message}`"
                  :class="issue.tone === 'warning' ? 'issue-list__warning' : undefined"
                >
                  <strong>{{ issue.section }}</strong>
                  <span>{{ issueToneText(issue.tone) }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
            </div>
            <div v-if="validationResult" class="result-block">
              <p :class="toneClass(validationResult.valid ? 'success' : 'error')">
                {{ validationResult.valid ? "后端校验通过" : "后端校验未通过" }}
              </p>
              <ul v-if="validationResult.errors.length" class="issue-list">
                <li v-for="issue in validationResult.errors" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <ul v-if="validationResult.warnings.length" class="issue-list issue-list--warning">
                <li v-for="issue in validationResult.warnings" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
            </div>
            <div v-else-if="validationErrorPayload" class="result-block">
              <p class="tone tone--error">后端校验请求失败</p>
              <ul v-if="validationErrorItems.length" class="issue-list">
                <li v-for="issue in validationErrorItems" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <p v-else class="empty-state">{{ validationErrorPayload.message ?? "未返回可解析的校验错误明细。" }}</p>
            </div>
            <p v-else class="empty-state">尚未执行配置校验。</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h3>提交结果</h3>
            </header>
            <dl v-if="initializationResult" class="summary">
              <div class="summary__row">
                <dt>是否已初始化</dt>
                <dd>{{ formatBoolean(initializationResult.initialized) }}</dd>
              </div>
              <div class="summary__row">
                <dt>当前配置版本</dt>
                <dd>{{ initializationResult.active_config_version }}</dd>
              </div>
              <div class="summary__row">
                <dt>企业 ID</dt>
                <dd class="summary__value--break">{{ initializationResult.enterprise_id }}</dd>
              </div>
              <div class="summary__row">
                <dt>管理员用户 ID</dt>
                <dd class="summary__value--break">{{ initializationResult.admin_user_id }}</dd>
              </div>
            </dl>
            <div v-else-if="initializationErrorPayload" class="result-block">
              <p class="tone tone--error">初始化提交失败</p>
              <ul v-if="initializationFailedChecks.length" class="issue-list">
                <li v-for="check in initializationFailedChecks" :key="check.name">
                  <strong>{{ check.name }}</strong>
                  <span>{{ check.required ? "required" : "optional" }}</span>
                  <p>{{ check.message }}</p>
                </li>
              </ul>
              <ul v-else-if="initializationErrorItems.length" class="issue-list">
                <li v-for="issue in initializationErrorItems" :key="`${normalizeIssueCode(issue)}-${issue.path}`">
                  <strong>{{ normalizeIssueCode(issue) }}</strong>
                  <span>{{ issue.path }}</span>
                  <p>{{ issue.message }}</p>
                </li>
              </ul>
              <dl v-else-if="initializationDatabaseError" class="summary">
                <div class="summary__row">
                  <dt>异常类型</dt>
                  <dd>{{ initializationDatabaseError.type ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>驱动错误</dt>
                  <dd>{{ initializationDatabaseError.driver_type ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>错误信息</dt>
                  <dd class="summary__value--break">{{ initializationDatabaseError.message ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>SQLSTATE</dt>
                  <dd>{{ initializationDatabaseError.sqlstate ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>约束</dt>
                  <dd class="summary__value--break">{{ initializationDatabaseError.constraint ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>数据表</dt>
                  <dd>{{ initializationDatabaseError.table ?? "-" }}</dd>
                </div>
                <div class="summary__row">
                  <dt>字段</dt>
                  <dd>{{ initializationDatabaseError.column ?? "-" }}</dd>
                </div>
              </dl>
              <p v-else class="empty-state">{{ initializationErrorPayload.message ?? "未返回可解析的初始化错误明细。" }}</p>
            </div>
            <p v-else class="empty-state">尚未提交初始化。</p>
          </section>
        </aside>
      </div>

      <footer class="action-bar">
        <label class="confirm">
          <input v-model="submitConfirmed" type="checkbox" />
          <span>{{ submitConfirmationText }}</span>
        </label>
        <p class="gate-message">{{ validationGateMessage }}</p>
        <div class="action-bar__buttons">
          <button class="button button--secondary" type="button" @click="runValidation" :disabled="!canValidate">
            {{ busy.validating ? "校验中..." : "校验配置" }}
          </button>
          <button class="button" type="button" @click="runInitialization" :disabled="!canSubmit">
            {{ submitButtonText }}
          </button>
        </div>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.auth-screen {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  color: #18202a;
  background: #f3f5f7;
}

.login-card {
  width: min(460px, 100%);
  display: grid;
  gap: 22px;
  padding: 28px;
  background: #ffffff;
  border: 1px solid #d8dee6;
  border-radius: 8px;
}

.login-card__header {
  display: grid;
  gap: 8px;
}

.auth-copy {
  margin: 0;
  color: #667182;
}

.login-form {
  display: grid;
  gap: 16px;
}

.admin-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  color: #18202a;
  background: #f3f5f7;
}

.admin-sidebar {
  background: #20252d;
  color: #f4f6f8;
  padding: 24px 20px;
  display: grid;
  align-content: start;
  gap: 22px;
  border-right: 1px solid #303744;
}

.admin-nav {
  display: grid;
  gap: 8px;
}

.admin-nav__item {
  width: 100%;
  border: 1px solid #3a4350;
  border-radius: 8px;
  background: transparent;
  color: #d6dce5;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
}

.admin-nav__item--active {
  border-color: #80b6a4;
  background: #2a403a;
  color: #ffffff;
}

.admin-workspace {
  min-width: 0;
  padding: 24px;
  display: grid;
  align-content: start;
  gap: 20px;
}

.admin-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
}

.admin-toolbar h2 {
  margin: 0;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 14px;
}

.user-menu > div {
  display: grid;
  justify-items: end;
  gap: 2px;
}

.user-menu span {
  color: #667182;
  font-size: 12px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.panel--wide {
  grid-column: 1 / -1;
}

.panel__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.config-version-strip {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.config-version-card {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 14px 16px;
  display: grid;
  gap: 4px;
}

.config-version-card span {
  color: #667182;
  font-size: 12px;
}

.config-version-card strong {
  color: #1d2935;
  font-size: 24px;
}

.config-secondary-grid {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 16px;
}

.config-secondary-grid--single {
  grid-template-columns: minmax(0, 1fr);
}

.config-versions {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 16px;
  display: grid;
  align-content: start;
  gap: 10px;
}

.version-row strong {
  overflow-wrap: anywhere;
}

.version-row span {
  color: #667182;
  font-size: 12px;
}

.config-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.result-block--compact {
  padding: 0;
}

.config-versions__title {
  margin: 0;
  color: #1d2935;
  font-size: 14px;
}

.version-list {
  display: grid;
  gap: 10px;
}

.audit-list {
  display: grid;
  gap: 10px;
}

.version-row {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.version-row > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.config-preview {
  min-width: 0;
}

.config-preview summary {
  cursor: pointer;
  color: #1d2935;
  overflow-wrap: anywhere;
}

.config-preview__sections {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

.config-preview__section {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #f7f9fb;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.config-preview__section header {
  min-width: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.config-preview__section header span,
.config-preview__section > p {
  color: #667182;
}

.config-preview__section dl {
  display: grid;
  gap: 6px;
}

.config-preview__section dl > div {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(110px, 0.55fr) minmax(0, 1fr);
  gap: 8px;
}

.config-preview__section dt {
  color: #667182;
}

.config-preview__section dd {
  margin: 0;
  color: #1d2935;
  overflow-wrap: anywhere;
}

.config-form-sections {
  display: grid;
  gap: 16px;
}

.config-form-section {
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 14px;
  display: grid;
  gap: 14px;
}

.config-form-section > header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.config-form-section > header h4 {
  margin: 0;
}

.config-form-section > header p,
.config-form-section > header span {
  color: #667182;
}

.config-audit-details summary {
  cursor: pointer;
  color: #1d2935;
  font-weight: 700;
}

.audit-row {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 10px 12px;
  display: grid;
  gap: 6px;
}

.audit-row header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: start;
}

.audit-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.audit-row p {
  margin: 0;
  color: #667182;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.audit-row__error {
  color: #9a2f2f !important;
}

.form-grid--compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 16px;
}

.form-grid--modal {
  padding: 0;
}

.admin-list-panel {
  min-width: 0;
  display: grid;
  gap: 16px;
  padding: 18px;
}

.pagination-bar {
  min-width: 0;
  border: 1px solid #e1e6ee;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #667182;
  font-size: 13px;
}

.pagination-bar label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.pagination-bar__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.pagination-bar--compact {
  align-items: flex-start;
  flex-wrap: wrap;
  justify-content: flex-start;
}

.list-filter {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(180px, 240px) auto;
  gap: 14px;
  align-items: end;
}

.list-filter .control {
  box-sizing: border-box;
  min-height: 43px;
}

.list-filter > .field {
  grid-template-rows: auto minmax(35px, auto) auto;
}

.list-filter > .field:not(:has(.field__hint)) {
  grid-template-rows: auto auto;
}

.list-filter > .button {
  align-self: end;
  justify-self: start;
  width: max-content;
  min-width: 88px;
  height: 43px;
  min-height: 0;
  box-sizing: border-box;
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.list-filter--imports {
  grid-template-columns: minmax(220px, 1fr) repeat(3, minmax(140px, 180px)) minmax(96px, auto);
}

.list-filter--documents {
  grid-template-columns: minmax(180px, 240px) auto;
}

.list-filter--knowledge {
  grid-template-columns: minmax(260px, 1fr) minmax(180px, 240px) minmax(88px, auto);
  align-items: end;
}

.list-filter--diagnostics {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}

.list-filter--index-ops {
  grid-template-columns: minmax(220px, 1fr) auto minmax(180px, 0.7fr) auto minmax(190px, 0.75fr) auto;
}

.list-filter--index-restore {
  grid-template-columns: minmax(260px, 1.2fr) minmax(130px, 0.45fr) minmax(160px, 0.6fr) minmax(260px, 1fr) auto;
}

.list-filter--model-calls {
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
}

.list-filter .field {
  grid-column: auto;
}

.diagnostics-pane {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 16px;
  display: grid;
  gap: 14px;
}

.resource-section {
  min-width: 0;
  border-top: 1px solid #e7ebf0;
  padding-top: 16px;
  display: grid;
  gap: 18px;
}

.resource-section--document-manager {
  border-top: 0;
  padding-top: 0;
}

.resource-block {
  min-width: 0;
  display: grid;
  gap: 14px;
}

.index-ops-panel {
  padding-top: 12px;
  border-top: 1px solid #e7ebf0;
}

.index-health-list {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.index-health-card {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
  display: grid;
  gap: 12px;
}

.index-health-card--selected {
  border-color: #8ec5b1;
  background: #f7fcfa;
}

.index-health-card__header {
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 12px;
}

.index-health-card__header > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.index-health-card__header strong,
.index-health-card__header span,
.index-health-metric dd {
  overflow-wrap: anywhere;
}

.index-health-card__header strong {
  color: #1d2935;
  font-size: 15px;
}

.index-health-card__header > div > span {
  color: #667182;
  font-size: 12px;
}

.index-health-metrics {
  min-width: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.index-health-metric {
  min-width: 0;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 10px 12px;
  display: grid;
  gap: 4px;
}

.index-health-metric dt {
  margin: 0;
  color: #667182;
  font-size: 12px;
}

.index-health-metric dd {
  margin: 0;
  color: #1d2935;
  font-size: 12px;
  line-height: 1.45;
}

.index-ops-layout {
  min-width: 0;
  display: grid;
  gap: 12px;
}

.index-ops-composite {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.48fr);
  gap: 18px;
  align-items: start;
}

.index-ops-selector {
  min-width: 0;
  display: grid;
  gap: 12px;
}

.index-ops-actions-stack {
  min-width: 0;
  border-left: 1px solid #eef1f5;
  padding-left: 18px;
  display: grid;
  gap: 14px;
}

.index-ops-action-panel {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.index-ops-action-panel + .index-ops-action-panel {
  border-top: 1px solid #eef1f5;
  padding-top: 14px;
}

.index-ops-action-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(112px, auto);
  align-items: center;
  gap: 10px;
}

.index-ops-card {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
  display: grid;
  align-content: start;
  gap: 12px;
}

.index-ops-card--restore {
  grid-column: 1 / -1;
}

.index-ops-card header,
.index-ops-selector header,
.index-ops-action-panel header {
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 10px;
}

.index-ops-card h5,
.index-ops-selector h5,
.index-ops-action-panel h5 {
  margin: 0;
  color: #1d2935;
  font-size: 14px;
}

.index-ops-card p,
.index-ops-selector p,
.index-ops-action-panel p {
  margin: 4px 0 0;
  color: #667182;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.index-ops-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
}

.index-ops-card--restore .index-ops-row {
  grid-template-columns: minmax(160px, 0.45fr) minmax(220px, 0.55fr);
}

.index-ops-row--actions {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.resource-section__header,
.document-detail-pane__header {
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 12px;
}

.resource-section__header h4,
.document-detail-pane__header h4 {
  margin: 0;
  color: #1d2935;
}

.document-detail-pane__header > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.resource-section__header p,
.document-detail-pane__header p,
.document-detail-pane__header span {
  margin: 4px 0 0;
  color: #667182;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.summary.document-detail-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 12px 14px;
}

.summary.document-detail-summary .summary__row {
  grid-template-columns: 1fr;
  gap: 4px;
  align-content: start;
}

.summary.document-detail-summary dt,
.summary.document-detail-summary dd {
  margin: 0;
  text-align: left;
  justify-self: start;
}

.summary.document-detail-summary dd {
  font-weight: 600;
}

.document-version-index-grid {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(260px, 0.6fr) minmax(0, 1.4fr);
  gap: 14px;
  align-items: start;
}

.document-detail-pane {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 14px;
  display: grid;
  gap: 12px;
}

.document-version-list {
  min-width: 0;
  border: 1px solid #e1e6ee;
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
  display: grid;
}

.document-version-row {
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #eef1f5;
}

.document-version-row:last-child {
  border-bottom: 0;
}

.document-version-row strong {
  color: #1d2935;
}

.index-version-list {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.index-version-row {
  min-width: 0;
  border: 1px solid #e1e6ee;
  border-radius: 8px;
  background: #ffffff;
  padding: 10px 12px;
  display: grid;
  gap: 10px;
}

.index-version-row--selectable {
  grid-template-columns: 20px minmax(0, 1fr);
  align-items: start;
}

.index-version-row__selector {
  margin-top: 3px;
}

.index-version-row__body {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.index-version-row header {
  min-width: 0;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: start;
}

.index-version-row strong,
.index-version-row dd {
  overflow-wrap: anywhere;
}

.index-version-row dl {
  min-width: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.index-version-row dt {
  margin: 0 0 2px;
  color: #667182;
  font-size: 12px;
}

.index-version-row dd {
  margin: 0;
  color: #1d2935;
  font-size: 12px;
}

.index-rebuild-panel {
  min-width: 0;
  border-top: 1px solid #e7ebf0;
  padding-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.chunk-preview-list {
  min-width: 0;
  max-height: 360px;
  overflow: auto;
  border: 1px solid #e1e6ee;
  border-radius: 8px;
  background: #ffffff;
  display: grid;
}

.chunk-preview-list--table {
  max-height: 420px;
}

.chunk-preview-row {
  min-width: 0;
  border: 0;
  border-bottom: 1px solid #eef1f5;
  border-radius: 0;
  background: #ffffff;
  padding: 11px 12px;
  display: grid;
  gap: 8px;
}

.chunk-preview-row:last-child {
  border-bottom: 0;
}

.chunk-preview-row--button {
  width: 100%;
  appearance: none;
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
}

.chunk-preview-row--button:hover,
.chunk-preview-row--active {
  border-color: #eef1f5;
  background: #f3f7ff;
}

.chunk-preview-row header {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(72px, 0.35fr) minmax(70px, 0.3fr) minmax(88px, 0.35fr);
  gap: 8px;
  align-items: center;
}

.chunk-preview-row strong,
.chunk-preview-row span,
.chunk-preview-row p {
  overflow-wrap: anywhere;
}

.chunk-preview-row span {
  color: #667182;
  font-size: 12px;
}

.chunk-preview-row p {
  margin: 0;
  color: #1d2935;
  line-height: 1.55;
}

.upload-panel {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 16px;
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.8fr);
  gap: 18px;
  align-items: start;
}

.upload-panel__main {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.upload-panel__side {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
  display: grid;
  gap: 12px;
}

.upload-panel__side h4 {
  margin: 0;
}

.upload-panel--modal {
  background: #ffffff;
}

.control--file {
  padding: 10px;
}

.file-list {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.file-row {
  min-width: 0;
  border: 1px solid #e1e6ee;
  border-radius: 8px;
  padding: 10px;
  display: grid;
  gap: 2px;
}

.file-row strong,
.file-row span {
  overflow-wrap: anywhere;
}

.file-row span {
  color: #667182;
  font-size: 12px;
}

.upload-summary {
  margin: 0;
}

.upload-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.batch-action-bar {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 12px 14px;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

.entity-table {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.entity-table__row {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px 14px;
  display: grid;
  gap: 12px;
  align-items: center;
}

.entity-table--departments .entity-table__row {
  grid-template-columns: minmax(240px, 1.6fr) minmax(110px, 0.7fr) minmax(90px, 0.6fr) minmax(140px, 0.8fr);
}

.entity-table--users .entity-table__row {
  grid-template-columns: minmax(180px, 1.1fr) minmax(105px, 0.55fr) minmax(190px, 1.25fr) minmax(190px, 1.2fr) minmax(240px, 1.35fr);
}

.entity-table--configs .entity-table__row {
  grid-template-columns: minmax(130px, 0.65fr) minmax(100px, 0.45fr) minmax(150px, 0.7fr) minmax(150px, 0.7fr) minmax(220px, 1.2fr) minmax(220px, 1fr);
}

.entity-table--knowledge .entity-table__row {
  grid-template-columns: minmax(220px, 1.2fr) minmax(90px, 0.4fr) minmax(150px, 0.7fr) minmax(160px, 0.7fr) minmax(430px, auto);
}

.entity-table--folders .entity-table__row {
  grid-template-columns: minmax(220px, 1.35fr) minmax(100px, 0.5fr) minmax(180px, 0.9fr) minmax(150px, 0.75fr);
}

.entity-table--documents .entity-table__row {
  grid-template-columns: minmax(220px, 1.25fr) minmax(120px, 0.6fr) minmax(100px, 0.5fr) minmax(110px, 0.55fr) minmax(190px, 0.9fr) minmax(150px, 0.75fr) minmax(190px, 0.9fr);
}

.entity-table--documents-selectable .entity-table__row {
  grid-template-columns: 44px minmax(220px, 1.25fr) minmax(120px, 0.6fr) minmax(100px, 0.5fr) minmax(110px, 0.55fr) minmax(190px, 0.9fr) minmax(150px, 0.75fr) minmax(190px, 0.9fr);
}

.entity-table--imports .entity-table__row {
  grid-template-columns: minmax(220px, 1.2fr) minmax(100px, 0.5fr) minmax(160px, 0.8fr) minmax(100px, 0.5fr) minmax(130px, 0.65fr) minmax(140px, 0.7fr) minmax(160px, 0.8fr);
}

.entity-table--index-jobs .entity-table__row {
  grid-template-columns: 44px minmax(220px, 1.2fr) minmax(160px, 0.8fr) minmax(130px, 0.65fr) minmax(140px, 0.7fr) minmax(180px, 0.9fr);
}

.entity-table--index-health .entity-table__row {
  grid-template-columns: minmax(220px, 1.2fr) minmax(170px, 0.8fr) minmax(160px, 0.75fr) minmax(230px, 1fr) minmax(180px, 0.9fr);
}

.entity-table--snapshots .entity-table__row {
  grid-template-columns: minmax(240px, 1.2fr) minmax(90px, 0.4fr) minmax(180px, 0.8fr) minmax(180px, 0.8fr);
}

.entity-table--query-logs .entity-table__row {
  grid-template-columns: minmax(220px, 1.1fr) minmax(190px, 0.95fr) minmax(130px, 0.65fr) minmax(90px, 0.45fr) minmax(150px, 0.75fr) minmax(100px, 0.5fr);
}

.entity-table--model-calls .entity-table__row {
  grid-template-columns: minmax(190px, 1.2fr) minmax(150px, 0.85fr) minmax(140px, 0.75fr) minmax(90px, 0.45fr) minmax(150px, 0.75fr) minmax(96px, 0.45fr);
}

.entity-table__row--header {
  border-color: transparent;
  background: #eef2f5;
  color: #516072;
  font-size: 12px;
  font-weight: 700;
}

.entity-table__row--selected {
  border-color: #8ec5b1;
  background: #f4fbf8;
}

.entity-main,
.entity-cell {
  min-width: 0;
}

.entity-main {
  display: grid;
  gap: 4px;
}

.entity-main strong,
.entity-main span,
.entity-cell {
  overflow-wrap: anywhere;
}

.entity-main span,
.entity-cell,
.empty-inline {
  color: #667182;
  font-size: 12px;
}

.badge-list {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.badge {
  max-width: 100%;
  border: 1px solid #d8dee6;
  border-radius: 999px;
  background: #f8fafc;
  color: #445163;
  padding: 4px 8px;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.row-actions {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.row-actions--dense {
  justify-content: flex-start;
}

.row-actions--knowledge {
  flex-wrap: nowrap;
  white-space: nowrap;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  padding: 24px;
  display: grid;
  place-items: center;
  background: rgba(24, 32, 42, 0.48);
}

.modal {
  width: min(720px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  border: 1px solid #cdd5df;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 18px 50px rgba(24, 32, 42, 0.22);
}

.modal--wide {
  width: min(920px, 100%);
}

.modal--document-details {
  width: min(1180px, 100%);
  overflow: hidden;
}

.modal--workspace {
  width: min(1320px, 100%);
}

.modal__header,
.modal__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
}

.modal__header {
  border-bottom: 1px solid #e7ebf0;
  background: #fbfcfd;
}

.modal__header h3 {
  margin: 0;
}

.modal__body {
  padding: 18px;
  display: grid;
  gap: 16px;
}

.modal__body--documents {
  max-height: calc(100vh - 170px);
  overflow: auto;
  align-content: start;
}

.modal__body--document-details {
  max-height: calc(100vh - 170px);
  overflow: auto;
  align-content: start;
  gap: 18px;
  padding-right: 28px;
}

.modal__body--split {
  grid-template-columns: minmax(0, 1fr) minmax(260px, 0.9fr);
  align-items: start;
}

.modal__footer {
  border-top: 1px solid #e7ebf0;
  background: #fbfcfd;
}

.modal-summary {
  border: 1px solid #e7ebf0;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 12px 14px;
}

.modal-confirm {
  grid-column: 1 / -1;
}

.modal-field {
  padding: 0;
}

.modal-pane {
  min-width: 0;
  display: grid;
  gap: 12px;
}

.modal-pane h4,
.danger-panel h4 {
  margin: 0;
  color: #1d2935;
}

.danger-panel {
  border: 1px solid #f0c6c6;
  border-radius: 8px;
  background: #fff8f8;
  padding: 14px 16px;
  display: grid;
  gap: 10px;
}

.danger-panel p {
  margin: 0;
  color: #6c4450;
  overflow-wrap: anywhere;
}

.role-picker,
.option-picker {
  grid-column: 1 / -1;
  min-width: 0;
  display: grid;
  gap: 8px;
}

.selector-search {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: end;
  margin-top: 8px;
}

.selector-search--stacked {
  margin: 0 0 8px;
}

.option-picker__grid {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.role-option,
.option-card {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.role-option {
  color: #1d2935;
  overflow-wrap: anywhere;
}

.option-card {
  min-height: 48px;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px 12px;
  color: #1d2935;
  overflow-wrap: anywhere;
}

.option-card span {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.option-card small {
  color: #2f7d66;
  font-size: 11px;
}

@media (max-width: 760px) {
  .option-picker__grid {
    grid-template-columns: 1fr;
  }
}

.role-binding-list {
  display: grid;
  gap: 10px;
}

.role-binding-row {
  min-width: 0;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #ffffff;
  padding: 10px 12px;
}

.role-binding-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.role-binding-row > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.role-binding-row strong {
  overflow-wrap: anywhere;
}

.role-binding-row span {
  margin: 0;
  color: #667182;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  color: #18202a;
  background: #f3f5f7;
}

.sidebar {
  background: #20252d;
  color: #f4f6f8;
  padding: 24px 20px;
  display: grid;
  align-content: start;
  gap: 18px;
  border-right: 1px solid #303744;
}

.sidebar__block {
  display: grid;
  gap: 12px;
}

.brand {
  margin: 0;
  font-size: 12px;
  text-transform: uppercase;
  color: #98a4b5;
}

.title {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

.section-title {
  margin: 0;
  font-size: 14px;
  color: #d6dce5;
}

.check-counter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.section-checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.section-checks li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #d6dce5;
  font-size: 13px;
}

.stack {
  display: grid;
  gap: 10px;
}

.workspace {
  min-width: 0;
  padding: 24px;
  display: grid;
  gap: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  color: #667182;
}

.toolbar h2,
.panel h3 {
  margin: 0;
}

.flow-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.flow-step {
  min-width: 0;
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  background: #ffffff;
  border: 1px solid #d8dee6;
  border-radius: 8px;
}

.flow-step span {
  color: #667182;
  font-size: 12px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 20px;
  min-height: 0;
}

.editor,
.rail {
  min-width: 0;
  display: grid;
  gap: 16px;
  align-content: start;
}

.panel {
  background: #ffffff;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  overflow: hidden;
}

.panel__header {
  padding: 16px 18px;
  border-bottom: 1px solid #e7ebf0;
  background: #fbfcfd;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  align-items: start;
  gap: 14px 16px;
  padding: 18px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 14px 16px;
  padding: 0 18px 18px;
}

.checkbox-grid > .field {
  grid-column: auto;
}

.field {
  min-width: 0;
  grid-column: span 3;
  display: grid;
  grid-template-rows: auto minmax(35px, auto) auto auto;
  align-content: start;
  gap: 8px;
}

.field--full {
  grid-column: 1 / -1;
}

.checkbox-list {
  border: 1px solid #d8dee8;
  border-radius: 8px;
  padding: 12px;
}

.check-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 4px 12px 4px 0;
  color: #263241;
  font-size: 13px;
}

.field__label {
  font-size: 13px;
  color: #516072;
  display: flex;
  align-items: center;
  gap: 8px;
}

.field__hint {
  margin: 0;
  color: #6c7788;
  font-size: 12px;
  line-height: 1.45;
  min-height: 35px;
  overflow-wrap: anywhere;
}

.field__hint--empty {
  visibility: hidden;
}

.required-mark {
  color: #7a4b14;
  background: #fff6e9;
  border: 1px solid #ead9bd;
  border-radius: 999px;
  padding: 1px 6px;
  font-size: 11px;
}

.field--checkbox {
  padding: 12px 14px;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  background: #fafbfd;
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  align-items: start;
  gap: 10px;
}

.field--checkbox > span {
  min-width: 0;
  color: #1d2935;
  line-height: 1.4;
  overflow-wrap: break-word;
  white-space: normal;
}

.field--checkbox .field__hint {
  grid-column: 2 / -1;
}

.field--checkbox .field-issues {
  grid-column: 2 / -1;
}

.control {
  width: 100%;
  border: 1px solid #cdd5df;
  border-radius: 8px;
  background: #ffffff;
  color: #18202a;
  padding: 10px 12px;
  font: inherit;
}

.control--compact {
  width: auto;
  min-width: 82px;
  padding: 6px 10px;
}

.config-json-editor {
  min-height: 320px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre;
}

.control:focus {
  outline: 2px solid #8ec5b1;
  outline-offset: 1px;
  border-color: #8ec5b1;
}

.field--error .control {
  border-color: #d08383;
}

.field--warning .control {
  border-color: #d9bd75;
}

.field-issues {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.field-issue {
  font-size: 12px;
  line-height: 1.4;
}

.field-issue--error {
  color: #9a2f2f;
}

.field-issue--warning {
  color: #7a4b14;
}

.checkbox {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #2f7d66;
}

.summary {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 16px 18px 18px;
}

.summary--compact {
  padding: 0;
}

.summary__row {
  min-width: 0;
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.summary dt {
  min-width: 0;
  color: #667182;
}

.summary dd {
  min-width: 0;
  margin: 0;
  text-align: right;
  color: #1d2935;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.sidebar .summary {
  padding: 0;
}

.sidebar .summary__row {
  grid-template-columns: minmax(82px, auto) minmax(0, 1fr);
}

.sidebar .summary dt {
  color: #98a4b5;
}

.sidebar .summary dd {
  color: #f4f6f8;
}

.summary__value--break {
  word-break: break-all;
}

.issue-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.issue-list li {
  padding: 12px;
  border: 1px solid #eed6d6;
  border-radius: 8px;
  background: #fff8f8;
  display: grid;
  gap: 4px;
}

.issue-list li span {
  font-size: 12px;
  color: #6c7788;
}

.issue-list li p {
  margin: 0;
}

.issue-list--warning li {
  border-color: #e8dcba;
  background: #fffaf0;
}

.issue-list li.issue-list__warning {
  border-color: #e8dcba;
  background: #fffaf0;
}

.result-block {
  padding: 16px 18px 18px;
  display: grid;
  gap: 14px;
}

.empty-state {
  margin: 0;
  padding: 16px 18px 18px;
  color: #6c7788;
}

.empty-state--plain {
  padding: 0;
}

.feedback {
  max-width: 420px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.feedback--wide {
  width: 100%;
  max-width: none;
}

.feedback--success {
  background: #eefaf5;
  border: 1px solid #b9e1cf;
  color: #225d4b;
}

.feedback--error {
  background: #fff5f5;
  border: 1px solid #f0c6c6;
  color: #8a3030;
}

.feedback--neutral {
  background: #f6f8fb;
  border: 1px solid #d8dee6;
  color: #445163;
}

.action-bar {
  position: sticky;
  bottom: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #d8dee6;
  border-radius: 8px;
  backdrop-filter: blur(10px);
}

.confirm {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #445163;
}

.gate-message {
  margin: 0;
  color: #667182;
  font-size: 13px;
}

.action-bar__buttons {
  display: flex;
  gap: 10px;
}

.button {
  appearance: none;
  border: 1px solid #2f7d66;
  border-radius: 8px;
  background: #2f7d66;
  color: #ffffff;
  font: inherit;
  padding: 10px 14px;
  cursor: pointer;
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.button--secondary {
  border-color: #cdd5df;
  background: #ffffff;
  color: #21303d;
}

.button--danger {
  border-color: #b54a4a;
  background: #b54a4a;
  color: #ffffff;
}

.button--small {
  padding: 6px 10px;
  font-size: 12px;
}

.tone {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.tone--success {
  background: #e9f8ef;
  color: #1f6748;
}

.tone--error {
  background: #fff0f0;
  color: #9a2f2f;
}

.tone--warning {
  background: #fff6e9;
  color: #8d5a14;
}

.tone--neutral {
  background: #eef2f5;
  color: #516072;
}

@media (max-width: 1200px) {
  .admin-shell,
  .shell {
    grid-template-columns: 1fr;
  }

  .admin-sidebar,
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #303744;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }

  .config-secondary-grid,
  .config-version-strip,
  .summary.document-detail-summary,
  .index-health-metrics,
  .document-version-index-grid {
    grid-template-columns: 1fr;
  }

  .index-ops-composite {
    grid-template-columns: 1fr;
  }

  .index-ops-actions-stack {
    border-top: 1px solid #eef1f5;
    border-left: 0;
    padding-top: 14px;
    padding-left: 0;
  }

  .config-versions {
    padding: 14px;
  }

  .entity-table__row--header {
    display: none;
  }

  .entity-table--departments .entity-table__row,
  .entity-table--users .entity-table__row,
  .entity-table--configs .entity-table__row,
  .entity-table--knowledge .entity-table__row,
  .entity-table--folders .entity-table__row,
  .entity-table--documents .entity-table__row,
  .entity-table--imports .entity-table__row,
  .entity-table--index-jobs .entity-table__row,
  .entity-table--index-health .entity-table__row,
  .entity-table--snapshots .entity-table__row,
  .entity-table--query-logs .entity-table__row,
  .entity-table--model-calls .entity-table__row {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .upload-panel,
  .upload-panel__main {
    grid-template-columns: 1fr;
  }

  .row-actions {
    justify-content: flex-start;
  }

  .pagination-bar {
    align-items: flex-start;
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .flow-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .admin-workspace,
  .workspace {
    padding: 16px;
  }

  .admin-toolbar,
  .toolbar,
  .action-bar {
    display: grid;
    grid-template-columns: 1fr;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .panel__header,
  .panel__actions,
  .list-filter,
  .list-filter--imports,
  .list-filter--documents,
  .list-filter--knowledge,
  .list-filter--diagnostics,
  .list-filter--index-ops,
  .list-filter--index-restore,
  .list-filter--model-calls,
  .index-ops-layout,
  .index-ops-composite,
  .index-ops-row,
  .index-ops-action-row,
  .index-ops-card--restore .index-ops-row,
  .selector-search,
  .modal__header,
  .modal__footer,
  .modal__body--split {
    grid-template-columns: 1fr;
  }

  .index-ops-card--restore {
    grid-column: auto;
  }

  .panel__header,
  .panel__actions,
  .modal__header,
  .modal__footer {
    display: grid;
    justify-items: stretch;
  }

  .list-filter > .button {
    justify-self: stretch;
    width: 100%;
  }

  .pagination-bar,
  .pagination-bar__actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .pagination-bar label,
  .pagination-bar__actions .button {
    width: 100%;
  }

  .control--compact {
    width: 100%;
  }

  .modal-backdrop {
    padding: 12px;
  }

  .modal {
    max-height: calc(100vh - 24px);
  }

  .modal__body--document-details {
    padding-right: 18px;
  }

  .user-menu {
    align-items: stretch;
    display: grid;
  }

  .user-menu > div {
    justify-items: start;
  }

  .flow-strip {
    grid-template-columns: 1fr;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .checkbox-grid {
    grid-template-columns: 1fr;
  }

  .field,
  .field--full {
    grid-column: auto;
  }

  .summary__row {
    grid-template-columns: 1fr;
  }

  .summary dd {
    text-align: left;
  }

  .action-bar__buttons {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
</style>
