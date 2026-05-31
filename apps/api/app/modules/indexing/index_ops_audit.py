"""索引运维审计写入。"""

from __future__ import annotations

from typing import Any

from app.modules.audit import AuditWriter
from sqlalchemy.orm import Session


class IndexOpsAuditWriter:
    def write(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
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
            resource_type="config",
            resource_id=resource_id,
            action=action,
            result=result,
            risk_level=risk_level,
            summary=summary,
            error_code=error_code,
        )
