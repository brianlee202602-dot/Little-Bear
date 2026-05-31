"""Import pipeline audit writer helpers."""

from __future__ import annotations

from typing import Any

from app.modules.audit import AuditWriter
from sqlalchemy.orm import Session


class ImportAuditWriter:
    """导入域审计写入适配器。

    这里固定导入任务相关的 actor/resource/action 默认值，避免 core、worker service
    和后续拆分模块重复拼装 audit 字段。
    """

    def write_user_event(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        AuditWriter().write(
            session,
            enterprise_id=enterprise_id,
            event_name=event_name,
            actor_type="user",
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            risk_level=risk_level,
            summary=summary,
            error_code=error_code,
        )

    def write_worker_event(
        self,
        session: Session,
        *,
        enterprise_id: str,
        event_name: str,
        resource_id: str,
        summary: dict[str, Any],
    ) -> None:
        AuditWriter().write(
            session,
            enterprise_id=enterprise_id,
            event_name=event_name,
            actor_type="system",
            actor_id=str(summary.get("worker_id", "worker")),
            resource_type="import_job",
            resource_id=resource_id,
            action="worker_update",
            result="success",
            risk_level="low",
            summary=summary,
        )
