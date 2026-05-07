"""Audit Service 的 P0 读取实现。

P0 只暴露审计事实源 `audit_logs` 的只读查询能力。写入由各业务模块在事务内完成，
这里不做审计事件生成，避免读写职责混在一起。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.audit.errors import AuditServiceError
from app.modules.audit.schemas import AuditLog, AuditLogList
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


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
