"""问答查询日志读取。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.audit.errors import AuditServiceError
from app.modules.audit.schemas import QueryLog, QueryLogList
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

QUERY_LOG_FILTER_FIELDS = {
    "request_id": "q.request_id",
    "trace_id": "q.trace_id",
    "user_id": "q.user_id",
    "status": "q.status",
    "query_scope_mode": "q.query_scope_mode",
    "degrade_reason": "q.degrade_reason",
    "error_code": "q.error_code",
}


class QueryLogReader:
    """读取问答链路诊断日志。"""

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
        conditions, params = _build_filter_conditions(filters or {})
        conditions.insert(0, "q.enterprise_id = CAST(:enterprise_id AS uuid)")
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
                        q.id::text AS id,
                        q.request_id,
                        q.trace_id,
                        q.user_id::text AS user_id,
                        COALESCE(
                            NULLIF(u.display_name, ''),
                            u.username,
                            q.user_id::text
                        ) AS user_display_name,
                        q.kb_ids,
                        COALESCE(
                            kb_lookup.knowledge_base_names,
                            ARRAY[]::text[]
                        ) AS knowledge_base_names,
                        q.query_hash,
                        q.status,
                        q.degraded,
                        q.degrade_reason,
                        q.config_version,
                        q.permission_version,
                        q.permission_filter_hash,
                        q.index_version_hash,
                        q.model_route_hash,
                        q.latency_ms,
                        q.candidate_count,
                        q.citation_count,
                        q.query_scope_mode,
                        q.resolved_kb_count,
                        q.rewrite_count,
                        q.error_code,
                        q.created_at
                    FROM query_logs q
                    LEFT JOIN users u
                      ON u.id = q.user_id
                     AND u.enterprise_id = q.enterprise_id
                    LEFT JOIN LATERAL (
                        SELECT array_agg(kb.name ORDER BY kb.name) AS knowledge_base_names
                        FROM knowledge_bases kb
                        WHERE kb.id = ANY(q.kb_ids)
                          AND kb.enterprise_id = q.enterprise_id
                    ) kb_lookup ON TRUE
                    {where_sql}
                    ORDER BY q.created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM query_logs q {where_sql}"),
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
                        q.id::text AS id,
                        q.request_id,
                        q.trace_id,
                        q.user_id::text AS user_id,
                        COALESCE(
                            NULLIF(u.display_name, ''),
                            u.username,
                            q.user_id::text
                        ) AS user_display_name,
                        q.kb_ids,
                        COALESCE(
                            kb_lookup.knowledge_base_names,
                            ARRAY[]::text[]
                        ) AS knowledge_base_names,
                        q.query_hash,
                        q.status,
                        q.degraded,
                        q.degrade_reason,
                        q.config_version,
                        q.permission_version,
                        q.permission_filter_hash,
                        q.index_version_hash,
                        q.model_route_hash,
                        q.latency_ms,
                        q.candidate_count,
                        q.citation_count,
                        q.query_scope_mode,
                        q.resolved_kb_count,
                        q.rewrite_count,
                        q.error_code,
                        retrieval_diag.diagnostics_json AS retrieval_diagnostics,
                        q.created_at
                    FROM query_logs q
                    LEFT JOIN users u
                      ON u.id = q.user_id
                     AND u.enterprise_id = q.enterprise_id
                    LEFT JOIN LATERAL (
                        SELECT array_agg(kb.name ORDER BY kb.name) AS knowledge_base_names
                        FROM knowledge_bases kb
                        WHERE kb.id = ANY(q.kb_ids)
                          AND kb.enterprise_id = q.enterprise_id
                    ) kb_lookup ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT jsonb_build_object(
                            'rewrite_queries', d.rewrite_queries,
                            'stage_counts', d.stage_counts,
                            'quality_gate', d.quality_gate,
                            'selected_chunks', d.selected_chunks
                        ) AS diagnostics_json
                        FROM query_retrieval_diagnostics d
                        WHERE d.query_log_id = q.id
                        LIMIT 1
                    ) retrieval_diag ON TRUE
                    WHERE q.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND q.id::text = :query_log_id
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


def _build_filter_conditions(
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
        conditions.append("q.degraded = :degraded")
        params["degraded"] = degraded
    kb_id = filters.get("kb_id")
    if isinstance(kb_id, str) and kb_id:
        conditions.append("CAST(:kb_id AS uuid) = ANY(q.kb_ids)")
        params["kb_id"] = kb_id
    return conditions, params


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
        query_scope_mode=str(row["query_scope_mode"]),
        resolved_kb_count=int(row["resolved_kb_count"]),
        rewrite_count=int(row["rewrite_count"]),
        error_code=_optional_str(row.get("error_code")),
        created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else None,
        user_display_name=_optional_str(row.get("user_display_name")),
        knowledge_base_names=tuple(str(item) for item in row.get("knowledge_base_names") or ()),
        retrieval_diagnostics=_json_mapping(row.get("retrieval_diagnostics")),
    )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _json_mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
