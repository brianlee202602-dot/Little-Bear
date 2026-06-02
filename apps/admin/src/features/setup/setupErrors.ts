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
