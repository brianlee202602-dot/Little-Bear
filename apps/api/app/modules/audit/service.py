"""Audit Service 的 P0 读取实现。

P0 只暴露审计事实源 `audit_logs` 的只读查询能力。写入由各业务模块在事务内完成，
这里不做审计事件生成，避免读写职责混在一起。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.audit.errors import AuditServiceError
from app.modules.audit.schemas import (
    AuditLog,
    AuditLogList,
    ModelCallLog,
    ModelCallLogList,
    QueryLog,
    QueryLogList,
)
from app.shared.json_utils import as_dict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

AUDIT_FILTER_FIELDS = {
    "actor_id": "actor_id",
    "action": "action",
    "resource_type": "resource_type",
    "result": "result",
    "risk_level": "risk_level",
}

QUERY_LOG_FILTER_FIELDS = {
    "request_id": "request_id",
    "trace_id": "trace_id",
    "user_id": "user_id",
    "status": "status",
    "degrade_reason": "degrade_reason",
    "error_code": "error_code",
}

MODEL_CALL_LOG_FILTER_FIELDS = {
    "request_id": "request_id",
    "trace_id": "trace_id",
    "caller": "caller",
    "model_type": "model_type",
    "status": "status",
    "error_code": "error_code",
}


class AuditService:
    """读取审计日志并提供受控筛选。"""

    def list_audit_logs(
        self,
        session: Session,
        *,
        page: int,
        page_size: int,
        filters: dict[str, str | None] | None = None,
    ) -> AuditLogList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions, params = _build_filter_conditions(filters or {})
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.update({"limit": page_size, "offset": (page - 1) * page_size})

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS id,
                        request_id,
                        trace_id,
                        event_name,
                        actor_type,
                        actor_id,
                        action,
                        resource_type,
                        resource_id,
                        result,
                        risk_level,
                        config_version,
                        permission_version,
                        index_version_hash,
                        summary_json,
                        error_code,
                        created_at
                    FROM audit_logs
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM audit_logs {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "AUDIT_LOG_UNAVAILABLE",
                "audit logs cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc

        return AuditLogList(
            items=[_audit_log_from_mapping(dict(row._mapping)) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_audit_log(self, session: Session, audit_id: str) -> AuditLog:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS id,
                        request_id,
                        trace_id,
                        event_name,
                        actor_type,
                        actor_id,
                        action,
                        resource_type,
                        resource_id,
                        result,
                        risk_level,
                        config_version,
                        permission_version,
                        index_version_hash,
                        summary_json,
                        error_code,
                        created_at
                    FROM audit_logs
                    WHERE id::text = :audit_id
                    LIMIT 1
                    """
                ),
                {"audit_id": audit_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "AUDIT_LOG_UNAVAILABLE",
                "audit log cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__, "audit_id": audit_id},
            ) from exc

        if row is None:
            raise AuditServiceError(
                "AUDIT_LOG_NOT_FOUND",
                "audit log does not exist",
                details={"audit_id": audit_id},
            )
        return _audit_log_from_mapping(dict(row._mapping))

    def list_query_logs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        filters: dict[str, str | bool | None] | None = None,
    ) -> QueryLogList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions, params = _build_query_log_filter_conditions(filters or {})
        conditions.insert(0, "enterprise_id = CAST(:enterprise_id AS uuid)")
        params.update(
            {
                "enterprise_id": enterprise_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            }
        )
        where_sql = f"WHERE {' AND '.join(conditions)}"

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS id,
                        request_id,
                        trace_id,
                        user_id::text AS user_id,
                        kb_ids,
                        query_hash,
                        status,
                        degraded,
                        degrade_reason,
                        config_version,
                        permission_version,
                        permission_filter_hash,
                        index_version_hash,
                        model_route_hash,
                        latency_ms,
                        candidate_count,
                        citation_count,
                        error_code,
                        created_at
                    FROM query_logs
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM query_logs {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "QUERY_LOG_UNAVAILABLE",
                "query logs cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc

        return QueryLogList(
            items=[_query_log_from_mapping(dict(row._mapping)) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_query_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        query_log_id: str,
    ) -> QueryLog:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS id,
                        request_id,
                        trace_id,
                        user_id::text AS user_id,
                        kb_ids,
                        query_hash,
                        status,
                        degraded,
                        degrade_reason,
                        config_version,
                        permission_version,
                        permission_filter_hash,
                        index_version_hash,
                        model_route_hash,
                        latency_ms,
                        candidate_count,
                        citation_count,
                        error_code,
                        created_at
                    FROM query_logs
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND id::text = :query_log_id
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id, "query_log_id": query_log_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "QUERY_LOG_UNAVAILABLE",
                "query log cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__, "query_log_id": query_log_id},
            ) from exc

        if row is None:
            raise AuditServiceError(
                "QUERY_LOG_NOT_FOUND",
                "query log does not exist",
                details={"query_log_id": query_log_id},
            )
        return _query_log_from_mapping(dict(row._mapping))

    def list_model_call_logs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        filters: dict[str, str | bool | None] | None = None,
    ) -> ModelCallLogList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions, params = _build_model_call_log_filter_conditions(filters or {})
        conditions.insert(0, "enterprise_id = CAST(:enterprise_id AS uuid)")
        params.update(
            {
                "enterprise_id": enterprise_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            }
        )
        where_sql = f"WHERE {' AND '.join(conditions)}"

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS id,
                        request_id,
                        trace_id,
                        caller,
                        model_type,
                        model_name,
                        model_version,
                        model_route_hash,
                        status,
                        latency_ms,
                        token_usage_json,
                        degraded,
                        config_version,
                        prompt_hash,
                        input_hash,
                        output_hash,
                        error_code,
                        created_at
                    FROM model_call_logs
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM model_call_logs {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "MODEL_CALL_LOG_UNAVAILABLE",
                "model call logs cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc

        return ModelCallLogList(
            items=[_model_call_log_from_mapping(dict(row._mapping)) for row in rows],
            total=int(total_row._mapping["total"]),
        )


def _build_filter_conditions(filters: dict[str, str | None]) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    for field, column in AUDIT_FILTER_FIELDS.items():
        value = filters.get(field)
        if not value:
            continue
        conditions.append(f"{column} = :{field}")
        params[field] = value
    return conditions, params


def _build_query_log_filter_conditions(
    filters: dict[str, str | bool | None],
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    for field, column in QUERY_LOG_FILTER_FIELDS.items():
        value = filters.get(field)
        if not value:
            continue
        if field == "user_id":
            conditions.append(f"{column} = CAST(:{field} AS uuid)")
        else:
            conditions.append(f"{column} = :{field}")
        params[field] = value
    degraded = filters.get("degraded")
    if isinstance(degraded, bool):
        conditions.append("degraded = :degraded")
        params["degraded"] = degraded
    kb_id = filters.get("kb_id")
    if isinstance(kb_id, str) and kb_id:
        conditions.append("CAST(:kb_id AS uuid) = ANY(kb_ids)")
        params["kb_id"] = kb_id
    return conditions, params


def _build_model_call_log_filter_conditions(
    filters: dict[str, str | bool | None],
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    for field, column in MODEL_CALL_LOG_FILTER_FIELDS.items():
        value = filters.get(field)
        if not value:
            continue
        conditions.append(f"{column} = :{field}")
        params[field] = value
    degraded = filters.get("degraded")
    if isinstance(degraded, bool):
        conditions.append("degraded = :degraded")
        params["degraded"] = degraded
    model = filters.get("model")
    if isinstance(model, str) and model:
        conditions.append("(model_name ILIKE :model OR model_route_hash ILIKE :model)")
        params["model"] = f"%{model}%"
    return conditions, params


def _audit_log_from_mapping(row: dict[str, Any]) -> AuditLog:
    return AuditLog(
        id=str(row["id"]),
        request_id=_optional_str(row.get("request_id")),
        trace_id=_optional_str(row.get("trace_id")),
        event_name=str(row["event_name"]),
        actor_type=str(row["actor_type"]),
        actor_id=_optional_str(row.get("actor_id")),
        action=str(row["action"]),
        resource_type=str(row["resource_type"]),
        resource_id=_optional_str(row.get("resource_id")),
        result=str(row["result"]),
        risk_level=str(row["risk_level"]),
        config_version=_optional_int(row.get("config_version")),
        permission_version=_optional_int(row.get("permission_version")),
        index_version_hash=_optional_str(row.get("index_version_hash")),
        summary_json=as_dict(row.get("summary_json")),
        error_code=_optional_str(row.get("error_code")),
        created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else None,
    )


def _query_log_from_mapping(row: dict[str, Any]) -> QueryLog:
    return QueryLog(
        id=str(row["id"]),
        request_id=str(row["request_id"]),
        trace_id=str(row["trace_id"]),
        user_id=str(row["user_id"]),
        kb_ids=tuple(str(item) for item in row.get("kb_ids") or ()),
        query_hash=str(row["query_hash"]),
        status=str(row["status"]),
        degraded=bool(row["degraded"]),
        degrade_reason=_optional_str(row.get("degrade_reason")),
        config_version=int(row["config_version"]),
        permission_version=int(row["permission_version"]),
        permission_filter_hash=str(row["permission_filter_hash"]),
        index_version_hash=_optional_str(row.get("index_version_hash")),
        model_route_hash=_optional_str(row.get("model_route_hash")),
        latency_ms=int(row["latency_ms"]),
        candidate_count=int(row["candidate_count"]),
        citation_count=int(row["citation_count"]),
        error_code=_optional_str(row.get("error_code")),
        created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else None,
    )


def _model_call_log_from_mapping(row: dict[str, Any]) -> ModelCallLog:
    token_usage = row.get("token_usage_json")
    return ModelCallLog(
        id=str(row["id"]),
        request_id=_optional_str(row.get("request_id")),
        trace_id=str(row["trace_id"]),
        caller=str(row["caller"]),
        model_type=str(row["model_type"]),
        model_name=str(row["model_name"]),
        model_version=_optional_str(row.get("model_version")),
        model_route_hash=str(row["model_route_hash"]),
        status=str(row["status"]),
        latency_ms=int(row["latency_ms"]),
        token_usage_json=as_dict(token_usage) if token_usage is not None else None,
        degraded=bool(row["degraded"]),
        config_version=_optional_int(row.get("config_version")),
        prompt_hash=_optional_str(row.get("prompt_hash")),
        input_hash=_optional_str(row.get("input_hash")),
        output_hash=_optional_str(row.get("output_hash")),
        error_code=_optional_str(row.get("error_code")),
        created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else None,
    )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
