"""Audit writer wrapper for setup initialization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session


class SetupInitializationAuditWriter:
    """Persist setup initialization audit events."""

    def __init__(self, *, audit_writer_factory: Callable[[], Any]) -> None:
        self._audit_writer_factory = audit_writer_factory

    def write(
        self,
        session: Session,
        *,
        event_name: str,
        action: str,
        result: str,
        summary: dict[str, Any],
        risk_level: str = "critical",
        resource_id: str | None = None,
        error_code: str | None = None,
        config_version: int | None = None,
    ) -> None:
        self._audit_writer_factory().write(
            session,
            event_name=event_name,
            actor_type="setup",
            actor_id=str(summary.get("setup_token_id")) if summary.get("setup_token_id") else None,
            resource_type="setup",
            resource_id=resource_id,
            action=action,
            result=result,
            risk_level=risk_level,
            config_version=config_version,
            summary=summary,
            error_code=error_code,
            filter_summary_none=True,
        )
