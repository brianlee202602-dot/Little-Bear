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


@dataclass(frozen=True)
class QueryLog:
    id: str
    request_id: str
    trace_id: str
    user_id: str
    kb_ids: tuple[str, ...]
    query_hash: str
    status: str
    degraded: bool
    degrade_reason: str | None
    config_version: int
    permission_version: int
    permission_filter_hash: str
    index_version_hash: str | None
    model_route_hash: str | None
    latency_ms: int
    candidate_count: int
    citation_count: int
    error_code: str | None
    created_at: datetime | None = None


@dataclass(frozen=True)
class QueryLogList:
    items: list[QueryLog]
    total: int


@dataclass(frozen=True)
class ModelCallLog:
    id: str
    request_id: str | None
    trace_id: str
    caller: str
    model_type: str
    model_name: str
    model_version: str | None
    model_route_hash: str
    status: str
    latency_ms: int
    token_usage_json: dict[str, Any] | None
    degraded: bool
    config_version: int | None
    prompt_hash: str | None
    input_hash: str | None
    output_hash: str | None
    error_code: str | None
    created_at: datetime | None = None


@dataclass(frozen=True)
class ModelCallLogList:
    items: list[ModelCallLog]
    total: int
