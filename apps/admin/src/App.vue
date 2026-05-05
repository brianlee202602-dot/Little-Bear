<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  ApiRequestError,
  getSetupState,
  initializeSetup,
  validateSetupConfig,
  type SetupInitializationData,
  type SetupIssue,
  type SetupStateData,
  type SetupValidationData,
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

type LocalValidationIssue = {
  field?: keyof SetupFormModel;
  section: string;
  tone: LocalIssueTone;
  message: string;
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
  options?: FieldOption[];
  required?: boolean;
};

type FieldSection = {
  title: string;
  fields: FieldDefinition[];
};

const form = reactive<SetupFormModel>(createDefaultSetupForm());

const busy = reactive({
  refreshing: false,
  validating: false,
  submitting: false,
});

const setupState = ref<SetupStateData | null>(null);
const validationResult = ref<SetupValidationData | null>(null);
const initializationResult = ref<SetupInitializationData | null>(null);
const feedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
const submitConfirmed = ref(false);
const lastValidatedPayload = ref<string | null>(null);

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
    { key: "collectionPrefix", label: "向量集合前缀", input: "text", hint: "用于生成和识别 Qdrant collection；变更前需评估既有索引兼容性。", required: true },
    {
      key: "vectorDistance",
      label: "向量距离",
      input: "select",
      required: true,
      options: [
        { label: "cosine", value: "cosine" },
        { label: "dot", value: "dot" },
        { label: "euclid", value: "euclid" },
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
      key: "rerankProviderBaseUrl",
      label: "重排模型服务地址",
      input: "text",
      hint: "Rerank provider 的基础 URL；同一 Docker 网络可使用 http://tei-rerank:80，生产环境应指向正式模型服务。",
      span: "full",
      required: true,
    },
    {
      key: "llmProviderBaseUrl",
      label: "大模型服务地址",
      input: "text",
      hint: "OpenAI-compatible LLM provider 的基础 URL；当前部署未内置 LLM 服务，必须填写可访问的正式地址。",
      span: "full",
      required: true,
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
    },
    {
      key: "chunkPreserveCodeBlocks",
      label: "保留代码块结构",
      input: "checkbox",
      hint: "启用后切片器应尽量避免拆散同一个代码块，减少技术文档上下文破碎。",
    },
    {
      key: "chunkPreserveContractClauses",
      label: "保留合同条款结构",
      input: "checkbox",
      hint: "启用后切片器应尽量保留条款编号和条款正文的完整性。",
      span: "full",
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
    { key: "queryEmbeddingEnabled", label: "查询向量缓存", input: "checkbox", hint: "启用后可复用相同查询的 embedding 结果，降低重复模型调用成本。" },
    { key: "retrievalResultEnabled", label: "召回结果缓存", input: "checkbox", hint: "启用后缓存检索召回结果；缓存键必须包含权限、配置和索引版本信息。" },
    { key: "finalAnswerEnabled", label: "最终答案缓存", input: "checkbox", hint: "启用后缓存最终答案；涉及权限变更和引用时效时需严格评估风险。" },
    { key: "crossUserFinalAnswerAllowed", label: "允许跨用户最终答案缓存", input: "checkbox", hint: "高风险配置，可能导致不同用户之间复用答案；P0 阶段禁止开启。", span: "full" },
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

const payload = computed(() => buildSetupPayload(form));
const payloadSignature = computed(() => JSON.stringify(payload.value));
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
const setupWritable = computed(
  () => !(setupState.value?.initialized ?? false) || setupState.value?.recovery_setup_allowed === true,
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

onMounted(async () => {
  if (window.location.pathname === "/admin" || window.location.pathname === "/admin/") {
    window.history.replaceState(null, "", "/admin/setup-initialization");
  }
  await refreshState();
});

async function refreshState(): Promise<void> {
  busy.refreshing = true;
  try {
    const response = await getSetupState(form.setupToken || undefined);
    setupState.value = response.data;
    feedback.value = null;
  } catch (error) {
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "读取 setup 状态失败"),
    };
  } finally {
    busy.refreshing = false;
  }
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
    lastValidatedPayload.value = response.data.valid ? payloadSignature.value : null;
    feedback.value = {
      tone: response.data.valid ? "success" : "error",
      message: response.data.valid ? "配置校验通过" : "配置校验未通过",
    };
    await refreshState();
  } catch (error) {
    validationResult.value = null;
    lastValidatedPayload.value = null;
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
    const response = await initializeSetup(payload.value, form.setupToken || undefined);
    initializationResult.value = response.data;
    feedback.value = {
      tone: "success",
      message: "初始化提交成功",
    };
    submitConfirmed.value = false;
    await refreshState();
  } catch (error) {
    initializationResult.value = null;
    feedback.value = {
      tone: "error",
      message: normalizeErrorMessage(error, "初始化提交失败"),
    };
  } finally {
    busy.submitting = false;
  }
}

function resetForm(): void {
  Object.assign(form, createDefaultSetupForm());
  validationResult.value = null;
  lastValidatedPayload.value = null;
  initializationResult.value = null;
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

function toneClass(tone: Tone): string {
  return `tone tone--${tone}`;
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

function validateLocalForm(
  current: SetupFormModel,
  currentSetupState: SetupStateData | null,
): LocalValidationIssue[] {
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
  <main class="shell">
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
                v-for="field in section.fields"
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
                <p v-if="field.hint" class="field__hint">{{ field.hint }}</p>
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  padding: 18px;
}

.field {
  min-width: 0;
  display: grid;
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

.feedback {
  max-width: 420px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
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
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #303744;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }

  .flow-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .workspace {
    padding: 16px;
  }

  .toolbar,
  .action-bar {
    display: grid;
    grid-template-columns: 1fr;
  }

  .flow-strip {
    grid-template-columns: 1fr;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

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
