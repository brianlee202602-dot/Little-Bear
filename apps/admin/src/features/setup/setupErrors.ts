import type { ApiErrorPayload } from "@/api/http";
import type { SetupIssue } from "@/api/setup";

export type BootstrapCheckIssue = {
  name: string;
  status: string;
  message: string;
  required: boolean;
  latency_ms?: number;
};

export type DatabaseErrorIssue = {
  type?: string;
  driver_type?: string;
  message?: string;
  sqlstate?: string;
  constraint?: string;
  table?: string;
  column?: string;
};

const BOOTSTRAP_CHECK_LABELS: Record<string, string> = {
  active_config: "active config",
  active_config_schema: "配置 Schema",
  keyword_search: "PostgreSQL 关键词检索",
  migration: "数据库迁移",
  minio: "MinIO",
  model_provider_embedding: "Embedding provider",
  model_provider_embedding_auth: "Embedding provider secret",
  model_provider_llm: "LLM provider",
  model_provider_llm_auth: "LLM provider secret",
  model_provider_rerank: "Rerank provider",
  model_provider_rerank_auth: "Rerank provider secret",
  qdrant: "Qdrant",
  redis: "Redis",
  secret_jwt_signing_key: "JWT signing key secret",
  secret_minio_access_key: "MinIO access key secret",
  secret_minio_secret_key: "MinIO secret key secret",
  secret_model_gateway_auth: "模型网关 secret",
  secret_model_provider_embedding_auth: "Embedding provider secret",
  secret_model_provider_llm_auth: "LLM provider secret",
  secret_model_provider_rerank_auth: "Rerank provider secret",
  secret_qdrant_api_key: "Qdrant API key secret",
  secret_store: "Secret Store",
};

const BOOTSTRAP_CHECK_HINTS: Record<string, string> = {
  keyword_search: "确认 PostgreSQL 镜像包含 zhparser，并且迁移已创建全文检索配置。",
  migration: "先执行 make PYTHON=.venv/bin/python db-upgrade，并确认 db-current 到 head。",
  minio: "检查初始化页 MinIO 地址是否能被 API 进程访问，并确认 /minio/health/live 可用。",
  model_provider_embedding: "检查 Embedding provider base URL 和 /health 路径是否能被 API 进程访问。",
  model_provider_llm: "检查 LLM provider base URL、鉴权 token 和 /health 路径。",
  model_provider_rerank: "检查 Rerank provider base URL 和 /health 路径是否能被 API 进程访问。",
  qdrant: "检查 Qdrant base URL、鉴权配置和 /readyz 或根路径健康检查。",
  redis: "检查 Redis 地址是否能被 API 进程访问；宿主机运行 API 时不要使用容器内服务名。",
  secret_jwt_signing_key: "执行 make PYTHON=.venv/bin/python setup-secrets，确认 JWT signing key 已写入 Secret Store。",
  secret_minio_access_key: "执行 make PYTHON=.venv/bin/python setup-secrets，确认 MinIO access key 已写入 Secret Store。",
  secret_minio_secret_key: "执行 make PYTHON=.venv/bin/python setup-secrets，确认 MinIO secret key 已写入 Secret Store。",
  secret_model_provider_embedding_auth: "检查初始化页填写的 Embedding token，或清空不需要的 auth token ref。",
  secret_model_provider_llm_auth: "检查初始化页填写的 LLM token，或清空不需要的 auth token ref。",
  secret_model_provider_rerank_auth: "检查初始化页填写的 Rerank token，或清空不需要的 auth token ref。",
  secret_qdrant_api_key: "如启用 Qdrant API Key 鉴权，设置 SECRET_INIT_QDRANT_API_KEY 后执行 make PYTHON=.venv/bin/python setup-qdrant-secret；未启用时保持 Qdrant API Key 引用为空。",
};

export function extractStructuredIssues(payload: ApiErrorPayload | null): SetupIssue[] {
  // 后端校验错误放在 details.errors 中，页面只消费结构化数组，避免解析自由文本。
  const details = asRecord(payload?.details);
  const errors = details?.errors;
  return Array.isArray(errors) ? errors.filter((item): item is SetupIssue => isRecord(item)) : [];
}

export function extractBootstrapChecks(payload: ApiErrorPayload | null): BootstrapCheckIssue[] {
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

export function isBootstrapProblemCheck(check: BootstrapCheckIssue): boolean {
  return check.status === "failed" || (check.status === "skipped" && check.required);
}

export function formatBootstrapCheckName(name: string): string {
  return BOOTSTRAP_CHECK_LABELS[name] ?? name;
}

export function bootstrapCheckHint(name: string): string | null {
  return BOOTSTRAP_CHECK_HINTS[name] ?? null;
}

export function buildInitializationFailureMessage(
  payload: ApiErrorPayload | null,
  fallback: string,
): string {
  const checks = extractBootstrapChecks(payload).filter(isBootstrapProblemCheck);
  if (checks.length > 0) {
    const labels = checks.slice(0, 3).map((check) => formatBootstrapCheckName(check.name));
    const suffix = checks.length > labels.length ? ` 等 ${checks.length} 项` : "";
    return `${fallback}：${labels.join("、")}${suffix}未通过`;
  }

  const issues = extractStructuredIssues(payload);
  if (issues[0]?.message) {
    return `${fallback}：${issues[0].message}`;
  }

  const databaseError = extractDatabaseError(payload);
  if (databaseError?.message) {
    return `${fallback}：${databaseError.message}`;
  }

  return payload?.message ? `${fallback}：${payload.message}` : fallback;
}

export function extractDatabaseError(payload: ApiErrorPayload | null): DatabaseErrorIssue | null {
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
