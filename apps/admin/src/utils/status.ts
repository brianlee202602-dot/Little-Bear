import type {
  ModelCallLogData,
  ModelCallLogListItemData,
  QueryLogData,
  QueryLogListItemData,
} from "@/api/diagnostics";
import type { IndexCollectionHealthData } from "@/api/indexOps";
import { formatStatusText } from "@/utils/display";
import { formatAuditTime } from "@/utils/date";

export type Tone = "success" | "error" | "warning" | "neutral";

export type QueryLogDisplayData = QueryLogData | QueryLogListItemData;
export type ModelCallLogDisplayData = ModelCallLogData | ModelCallLogListItemData;

export function formatStatusWithDegradation(
  status: string,
  degraded: boolean,
  formatStatusText: (status: string | null | undefined) => string,
): string {
  const statusText = formatStatusText(status);
  if (status === "degraded") {
    return "已降级";
  }
  if (degraded) {
    return `${statusText} / 已降级`;
  }
  return `${statusText} / 未降级`;
}

export function formatDiagnosticReasonCode(reason: string): string {
  const labels: Record<string, string> = {
    llm_context_empty: "无上下文",
    llm_runtime_config_unavailable: "LLM 配置缺失",
    llm_stream_result_missing: "流式为空",
    llm_degraded: "LLM 降级",
    citation_missing: "缺少引用",
    citation_auto_attached: "自动补引用",
    citation_invalid_format: "引用格式错误",
    citation_unauthorized: "引用未授权",
    vector_retriever_unavailable: "向量不可用",
    vector_runtime_config_unavailable: "向量配置缺失",
    vector_runtime_config_incomplete: "向量配置不完整",
    vector_collection_unavailable: "向量集合不可用",
    query_embedding_failed: "问题向量化失败",
    vector_search_failed: "向量检索失败",
    vector_retrieval_degraded: "向量降级",
    retrieval_relevance_too_low: "相关性过低",
    RERANK_PROVIDER_UNAVAILABLE: "精排不可用",
    RERANK_PROVIDER_HTTP_ERROR: "精排异常",
    RERANK_PROVIDER_RESPONSE_INVALID: "精排响应异常",
    QUERY_RERANK_INPUT_UNAVAILABLE: "精排输入缺失",
    rerank_input_mismatch: "精排输入不匹配",
    rerank_degraded: "精排降级",
    LLM_PROVIDER_HTTP_ERROR: "LLM 异常",
    LLM_PROVIDER_UNAVAILABLE: "LLM 不可用",
    LLM_PROVIDER_RESPONSE_INVALID: "LLM 响应异常",
    QUERY_STREAM_FINALIZE_FAILED: "流式收尾失败",
  };
  return labels[reason] ?? "未归类";
}

export function formatDiagnosticReasonList(
  value: string | null | undefined,
  fallback = "未降级",
): string {
  if (!value) {
    return fallback;
  }
  return (
    value
      .split(";")
      .map((item) => item.trim())
      .filter(Boolean)
      .map(formatDiagnosticReasonCode)
      .filter((item, index, items) => items.indexOf(item) === index)
      .join("；") || fallback
  );
}

export function queryLogStatusTone(log: QueryLogDisplayData): Tone {
  if (log.status === "success" && !log.degraded) {
    return "success";
  }
  if (log.status === "denied" || log.degraded) {
    return "warning";
  }
  return "error";
}

export function modelCallStatusTone(log: ModelCallLogDisplayData): Tone {
  if (log.status === "success" && !log.degraded) {
    return "success";
  }
  if (log.status === "degraded" || log.degraded) {
    return "warning";
  }
  return "error";
}

export function indexHealthTone(item: IndexCollectionHealthData): Tone {
  if (item.issues.length === 0) {
    return "success";
  }
  if (
    item.issues.some((issue) =>
      [
        "qdrant_unreachable",
        "qdrant_collection_missing",
        "qdrant_vector_size_mismatch",
        "qdrant_points_less_than_active_refs",
        "active_index_ref_count_mismatch",
      ].includes(issue),
    )
  ) {
    return "error";
  }
  return "warning";
}

export function formatIssueList(issues: string[]): string {
  return issues.length ? issues.join(" / ") : "无";
}

export function formatQueryLogStatus(log: QueryLogDisplayData): string {
  return formatStatusWithDegradation(log.status, log.degraded, formatStatusText);
}

export function formatModelCallStatus(log: ModelCallLogDisplayData): string {
  return formatStatusWithDegradation(log.status, log.degraded, formatStatusText);
}

export function formatModelCallTitle(log: ModelCallLogDisplayData): string {
  return `${log.model_name} / ${formatModelCallStatus(log)}`;
}

export function formatQueryLogTitle(log: QueryLogDisplayData): string {
  return `${formatAuditTime(log.created_at)} / ${formatQueryLogStatus(log)}`;
}

export function formatQueryLogUser(log: QueryLogDisplayData): string {
  return log.user_display_name || "未知用户";
}

export function formatQueryLogKnowledgeBases(log: QueryLogDisplayData): string {
  if (log.knowledge_base_names.length) {
    return log.knowledge_base_names.join("，");
  }
  if ("kb_ids" in log && log.kb_ids.length) {
    return `${log.kb_ids.length} 个知识库`;
  }
  return "-";
}

export function auditSummaryPreview(log: {
  action: string;
  config_version: number | null;
  permission_version: number | null;
  resource_type: string;
}): string {
  const version = log.config_version ? `v${log.config_version}` : "";
  const permissionVersion = log.permission_version ? `权限 v${log.permission_version}` : "";
  const resource = log.resource_type ? formatStatusText(log.resource_type) : "";
  const action = log.action ? formatStatusText(log.action) : "";
  return [version, permissionVersion, resource, action].filter(Boolean).join(" / ") || "-";
}
