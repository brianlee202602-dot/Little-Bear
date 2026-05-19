"""Audit Admin API 的请求和响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.config import PaginationData


class AuditLogData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    request_id: str | None = None
    trace_id: str | None = None
    event_name: str
    actor_type: str
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    result: Literal["success", "failure", "denied"]
    risk_level: Literal["low", "medium", "high", "critical"]
    config_version: int | None = None
    permission_version: int | None = None
    index_version_hash: str | None = None
    summary_json: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    created_at: datetime | None = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: AuditLogData


class AuditLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[AuditLogData]
    pagination: PaginationData


class QueryLogData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    request_id: str
    trace_id: str
    user_id: str
    kb_ids: list[str] = Field(default_factory=list)
    query_hash: str
    status: Literal["success", "failed", "denied"]
    degraded: bool
    degrade_reason: str | None = None
    config_version: int
    permission_version: int
    permission_filter_hash: str
    index_version_hash: str | None = None
    model_route_hash: str | None = None
    latency_ms: int
    candidate_count: int
    citation_count: int
    error_code: str | None = None
    created_at: datetime | None = None


class QueryLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: QueryLogData


class QueryLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[QueryLogData]
    pagination: PaginationData


class ModelCallLogData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    request_id: str | None = None
    trace_id: str
    caller: str
    model_type: str
    model_name: str
    model_version: str | None = None
    model_route_hash: str
    status: Literal["success", "failed", "degraded"]
    latency_ms: int
    token_usage_json: dict[str, Any] | None = None
    degraded: bool
    config_version: int | None = None
    prompt_hash: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    error_code: str | None = None
    created_at: datetime | None = None


class ModelCallLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[ModelCallLogData]
    pagination: PaginationData
