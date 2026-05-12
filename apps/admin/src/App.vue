<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiRequestError,
  type ApiErrorPayload,
  type AdminDepartmentData,
  type AdminKnowledgeBaseData,
  type AdminRoleBindingData,
  type AdminRoleData,
  type AdminUserData,
  createAdminDepartment,
  createAdminUser,
  createSession,
  createAdminUserRoleBindings,
  deleteAdminDepartment,
  deleteAdminUser,
  deleteCurrentSession,
  discardConfigDraft,
  getCurrentUser,
  getAdminDepartment,
  getSetupState,
  initializeSetup,
  listAdminDepartments,
  listAdminKnowledgeBases,
  listAdminRoles,
  listAdminUserDepartments,
  listAdminUserRoleBindings,
  listAdminUsers,
  listAuditLogs,
  listConfigVersions,
  listConfigs,
  patchAdminDepartment,
  patchAdminUser,
  publishConfigVersion,
  refreshSession,
  replaceAdminUserDepartments,
  resetAdminUserPassword,
  revokeAdminUserRoleBinding,
  saveConfigDraft,
  unlockAdminUser,
  validateAdminConfig,
  validateSetupConfig,
  type AuditLogData,
  type ConfigItemData,
  type ConfigVersionData,
  type CurrentUserData,
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
type ActiveAdminTab = "config" | "departments" | "users";
type ConfigModalMode = "create" | "edit" | "delete" | null;
type DepartmentModalMode = "create" | "edit" | "delete" | null;
type UserModalMode = "create" | "edit" | "departments" | "roles" | "password" | "delete" | null;
type RoleScopeType = AdminRoleData["scope_type"];
type RoleBindingCandidate = {
  role: AdminRoleData;
  scopeType: RoleScopeType;
  scopeId: string | null;
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
const userEditForm = reactive({
  name: "",
  status: "active" as "active" | "disabled" | "locked",
  confirmedDisableAdmin: false,
});
const departmentDangerForm = reactive({
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
const configDangerForm = reactive({
  confirmedDelete: false,
});
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
const userAdminFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const departmentAdminFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(
  null,
);
const validationErrorPayload = ref<ApiErrorPayload | null>(null);
const initializationErrorPayload = ref<ApiErrorPayload | null>(null);
const submitConfirmed = ref(false);
const lastValidatedPayload = ref<string | null>(null);
const authTokens = ref<AuthTokenState | null>(loadStoredAuthTokens());
const currentUser = ref<CurrentUserData | null>(null);
const configItems = ref<ConfigItemData[]>([]);
const configVersions = ref<ConfigVersionData[]>([]);
const auditLogs = ref<AuditLogData[]>([]);
const selectedConfigKey = ref<string>("");
const configEditorText = ref("");
const configValidationResult = ref<SetupValidationData | null>(null);
const selectedDraftVersion = ref<number | null>(null);
const lastConfigValidatedText = ref<string | null>(null);
const selectedAdminTab = ref<ActiveAdminTab>("config");
const configModalMode = ref<ConfigModalMode>(null);
const adminUsers = ref<AdminUserData[]>([]);
const adminDepartments = ref<AdminDepartmentData[]>([]);
const adminKnowledgeBases = ref<AdminKnowledgeBaseData[]>([]);
const adminRoles = ref<AdminRoleData[]>([]);
const selectedDepartmentId = ref<string>("");
const selectedAdminUserId = ref<string>("");
const selectedUserDepartments = ref<AdminDepartmentData[]>([]);
const selectedUserRoleBindings = ref<AdminRoleBindingData[]>([]);
const departmentModalMode = ref<DepartmentModalMode>(null);
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

const setupFieldByKey = new Map<keyof SetupFormModel, FieldDefinition>(
  sections.flatMap((section) => section.fields.map((field) => [field.key, field] as const)),
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
    fields: setupFields("vectorTopK", "keywordTopK", "rerankInputTopK", "finalContextTopK", "maxContextTokens"),
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
    fields: [],
  },
  {
    key: "permission",
    label: "权限策略",
    description: "默认角色、默认可见性和权限收紧阻断策略。",
    fields: [],
  },
  {
    key: "security",
    label: "安全策略",
    description: "引用强制、Prompt 泄露防护和 PII 脱敏策略。",
    fields: [],
  },
  {
    key: "timeout",
    label: "超时预算",
    description: "查询链路各阶段的超时预算。",
    fields: [],
  },
  {
    key: "degrade",
    label: "降级策略",
    description: "模型、检索、导入等链路异常时的降级动作。",
    fields: [],
  },
  {
    key: "observability",
    label: "可观测性",
    description: "指标、Trace 和关键告警阈值。",
    fields: [],
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
  return "dashboard";
});
const userDisplayName = computed(() => currentUser.value?.name || currentUser.value?.username || "-");
const userRoleLabels = computed(() => formatRoleList(currentUser.value?.roles ?? []));
const canManageConfig = computed(() => hasScope(currentUser.value?.scopes ?? [], "config:manage"));
const canReadConfig = computed(() => hasScope(currentUser.value?.scopes ?? [], "config:read"));
const canReadAudit = computed(() => hasScope(currentUser.value?.scopes ?? [], "audit:read"));
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
  configItems.value.filter((item) => item.status === "draft" || item.status === "validating"),
);
const editableConfigDefinitions = computed(() =>
  configSectionDefinitions.filter((definition) => definition.fields.length > 0),
);
const selectedConfigDefinition = computed(() => configDefinitionForKey(selectedConfigKey.value));
const selectedConfigFields = computed(() => selectedConfigDefinition.value?.fields ?? []);
const selectedAdminUser = computed(
  () => adminUsers.value.find((user) => user.id === selectedAdminUserId.value) ?? null,
);
const selectedDepartment = computed(
  () => adminDepartments.value.find((department) => department.id === selectedDepartmentId.value) ?? null,
);
const selectedUserDepartmentsForDisplay = computed(() => {
  if (selectedUserDepartments.value.length > 0) {
    return selectedUserDepartments.value;
  }
  return selectedAdminUser.value?.departments ?? [];
});
const initialAssignableRoles = computed(() =>
  adminRoles.value.filter((role) => role.status === "active" && role.scope_type === "enterprise"),
);
const assignableRoles = computed(() => adminRoles.value.filter((role) => role.status === "active"));
const activeDepartments = computed(() =>
  adminDepartments.value.filter((department) => department.status === "active"),
);
const activeKnowledgeBases = computed(() =>
  adminKnowledgeBases.value.filter((knowledgeBase) => knowledgeBase.status === "active"),
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
  const departments = selectedUserDepartmentsForDisplay.value;
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
  () => canReadUsers.value || canReadRoles.value || canReadDepartments.value,
);
const canLoadDepartmentAdmin = computed(() => canReadDepartments.value || canManageDepartments.value);
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
  return activeVersion?.version ?? selectedConfigItem.value?.version ?? 1;
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
    Boolean(selectedConfigDefinition.value) &&
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
const canDiscardSelectedDraft = computed(
  () =>
    Boolean(selectedDraftVersion.value) &&
    canManageConfig.value &&
    configDangerForm.confirmedDelete &&
    !configBusy.loading &&
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
    const userResponse = await getCurrentUser(tokenResponse.access_token);
    currentUser.value = userResponse.data;
    await refreshConfigAdminState();
    await refreshUserRoleAdminState();
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
    const userResponse = await getCurrentUser(accessToken);
    currentUser.value = userResponse.data;
    authFeedback.value = null;
    await refreshConfigAdminState();
    await refreshUserRoleAdminState();
  } catch {
    clearAuthSession();
  }
}

