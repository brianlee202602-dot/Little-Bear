import { setupFields, type FieldDefinition } from "@/features/setup/setupFields";

export type ConfigSectionFormDefinition = {
  key: string;
  label: string;
  description: string;
  fields: FieldDefinition[];
};

export const configSectionDefinitions: ConfigSectionFormDefinition[] = [
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
export function configDefinitionForKey(key: string): ConfigSectionFormDefinition | null {
  return configSectionDefinitions.find((definition) => definition.key === key) ?? null;
}

export function configEditableFields(): FieldDefinition[] {
  return configSectionDefinitions.flatMap((definition) => definition.fields);
}

export function configNormalFields(definition: ConfigSectionFormDefinition): FieldDefinition[] {
  return definition.fields.filter((field) => field.input !== "checkbox");
}

export function configCheckboxFields(definition: ConfigSectionFormDefinition): FieldDefinition[] {
  return definition.fields.filter((field) => field.input === "checkbox");
}
