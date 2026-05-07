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