async function refreshConfigAdminState(): Promise<void> {
  if (!canReadConfig.value && !canManageConfig.value) {
    configItems.value = [];
    configVersions.value = [];
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.loading = true;
  try {
    const [itemsResponse, versionsResponse] = await Promise.all([
      listConfigs(accessToken),
      listConfigVersions(accessToken),
    ]);
    configItems.value = itemsResponse.data;
    configVersions.value = versionsResponse.data;
    if (canReadAudit.value) {
      try {
        const auditResponse = await listAuditLogs(accessToken, { resource_type: "config" });
        auditLogs.value = auditResponse.data;
        auditFeedback.value = null;
      } catch (error) {
        auditLogs.value = [];
        auditFeedback.value = {
          tone: "error",
          message: normalizeErrorMessage(error, "读取配置审计日志失败"),
        };
      }
    } else {
      auditLogs.value = [];
      auditFeedback.value = null;
    }
    if (!selectedConfigKey.value && configItems.value.length > 0) {
      selectConfigItem(configItems.value.find((item) => item.status === "active") ?? configItems.value[0]);
    } else if (
      selectedConfigKey.value &&
      !configItems.value.some(
        (item) =>
          item.key === selectedConfigKey.value &&
          (!selectedDraftVersion.value || item.version === selectedDraftVersion.value),
      )
    ) {
      const fallback = configItems.value.find((item) => item.status === "active") ?? configItems.value[0];
      if (fallback) {
        selectConfigItem(fallback);
      } else {
        selectedConfigKey.value = "";
        selectedDraftVersion.value = null;
        syncConfigFormFromActiveConfig();
      }
    } else if (selectedConfigKey.value) {
      syncConfigFormFromActiveConfig();
    }
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

async function refreshUserRoleAdminState(): Promise<void> {
  if (!canLoadUserAdmin.value) {
    adminUsers.value = [];
    adminDepartments.value = [];
    adminKnowledgeBases.value = [];
    adminRoles.value = [];
    selectedAdminUserId.value = "";
    selectedUserDepartments.value = [];
    selectedUserRoleBindings.value = [];
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  userAdminBusy.loading = true;
  try {
    if (canReadRoles.value) {
      const rolesResponse = await listAdminRoles(accessToken);
      adminRoles.value = rolesResponse.data;
      if (!roleBindingForm.roleId && assignableRoles.value.length > 0) {
        roleBindingForm.roleId = assignableRoles.value[0].id;
      }
      syncRoleBindingScopeDefault();
    } else {
      adminRoles.value = [];
    }
    if (canReadDepartments.value) {
      const departmentsResponse = await listAdminDepartments(accessToken, { status: "active" });
      adminDepartments.value = departmentsResponse.data;
      ensureDefaultCreateDepartmentSelection();
      syncRoleBindingScopeDefault();
    } else {
      adminDepartments.value = [];
      userCreateForm.departmentIds = [];
    }
    if (canManageKnowledgeBases.value) {
      const knowledgeBasesResponse = await listAdminKnowledgeBases(accessToken, { status: "active" });
      adminKnowledgeBases.value = knowledgeBasesResponse.data;
      syncRoleBindingScopeDefault();
    } else {
      adminKnowledgeBases.value = [];
    }
    if (canReadUsers.value) {
      const usersResponse = await listAdminUsers(accessToken, {
        keyword: userSearchForm.keyword.trim() || undefined,
        status: userSearchForm.status || undefined,
      });
      adminUsers.value = usersResponse.data;
      if (
        !selectedAdminUserId.value ||
        !adminUsers.value.some((user) => user.id === selectedAdminUserId.value)
      ) {
        selectedAdminUserId.value = adminUsers.value[0]?.id ?? "";
      }
    } else {
      adminUsers.value = [];
      selectedAdminUserId.value = "";
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
    });
    adminDepartments.value = response.data;
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

async function refreshSelectedUserRoleBindings(existingAccessToken?: string): Promise<void> {
  if (!selectedAdminUserId.value || !canReadRoles.value) {
    selectedUserRoleBindings.value = [];
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminUserRoleBindings(selectedAdminUserId.value, accessToken);
  selectedUserRoleBindings.value = response.data;
  syncRoleBindingScopeDefault();
}

async function refreshSelectedUserDepartments(existingAccessToken?: string): Promise<void> {
  if (!selectedAdminUserId.value) {
    selectedUserDepartments.value = [];
    syncSelectedUserDepartmentForm();
    return;
  }
  if (!canReadDepartments.value) {
    selectedUserDepartments.value = selectedAdminUser.value?.departments ?? [];
    syncSelectedUserDepartmentForm();
    return;
  }
  const accessToken = existingAccessToken ?? (await ensureAccessToken());
  if (!accessToken) {
    return;
  }
  const response = await listAdminUserDepartments(selectedAdminUserId.value, accessToken);
  selectedUserDepartments.value = response.data;
  updateSelectedAdminUserDepartments(response.data);
  syncSelectedUserDepartmentForm();
}

async function selectAdminUser(userId: string): Promise<void> {
  selectedAdminUserId.value = userId;
  userDangerForm.confirmedDelete = false;
  passwordResetForm.newPassword = "";
  passwordResetForm.passwordConfirm = "";
  passwordResetForm.confirmed = false;
  userDepartmentForm.confirmedReplacePrimary = false;
  selectedUserDepartments.value = selectedAdminUser.value?.departments ?? [];
  syncSelectedUserDepartmentForm();
  roleBindingForm.confirmedRemoveAdmin = false;
  try {
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

function switchAdminTab(tab: ActiveAdminTab): void {
  selectedAdminTab.value = tab;
  if (tab === "departments") {
    void refreshDepartmentAdminState();
  } else if (tab === "users") {
    void refreshUserRoleAdminState();
  } else if (tab === "config") {
    void refreshConfigAdminState();
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

function ensureDefaultCreateDepartmentSelection(): void {
  const availableIds = new Set(activeDepartments.value.map((department) => department.id));
  userCreateForm.departmentIds = userCreateForm.departmentIds.filter((id) => availableIds.has(id));
  if (userCreateForm.departmentIds.length > 0) {
    return;
  }
  const defaultDepartment =
    activeDepartments.value.find((department) => department.is_default) ?? activeDepartments.value[0];
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

async function openEditDepartmentModal(department: AdminDepartmentData): Promise<void> {
  departmentModalMode.value = "edit";
  await selectDepartment(department.id);
}

async function openDeleteDepartmentModal(department: AdminDepartmentData): Promise<void> {
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
  userAdminFeedback.value = null;
  userModalMode.value = "create";
}

async function openEditUserModal(user: AdminUserData): Promise<void> {
  userModalMode.value = "edit";
  await selectAdminUser(user.id);
  syncUserEditForm();
}

async function openUserDepartmentsModal(user: AdminUserData): Promise<void> {
  userModalMode.value = "departments";
  await selectAdminUser(user.id);
}

async function openUserRolesModal(user: AdminUserData): Promise<void> {
  userModalMode.value = "roles";
  await selectAdminUser(user.id);
  if (!roleBindingForm.roleId && assignableRoles.value.length > 0) {
    roleBindingForm.roleId = assignableRoles.value[0].id;
  }
  if (!roleBindingForm.roleId || selectedUserRoleBindingKeys.value.has(selectedRoleBindingKey.value)) {
    selectNextAvailableRoleBindingTarget();
  } else {
    syncRoleBindingScopeDefault();
  }
}

async function openPasswordResetModal(user: AdminUserData): Promise<void> {
  userModalMode.value = "password";
  await selectAdminUser(user.id);
}

async function openDeleteUserModal(user: AdminUserData): Promise<void> {
  userDangerForm.confirmedDelete = false;
  userModalMode.value = "delete";
  await selectAdminUser(user.id);
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
  roleBindingForm.scopeId = candidate.scopeId ?? "";
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
  if (index >= 0) {
    adminDepartments.value[index] = department;
    return;
  }
  adminDepartments.value = [department, ...adminDepartments.value];
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
    updateSelectedAdminUserDepartments(response.data);
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
  userDepartmentForm.departmentIds = selectedUserDepartmentsForDisplay.value.map(
    (department) => department.id,
  );
  userDepartmentForm.confirmedReplacePrimary = false;
}

function updateSelectedAdminUserDepartments(departments: AdminDepartmentData[]): void {
  const index = adminUsers.value.findIndex((user) => user.id === selectedAdminUserId.value);
  if (index < 0) {
    return;
  }
  adminUsers.value[index] = {
    ...adminUsers.value[index],
    departments,
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

function openCreateConfigModal(): void {
  const fallback =
    editableConfigDefinitions.value.find((definition) =>
      activeConfigItems.value.some((item) => item.key === definition.key),
    ) ?? editableConfigDefinitions.value[0];
  if (!fallback) {
    configFeedback.value = {
      tone: "error",
      message: "当前没有可编辑的配置项。",
    };
    return;
  }
  selectedConfigKey.value = fallback.key;
  selectedDraftVersion.value = null;
  syncConfigFormFromActiveConfig();
  resetConfigModalState();
  configModalMode.value = "create";
}

function openEditConfigModal(item: ConfigItemData): void {
  selectConfigItem(item);
  resetConfigModalState();
  configModalMode.value = "edit";
}

function openDeleteConfigModal(item: ConfigItemData): void {
  selectConfigItem(item);
  resetConfigModalState();
  configDangerForm.confirmedDelete = false;
  configModalMode.value = "delete";
}

function closeConfigModal(): void {
  configModalMode.value = null;
  configDangerForm.confirmedDelete = false;
}

function configModalTitle(): string {
  if (configModalMode.value === "create") {
    return "新增配置草稿";
  }
  if (configModalMode.value === "edit") {
    return "编辑配置项";
  }
  return "删除配置草稿";
}

function resetConfigModalState(): void {
  configFeedback.value = null;
  configValidationResult.value = null;
  lastConfigValidatedText.value = null;
  configDangerForm.confirmedDelete = false;
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
  if (configModalMode.value === "edit" || configModalMode.value === "create") {
    selectedDraftVersion.value =
      selectedConfigItem.value?.status === "draft" || selectedConfigItem.value?.status === "validating"
        ? selectedConfigItem.value.version
        : selectedDraftVersion.value;
  }
  configEditorText.value = configFormSignature();
}

async function validateSelectedConfig(): Promise<void> {
  const configBundle = buildEditedActiveConfigBundle();
  if (!configBundle) {
    configFeedback.value = {
      tone: "error",
      message: configEditorParseError.value ?? "请选择需要校验的配置分组。",
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
  const valueJson = buildSelectedConfigSectionValue();
  const definition = selectedConfigDefinition.value;
  if (!definition || !valueJson) {
    configFeedback.value = {
      tone: "error",
      message: configEditorParseError.value ?? "请选择需要保存的配置分组。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.saving = true;
  try {
    const response = await saveConfigDraft(definition.key, valueJson, accessToken);
    selectedDraftVersion.value =
      response.data.status === "draft" ? response.data.version : selectedDraftVersion.value;
    configFeedback.value = {
      tone: "success",
      message:
        response.data.status === "draft"
          ? `已保存配置草稿 v${response.data.version}。`
          : "配置内容与当前生效版本一致。",
    };
    await refreshConfigAdminState();
    selectConfigItem(response.data);
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

  const currentKey = selectedConfigKey.value;
  configBusy.publishing = true;
  try {
    const response = await publishConfigVersion(targetVersion, accessToken);
    selectedDraftVersion.value = null;
    configValidationResult.value = null;
    lastConfigValidatedText.value = null;
    configFeedback.value = {
      tone: "success",
      message: `已发布 active_config v${response.data.version}。`,
    };
    await refreshConfigAdminState();
    if (currentKey && configItems.value.some((item) => item.key === currentKey)) {
      selectConfigItem(currentKey);
    }
    closeConfigModal();
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "发布配置版本失败"),
    };
  } finally {
    configBusy.publishing = false;
  }
}

async function discardSelectedDraft(): Promise<void> {
  const targetVersion = selectedDraftVersion.value;
  if (!targetVersion || !configDangerForm.confirmedDelete) {
    configFeedback.value = {
      tone: "error",
      message: "删除草稿前必须勾选确认项。",
    };
    return;
  }
  const accessToken = await ensureAccessToken();
  if (!accessToken) {
    return;
  }

  configBusy.deleting = true;
  try {
    await discardConfigDraft(targetVersion, accessToken);
    selectedDraftVersion.value = null;
    configDangerForm.confirmedDelete = false;
    configFeedback.value = {
      tone: "success",
      message: `已删除配置草稿 v${targetVersion}。`,
    };
    await refreshConfigAdminState();
    closeConfigModal();
  } catch (error) {
    configFeedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "删除配置草稿失败"),
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
  configItems.value = [];
  configVersions.value = [];
  auditLogs.value = [];
  adminUsers.value = [];
  adminDepartments.value = [];
  adminKnowledgeBases.value = [];
  adminRoles.value = [];
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

function formatDepartmentLabel(
  department: { code?: string | null; name?: string | null } | null | undefined,
): string {
  if (!department) {
    return "-";
  }
  const name = department.name?.trim();
  const code = department.code?.trim();
  if (name && code) {
    return `${name}（${code}）`;
  }
  return name || code || "-";
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
  return knowledgeBase?.name?.trim() || knowledgeBase?.id?.trim() || "-";
}

function formatRoleBindingScope(binding: AdminRoleBindingData): string {
  if (binding.scope_type === "enterprise") {
    return "全企业";
  }
  if (binding.scope_type === "department") {
    const department = adminDepartments.value.find((item) => item.id === binding.scope_id);
    return `部门：${formatDepartmentLabel(department ?? { code: binding.scope_id, name: "" })}`;
  }
  const knowledgeBase = adminKnowledgeBases.value.find((item) => item.id === binding.scope_id);
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

function isHighRiskAdminRole(role: AdminRoleData): boolean {
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
  configEditorText.value = configFormSignature();
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
}

function buildCurrentConfigBundle(preferredItem: ConfigItemData | null = null): Record<string, unknown> {
  const config: Record<string, unknown> = {
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
  const valueJson = buildSelectedConfigSectionValue();
  const definition = selectedConfigDefinition.value;
  if (!definition || !valueJson) {
    return null;
  }
  const config = buildCurrentConfigBundle();
  config.config_version = newestConfigVersion.value + 1;
  config[definition.key] = valueJson;
  return config;
}

function buildSelectedConfigSectionValue(): Record<string, unknown> | null {
  const key = selectedConfigDefinition.value?.key;
  if (!key) {
    return null;
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
  const formProviders = asRecord(formValue.providers);
  const providers = asRecord(merged.providers);
  for (const key of ["embedding", "rerank", "llm"]) {
    const provider = asRecord(providers?.[key]);
    const formProvider = asRecord(formProviders?.[key]);
    if (provider && formProvider) {
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
  const definition = selectedConfigDefinition.value;
  if (!definition) {
    return "请选择需要编辑的配置项。";
  }
  if (definition.fields.length === 0) {
    return "该配置项暂未提供结构化表单，请通过初始化配置契约扩展后再编辑。";
  }
  const value = buildSelectedConfigSectionValue();
  if (!value) {
    return "配置项内容不能为空。";
  }
  const localIssues = validateLocalForm(configForm, null);
  const fieldKeys = new Set(definition.fields.map((field) => field.key));
  const blockingIssue = localIssues.find(
    (issue) => issue.tone === "error" && issue.field && fieldKeys.has(issue.field),
  );
  return blockingIssue?.message ?? null;
}

function configFormSignature(): string {
  const value = buildSelectedConfigSectionValue();
  return JSON.stringify(
    {
      key: selectedConfigDefinition.value?.key ?? "",
      value,
    },
    null,
    2,
  );
}

function configValuePreview(value: Record<string, unknown>): string {
  const entries = Object.entries(value)
    .filter(([, entryValue]) => typeof entryValue !== "object" || entryValue === null)
    .slice(0, 3)
    .map(([key, entryValue]) => `${key}: ${String(entryValue)}`);
  return entries.join(" / ") || `${Object.keys(value).length} 个子项`;
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

function auditSummaryPreview(log: AuditLogData): string {
  const summary = log.summary_json;
  const version = log.config_version ? `v${log.config_version}` : "";
  const hash = typeof summary.config_hash === "string" ? summary.config_hash.slice(0, 10) : "";
  const previous =
    typeof summary.previous_active_version === "number"
      ? `from v${summary.previous_active_version}`
      : "";
  return [version, previous, hash].filter(Boolean).join(" / ") || "-";
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
          :class="['admin-nav__item', { 'admin-nav__item--active': selectedAdminTab === 'config' }]"
          type="button"
          @click="switchAdminTab('config')"
        >
          配置管理
        </button>
        <button
          :class="['admin-nav__item', { 'admin-nav__item--active': selectedAdminTab === 'departments' }]"
          type="button"
          @click="switchAdminTab('departments')"
        >
          部门管理
        </button>
        <button
          :class="['admin-nav__item', { 'admin-nav__item--active': selectedAdminTab === 'users' }]"
          type="button"
          @click="switchAdminTab('users')"
        >
          用户管理
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
        <section v-if="selectedAdminTab === 'config'" class="panel">
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
              <dd>{{ currentUser.status }}</dd>
            </div>
            <div class="summary__row">
              <dt>角色</dt>
              <dd>{{ userRoleLabels }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="selectedAdminTab === 'departments'" class="panel panel--wide">
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

            <form class="list-filter" @submit.prevent="refreshDepartmentAdminState">
              <label class="field">
                <span class="field__label">关键词</span>
                <p class="field__hint">按部门编码或部门名称过滤。</p>
                <input v-model.trim="departmentSearchForm.keyword" class="control" type="text" />
              </label>
              <label class="field">
                <span class="field__label">部门状态</span>
                <p class="field__hint">留空时显示全部未删除部门。</p>
                <select v-model="departmentSearchForm.status" class="control">
                  <option value="">全部</option>
                  <option value="active">active</option>
                  <option value="disabled">disabled</option>
                </select>
              </label>
              <button class="button button--secondary" type="submit" :disabled="departmentAdminBusy.loading">
                查询
              </button>
            </form>

            <div v-if="adminDepartments.length" class="entity-table entity-table--departments">
              <div class="entity-table__row entity-table__row--header">
                <span>部门</span>
                <span>编码</span>
                <span>状态</span>
                <span>默认部门</span>
                <span>操作</span>
              </div>
              <article v-for="department in adminDepartments" :key="department.id" class="entity-table__row">
                <div class="entity-main">
                  <strong>{{ department.name }}</strong>
                  <span>{{ department.is_default ? "默认组织部门" : "普通部门" }}</span>
                </div>
                <div class="entity-cell">{{ department.code }}</div>
                <div class="entity-cell">
                  <span :class="toneClass(department.status === 'active' ? 'success' : 'neutral')">
                    {{ department.status }}
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
          </div>
        </section>

        <section v-if="selectedAdminTab === 'users'" class="panel panel--wide">
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

            <form class="list-filter" @submit.prevent="refreshUserRoleAdminState">
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
                  <option value="active">active</option>
                  <option value="disabled">disabled</option>
                  <option value="locked">locked</option>
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
                    {{ user.status }}
                  </span>
                </div>
                <div class="badge-list">
                  <span v-for="department in user.departments" :key="department.id" class="badge">
                    {{ formatDepartmentLabel(department) }}
                  </span>
                  <span v-if="!user.departments.length" class="empty-inline">-</span>
                </div>
                <div class="badge-list">
                  <span v-for="role in user.roles" :key="role.id" class="badge">
                    {{ formatRoleLabel(role) }}
                  </span>
                  <span v-if="!user.roles.length" class="empty-inline">-</span>
                </div>
                <div class="row-actions row-actions--dense">
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
          </div>
        </section>

        <section v-if="selectedAdminTab === 'config'" class="panel panel--wide">
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
                新增配置
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
                <span>配置项</span>
                <strong>{{ activeConfigItems.length }}</strong>
              </article>
              <article class="config-version-card">
                <span>待发布草稿</span>
                <strong>{{ configDraftItems.length }}</strong>
              </article>
            </section>

            <div v-if="configItems.length" class="entity-table entity-table--configs">
              <div class="entity-table__row entity-table__row--header">
                <span>配置项</span>
                <span>版本</span>
                <span>状态</span>
                <span>内容摘要</span>
                <span>操作</span>
              </div>
              <article
                v-for="item in configItems"
                :key="`${item.key}-${item.version}-${item.status}`"
                class="entity-table__row"
              >
                <div class="entity-main">
                  <strong>{{ configSectionLabel(item.key) }}</strong>
                  <span>{{ item.key }} · {{ configSectionDescription(item.key) }}</span>
                </div>
                <div class="entity-cell">v{{ item.version }}</div>
                <div class="entity-cell">
                  <span :class="toneClass(configStatusTone(item.status))">{{ item.status }}</span>
                </div>
                <div class="entity-cell">{{ configValuePreview(item.value_json) }}</div>
                <div class="row-actions">
                  <button
                    class="button button--secondary button--small"
                    type="button"
                    @click="openEditConfigModal(item)"
                    :disabled="!canManageConfig || !configDefinitionForKey(item.key)?.fields.length"
                  >
                    编辑
                  </button>
                  <button
                    v-if="item.status === 'draft' || item.status === 'validating'"
                    class="button button--secondary button--small"
                    type="button"
                    @click="publishDraftVersion(item.version)"
                    :disabled="!canManageConfig || configBusy.publishing"
                  >
                    发布
                  </button>
                  <button
                    class="button button--danger button--small"
                    type="button"
                    @click="openDeleteConfigModal(item)"
                    :disabled="!canManageConfig || item.status === 'active'"
                  >
                    删除
                  </button>
                </div>
              </article>
            </div>
            <p v-else class="empty-state empty-state--plain">当前尚未读取到配置项。</p>

            <section class="config-secondary-grid">
              <div class="config-versions" aria-label="配置版本">
                <h4 class="config-versions__title">配置版本</h4>
                <div v-if="configVersions.length" class="version-list">
                  <div v-for="version in configVersions" :key="version.version" class="version-row">
                    <div>
                      <strong>v{{ version.version }}</strong>
                      <span>{{ version.status }} / {{ version.risk_level }}</span>
                    </div>
                    <button
                      v-if="version.status === 'draft' || version.status === 'validating'"
                      class="button button--secondary button--small"
                      type="button"
                      @click="publishDraftVersion(version.version)"
                      :disabled="!canManageConfig || configBusy.publishing"
                    >
                      发布
                    </button>
                  </div>
                </div>
                <p v-else class="empty-state">当前尚未读取到配置版本。</p>
              </div>

              <div class="config-versions" aria-label="配置审计">
                <h4 class="config-versions__title">配置审计</h4>
                <p v-if="auditFeedback" :class="toneClass(auditFeedback.tone)">
                  {{ auditFeedback.message }}
                </p>
                <div v-if="auditLogs.length" class="audit-list">
                  <article v-for="log in auditLogs" :key="log.id" class="audit-row">
                    <header>
                      <strong>{{ log.event_name }}</strong>
                      <span :class="toneClass(log.result === 'success' ? 'success' : 'error')">
                        {{ log.result }}
                      </span>
                    </header>
                    <p>{{ formatAuditTime(log.created_at) }}</p>
                    <p>{{ auditSummaryPreview(log) }}</p>
                    <p v-if="log.error_code" class="audit-row__error">{{ log.error_code }}</p>
                  </article>
                </div>
                <p v-else-if="canReadAudit" class="empty-state">当前尚未读取到配置审计记录。</p>
                <p v-else class="empty-state">当前账号缺少审计读取权限。</p>
              </div>
            </section>
          </div>
        </section>
      </section>

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
              <label class="field field--full modal-field">
                <span class="field__label">配置项</span>
                <p class="field__hint">新增会从当前 active_config 复制基线并生成新的草稿版本。</p>
                <select
                  class="control"
                  :value="selectedConfigKey"
                  :disabled="configModalMode === 'edit'"
                  @change="onConfigKeyChange(($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="definition in editableConfigDefinitions" :key="definition.key" :value="definition.key">
                    {{ definition.label }} / {{ definition.key }}
                  </option>
                </select>
              </label>
              <dl v-if="selectedConfigDefinition" class="summary summary--compact modal-summary">
                <div class="summary__row">
                  <dt>当前 active 版本</dt>
                  <dd>v{{ activeConfigVersion }}</dd>
                </div>
                <div class="summary__row">
                  <dt>配置说明</dt>
                  <dd>{{ selectedConfigDefinition.description }}</dd>
                </div>
              </dl>
              <div class="form-grid form-grid--compact form-grid--modal">
                <label
                  v-for="field in selectedConfigFields"
                  :key="String(field.key)"
                  class="field"
                  :class="{ 'field--full': field.span === 'full', 'field--checkbox': field.input === 'checkbox' }"
                >
                  <template v-if="field.input === 'checkbox'">
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
                      :value="String(configForm[field.key])"
                      @change="updateConfigFieldFromSelect(field, ($event.target as HTMLSelectElement).value)"
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
                      :value="String(configForm[field.key] ?? '')"
                      @input="updateConfigFieldFromInput(field, ($event.target as HTMLInputElement).value)"
                    />
                  </template>
                </label>
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
                  {{ configBusy.saving ? "保存中..." : "保存草稿" }}
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
                {{ configBusy.saving ? "保存中..." : "保存草稿" }}
              </button>
            </footer>
          </form>

          <div v-else-if="configModalMode === 'delete' && selectedConfigItem">
            <div class="modal__body">
              <div class="danger-panel">
                <h4>确认删除配置草稿</h4>
                <p>
                  将删除 {{ configSectionLabel(selectedConfigItem.key) }} 的草稿版本 v{{ selectedConfigItem.version }}。active 配置不会被删除。
                </p>
                <label class="confirm confirm--inline">
                  <input v-model="configDangerForm.confirmedDelete" type="checkbox" />
                  <span>确认删除该配置草稿</span>
                </label>
              </div>
              <div v-if="configFeedback" :class="['feedback feedback--wide', `feedback--${configFeedback.tone}`]">
                {{ configFeedback.message }}
              </div>
            </div>
            <footer class="modal__footer">
              <button class="button button--secondary" type="button" @click="closeConfigModal">
                取消
              </button>
              <button
                class="button button--danger"
                type="button"
                @click="discardSelectedDraft"
                :disabled="!canDiscardSelectedDraft"
              >
                {{ configBusy.deleting ? "删除中..." : "删除草稿" }}
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
                  <dt>部门编码</dt>
                  <dd>{{ selectedDepartment.code }}</dd>
                </div>
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
                    <option value="active">active</option>
                    <option value="disabled">disabled</option>
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
                  <div class="option-picker__grid">
                    <label v-for="department in activeDepartments" :key="department.id" class="option-card">
                      <input
                        type="checkbox"
                        :checked="userCreateForm.departmentIds.includes(department.id)"
                        @change="toggleCreateDepartment(department.id, ($event.target as HTMLInputElement).checked)"
                      />
                      <span>{{ formatDepartmentLabel(department) }}</span>
                    </label>
                  </div>
                  <p v-if="!activeDepartments.length" class="empty-state empty-state--plain">请先创建可用部门。</p>
                </div>
                <div class="role-picker">
                  <span class="field__label">初始角色</span>
                  <p class="field__hint">未选择时后端会尝试授予普通员工默认角色。</p>
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
                <label class="confirm confirm--inline modal-confirm">
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
                  <p class="field__hint">disabled 会吊销用户会话；locked 状态通常由登录失败策略触发。</p>
                  <select v-model="userEditForm.status" class="control">
                    <option value="active">active</option>
                    <option value="disabled">disabled</option>
                    <option value="locked">locked</option>
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
              <div v-if="userAdminFeedback" :class="['feedback feedback--wide', `feedback--${userAdminFeedback.tone}`]">
                {{ userAdminFeedback.message }}
              </div>
              <div class="option-picker">
                <span class="field__label">调整归属部门</span>
                <p class="field__hint">至少选择一个部门；保存时第一个被选中的部门会作为主部门。</p>
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
                <p v-if="!activeDepartments.length" class="empty-state empty-state--plain">当前没有可用的 active 部门。</p>
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
              </section>

              <section class="modal-pane">
                <h4>授予角色</h4>
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
                      {{ formatRoleLabel(role) }} / {{ role.scope_type }}
                    </option>
                  </select>
                </label>
                <label
                  v-if="selectedRoleBindingScopeType === 'department'"
                  class="field field--full modal-field"
                >
                  <span class="field__label">部门作用域</span>
                  <p class="field__hint">该用户只会在选定部门范围内获得部门管理员权限。</p>
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
                  <dd>{{ selectedAdminUser.status }}</dd>
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

.list-filter {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(180px, 240px) auto;
  gap: 14px;
  align-items: end;
}

.list-filter .field {
  grid-column: auto;
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
  grid-template-columns: minmax(220px, 1.6fr) minmax(130px, 0.9fr) minmax(110px, 0.7fr) minmax(90px, 0.6fr) minmax(140px, 0.8fr);
}

.entity-table--users .entity-table__row {
  grid-template-columns: minmax(180px, 1.1fr) minmax(105px, 0.55fr) minmax(190px, 1.25fr) minmax(190px, 1.2fr) minmax(240px, 1.35fr);
}

.entity-table--configs .entity-table__row {
  grid-template-columns: minmax(220px, 1.3fr) minmax(90px, 0.45fr) minmax(110px, 0.5fr) minmax(220px, 1.2fr) minmax(210px, 1fr);
}

.entity-table__row--header {
  border-color: transparent;
  background: #eef2f5;
  color: #516072;
  font-size: 12px;
  font-weight: 700;
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
  .config-version-strip {
    grid-template-columns: 1fr;
  }

  .config-versions {
    padding: 14px;
  }

  .entity-table__row--header {
    display: none;
  }

  .entity-table--departments .entity-table__row,
  .entity-table--users .entity-table__row,
  .entity-table--configs .entity-table__row {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .row-actions {
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
  .modal__header,
  .modal__footer,
  .modal__body--split {
    grid-template-columns: 1fr;
  }

  .panel__header,
  .panel__actions,
  .modal__header,
  .modal__footer {
    display: grid;
    justify-items: stretch;
  }

  .modal-backdrop {
    padding: 12px;
  }

  .modal {
    max-height: calc(100vh - 24px);
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
