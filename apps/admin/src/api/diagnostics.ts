import { requestJson } from "./http";
import type {
  ModelCallLogListResponse,
  ModelCallLogResponse,
  QueryLogListResponse,
  QueryLogResponse,
} from "./diagnosticsTypes";

export type {
  ModelCallLogData,
  ModelCallLogListItemData,
  ModelCallLogListResponse,
  ModelCallLogResponse,
  QueryLogData,
  QueryLogListItemData,
  QueryLogListResponse,
  QueryLogResponse,
} from "./diagnosticsTypes";

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
