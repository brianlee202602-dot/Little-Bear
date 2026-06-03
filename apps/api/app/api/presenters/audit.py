"""审计响应 DTO 映射。"""

from __future__ import annotations

from app.api.schemas.audit import (
    AuditLogData,
    AuditLogListItemData,
    ModelCallLogData,
    ModelCallLogListItemData,
    QueryLogData,
    QueryLogListItemData,
)
from app.modules.audit.schemas import AuditLog, ModelCallLog, QueryLog


def audit_log_data(log: AuditLog) -> AuditLogData:
    return AuditLogData(
        id=log.id,
        request_id=log.request_id,
        trace_id=log.trace_id,
        event_name=log.event_name,
        actor_type=log.actor_type,
        actor_id=log.actor_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        result=log.result,
        risk_level=log.risk_level,
        config_version=log.config_version,
        permission_version=log.permission_version,
        index_version_hash=log.index_version_hash,
        summary_json=log.summary_json,
        error_code=log.error_code,
        created_at=log.created_at,
    )


def audit_log_list_item_data(log: AuditLog) -> AuditLogListItemData:
    return AuditLogListItemData(
        id=log.id,
        event_name=log.event_name,
        actor_type=log.actor_type,
        action=log.action,
        resource_type=log.resource_type,
        result=log.result,
        risk_level=log.risk_level,
        config_version=log.config_version,
        permission_version=log.permission_version,
        error_code=log.error_code,
        created_at=log.created_at,
    )


def query_log_data(log: QueryLog) -> QueryLogData:
    return QueryLogData(
        id=log.id,
        request_id=log.request_id,
        trace_id=log.trace_id,
        user_id=log.user_id,
        user_display_name=log.user_display_name,
        kb_ids=list(log.kb_ids),
        knowledge_base_names=list(log.knowledge_base_names),
        query_hash=log.query_hash,
        status=log.status,
        degraded=log.degraded,
        degrade_reason=log.degrade_reason,
        config_version=log.config_version,
        permission_version=log.permission_version,
        permission_filter_hash=log.permission_filter_hash,
        index_version_hash=log.index_version_hash,
        model_route_hash=log.model_route_hash,
        latency_ms=log.latency_ms,
        candidate_count=log.candidate_count,
        citation_count=log.citation_count,
        query_scope_mode=log.query_scope_mode,
        resolved_kb_count=log.resolved_kb_count,
        rewrite_count=log.rewrite_count,
        error_code=log.error_code,
        created_at=log.created_at,
        retrieval_diagnostics=log.retrieval_diagnostics,
    )


def query_log_list_item_data(log: QueryLog) -> QueryLogListItemData:
    return QueryLogListItemData(
        id=log.id,
        user_display_name=log.user_display_name,
        knowledge_base_names=list(log.knowledge_base_names),
        status=log.status,
        degraded=log.degraded,
        degrade_reason=log.degrade_reason,
        latency_ms=log.latency_ms,
        candidate_count=log.candidate_count,
        citation_count=log.citation_count,
        query_scope_mode=log.query_scope_mode,
        resolved_kb_count=log.resolved_kb_count,
        rewrite_count=log.rewrite_count,
        error_code=log.error_code,
        created_at=log.created_at,
    )


def model_call_log_data(log: ModelCallLog) -> ModelCallLogData:
    return ModelCallLogData(
        id=log.id,
        request_id=log.request_id,
        trace_id=log.trace_id,
        caller=log.caller,
        model_type=log.model_type,
        model_name=log.model_name,
        model_version=log.model_version,
        model_route_hash=log.model_route_hash,
        status=log.status,
        latency_ms=log.latency_ms,
        token_usage_json=log.token_usage_json,
        degraded=log.degraded,
        config_version=log.config_version,
        prompt_hash=log.prompt_hash,
        input_hash=log.input_hash,
        output_hash=log.output_hash,
        error_code=log.error_code,
        created_at=log.created_at,
    )


def model_call_log_list_item_data(log: ModelCallLog) -> ModelCallLogListItemData:
    return ModelCallLogListItemData(
        id=log.id,
        caller=log.caller,
        model_type=log.model_type,
        model_name=log.model_name,
        model_version=log.model_version,
        status=log.status,
        latency_ms=log.latency_ms,
        degraded=log.degraded,
        error_code=log.error_code,
        created_at=log.created_at,
    )
