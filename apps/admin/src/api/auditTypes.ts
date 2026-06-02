import type { PaginationData } from "./commonTypes";
import type { ConfigRiskLevel } from "./configTypes";

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
