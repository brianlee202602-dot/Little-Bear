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
  query_scope_mode: "explicit" | "auto_all_accessible";
  resolved_kb_count: number;
  rewrite_count: number;
  error_code: string | null;
  created_at: string | null;
  retrieval_diagnostics: QueryRetrievalDiagnosticsData | null;
}

export interface QueryRetrievalDiagnosticsData {
  rewrite_queries?: QueryRetrievalQueryData[];
  stage_counts?: QueryRetrievalStageCountsData;
  quality_gate?: QueryRetrievalQualityGateData;
  selected_chunks?: QueryRetrievalSelectedChunkData[];
}

export interface QueryRetrievalQueryData {
  query?: string;
  index?: number;
  intent?: string | null;
  weight?: number;
}

export interface QueryRetrievalStageCountsData {
  resolved_kb_count?: number;
  keyword_candidate_count?: number;
  vector_candidate_count?: number;
  fused_candidate_count?: number;
  gated_candidate_count?: number;
  relevant_candidate_count?: number;
  quality_rejected_count?: number;
  context_candidate_count?: number;
  context_chunk_count?: number;
  citation_count?: number;
  per_query?: QueryRetrievalPerQueryData[];
  gate?: QueryRetrievalGateData;
  rerank?: QueryRetrievalRerankData[];
}

export interface QueryRetrievalQualityGateData {
  reason?: string | null;
  top_score?: number | null;
  rejected_count?: number | null;
}

export interface QueryRetrievalSelectedChunkData {
  chunk_id?: string;
  document_id?: string;
  document_version_id?: string;
  title?: string;
  heading_path?: string | null;
  matched_query?: string | null;
  matched_query_index?: number;
  rank?: number;
  score?: number;
}

export interface QueryRetrievalPerQueryData {
  index?: number;
  query?: string;
  intent?: string | null;
  weight?: number;
  keyword_candidate_count?: number;
  vector_candidate_count?: number;
  fused_candidate_count?: number;
  gated_candidate_count?: number;
  relevant_candidate_count?: number;
  context_chunk_count?: number;
  vector_degraded?: boolean;
  vector_degrade_reason?: string | null;
}

export interface QueryRetrievalGateData {
  input_count?: number;
  allowed_count?: number;
  rejected_count?: number;
  missing_metadata_count?: number;
  rejection_reasons?: Array<{
    reason?: string;
    count?: number;
  }>;
}

export interface QueryRetrievalRerankData {
  query_index?: number;
  query?: string;
  input_candidate_count?: number;
  output_candidate_count?: number;
  degraded?: boolean;
  degrade_reason?: string | null;
  model_status?: string;
  scores?: QueryRetrievalRerankScoreData[];
}

export interface QueryRetrievalRerankScoreData {
  chunk_id?: string;
  document_id?: string;
  title?: string;
  rank?: number;
  score?: number;
  source_score?: number;
  matched_query?: string | null;
  matched_query_index?: number;
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
  query_scope_mode: "explicit" | "auto_all_accessible";
  resolved_kb_count: number;
  rewrite_count: number;
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
