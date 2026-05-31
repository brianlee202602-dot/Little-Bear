"""审计日志写入工具。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.shared.context import get_request_context
from sqlalchemy import text
from sqlalchemy.orm import Session


class AuditWriter:
    """在业务事务内写入 `audit_logs`。

    该类只封装统一写入格式，不吞异常；各业务 service 仍负责把数据库异常转换成自己的
    ServiceError。
    """

    def write(
        self,
        session: Session,
        *,
        event_name: str,
        actor_type: str,
        action: str,
        resource_type: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        enterprise_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        config_version: int | None = None,
        permission_version: int | None = None,
        index_version_hash: str | None = None,
        error_code: str | None = None,
        filter_summary_none: bool = False,
    ) -> None:
        request_context = get_request_context()
        resolved_request_id = request_id
        resolved_trace_id = trace_id
        if request_context is not None:
            resolved_request_id = resolved_request_id or request_context.request_id
            resolved_trace_id = resolved_trace_id or request_context.trace_id

        if filter_summary_none:
            summary = {key: value for key, value in summary.items() if value is not None}

        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, enterprise_id, request_id, trace_id, event_name, actor_type,
                    actor_id, resource_type, resource_id, action, result, risk_level,
                    config_version, permission_version, index_version_hash, summary_json,
                    error_code
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id, :trace_id,
                    :event_name, :actor_type, :actor_id, :resource_type, :resource_id,
                    :action, :result, :risk_level, :config_version, :permission_version,
                    :index_version_hash, CAST(:summary_json AS jsonb), :error_code
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "request_id": resolved_request_id,
                "trace_id": resolved_trace_id,
                "event_name": event_name,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "result": result,
                "risk_level": risk_level,
                "config_version": config_version,
                "permission_version": permission_version,
                "index_version_hash": index_version_hash,
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
                "error_code": error_code,
            },
        )
