import { requestJson } from "./http";
import type { AuditLogListResponse, AuditLogResponse } from "./auditTypes";

export type {
  AuditLogData,
  AuditLogListItemData,
  AuditLogListResponse,
  AuditLogResponse,
  AuditResult,
} from "./auditTypes";
export type { PaginationData } from "./commonTypes";
export type { ConfigRiskLevel } from "./configTypes";

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
