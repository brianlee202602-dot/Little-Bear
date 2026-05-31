"""Config Admin API 的请求和响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginationData


class ConfigItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value_json: dict[str, Any]
    scope_type: str
    status: Literal["draft", "validating", "active", "inactive", "archived", "failed"]
    version: int


class ConfigItemListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    scope_type: str
    status: Literal["draft", "validating", "active", "inactive", "archived", "failed"]
    version: int


class ConfigPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_json: dict[str, Any] = Field(default_factory=dict)


class ConfigItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: ConfigItemData


class ConfigItemListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[ConfigItemListItemData]
    pagination: PaginationData


class ConfigVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    status: Literal["draft", "validating", "active", "inactive", "archived", "failed"]
    risk_level: Literal["low", "medium", "high", "critical"]
    created_by: str | None = None
    config: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    activated_at: datetime | None = None


class ConfigVersionListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    status: Literal["draft", "validating", "active", "inactive", "archived", "failed"]
    risk_level: Literal["low", "medium", "high", "critical"]
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    activated_at: datetime | None = None


class ConfigVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] = Field(default_factory=dict)


class ConfigVersionPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] = Field(default_factory=dict)


class ConfigVersionPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "archived"]


class ConfigVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: ConfigVersionData


class ConfigVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[ConfigVersionListItemData]
    pagination: PaginationData


class ConfigValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any]


class ConfigValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[dict[str, object]] = Field(default_factory=list)


class ConfigValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: ConfigValidationData
