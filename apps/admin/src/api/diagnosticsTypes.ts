import type { PaginationData } from "./commonTypes";

export interface QueryLogData {
  id: string;
  request_id: string;
  trace_id: string;
  user_id: string;
  user_display_name: string | null;
  kb_ids: string[];
  knowledge_base_names: string[];
  query_hash: string;
  status: "success" | "failed" | "denied";
  degraded: boolean;
  degrade_reason: string | null;
  config_version: number;
  permission_version: number;
  permission_filter_hash: string;
  index_version_hash: string | null;
  model_route_hash: string | null;
  latency_ms: number;
  candidate_count: number;
  citation_count: number;
  error_code: string | null;
  created_at: string | null;
}

export interface QueryLogResponse {
  request_id: string;
  data: QueryLogData;
}

export interface QueryLogListItemData {
  id: string;
  user_display_name: string | null;
  knowledge_base_names: string[];
  status: "success" | "failed" | "denied";
  degraded: boolean;
  degrade_reason: string | null;
  latency_ms: number;
  candidate_count: number;
  citation_count: number;
  error_code: string | null;
  created_at: string | null;
}

export interface QueryLogListResponse {
  request_id: string;
  data: QueryLogListItemData[];
  pagination: PaginationData;
}

export interface ModelCallLogData {
  id: string;
  request_id: string | null;
  trace_id: string;
  caller: string;
  model_type: string;
  model_name: string;
  model_version: string | null;
  model_route_hash: string;
  status: "success" | "failed" | "degraded";
  latency_ms: number;
  token_usage_json: Record<string, unknown> | null;
  degraded: boolean;
  config_version: number | null;
  prompt_hash: string | null;
  input_hash: string | null;
  output_hash: string | null;
  error_code: string | null;
  created_at: string | null;
}

export interface ModelCallLogResponse {
  request_id: string;
  data: ModelCallLogData;
}

export interface ModelCallLogListItemData {
  id: string;
  caller: string;
  model_type: string;
  model_name: string;
  model_version: string | null;
  status: "success" | "failed" | "degraded";
  latency_ms: number;
  degraded: boolean;
  error_code: string | null;
  created_at: string | null;
}

export interface ModelCallLogListResponse {
  request_id: string;
  data: ModelCallLogListItemData[];
  pagination: PaginationData;
}
