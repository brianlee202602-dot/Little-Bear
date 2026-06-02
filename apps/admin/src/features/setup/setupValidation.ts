import type { SetupStateData } from "@/api/setup";
import type { SetupFormModel } from "@/features/setup/setupModel";

export type LocalIssueTone = "error" | "warning";

export type LocalValidationIssue = {
  field?: keyof SetupFormModel;
  section: string;
  tone: LocalIssueTone;
  message: string;
};

type AddIssue = (
  tone: LocalIssueTone,
  section: string,
  message: string,
  field?: keyof SetupFormModel,
) => void;

export function validateLocalForm(
  current: SetupFormModel,
  currentSetupState: SetupStateData | null,
): LocalValidationIssue[] {
  // 本地校验只处理确定性规则；服务连通性、配置契约和权限状态由后端再次校验。
  const issues: LocalValidationIssue[] = [];
  const add: AddIssue = (tone, section, message, field) => {
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
    add(
      "error",
      "首个管理员",
      "登录名只能包含字母、数字、点、下划线或连字符，长度 3 到 64。",
      "adminUsername",
    );
  }
  if (!current.adminDisplayName.trim()) {
    add("error", "首个管理员", "管理员显示名不能为空。", "adminDisplayName");
  }
  if (current.adminPassword.length < current.passwordMinLength) {
    add("error", "首个管理员", "初始密码长度不能小于密码策略。", "adminPassword");
  }
  if (
    !/[A-Z]/.test(current.adminPassword) ||
    !/[a-z]/.test(current.adminPassword) ||
    !/\d/.test(current.adminPassword)
  ) {
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
  validateHttpUrl(
    current.embeddingProviderBaseUrl,
    "向量模型服务地址",
    "embeddingProviderBaseUrl",
    "模型与检索",
    add,
  );
  validateHttpUrl(
    current.rerankProviderBaseUrl,
    "重排模型服务地址",
    "rerankProviderBaseUrl",
    "模型与检索",
    add,
  );
  if (!current.llmProviderBaseUrl.trim()) {
    add("error", "模型与检索", "当前 compose 未创建大模型服务，必须填写真实大模型服务地址。", "llmProviderBaseUrl");
  } else {
    validateHttpUrl(current.llmProviderBaseUrl, "大模型服务地址", "llmProviderBaseUrl", "模型与检索", add);
  }
  if (
    isComposeDemoProvider(current.embeddingProviderBaseUrl) ||
    isComposeDemoProvider(current.rerankProviderBaseUrl)
  ) {
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
  add: AddIssue,
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
  add: AddIssue,
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
  add: AddIssue,
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
  add: AddIssue,
): void {
  if (value.trim()) {
    validateSecretRef(value, label, field, section, add);
  }
}

function validateCollectionPrefix(value: string, add: AddIssue): void {
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value)) {
    add("error", "基础设施", "向量集合前缀必须以字母开头，只能包含字母、数字、下划线或连字符。", "collectionPrefix");
  }
}

function validateNonEmpty(
  value: string,
  label: string,
  field: keyof SetupFormModel,
  section: string,
  add: AddIssue,
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
