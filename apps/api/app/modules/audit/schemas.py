"""Audit Service 对外返回的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuditLog:
    id: str
    request_id: str | None
    trace_id: str | None
    event_name: str
    actor_type: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    result: str
    risk_level: str
    config_version: int | None
    permission_version: int | None
    index_version_hash: str | None
    summary_json: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class AuditLogList:
    items: list[AuditLog]
    total: int
