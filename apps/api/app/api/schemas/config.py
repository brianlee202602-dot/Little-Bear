"""Config Admin API 的请求和响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value_json: dict[str, Any]
    scope_type: str
    status: Literal["draft", "validating", "active", "archived", "failed"]
    version: int


class PaginationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    page_size: int
    total: int


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
    data: list[ConfigItemData]
    pagination: PaginationData


class ConfigVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    status: Literal["draft", "validating", "active", "archived", "failed"]
    risk_level: Literal["low", "medium", "high", "critical"]
    created_by: str | None = None


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
    data: list[ConfigVersionData]


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
