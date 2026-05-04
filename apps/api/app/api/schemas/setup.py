from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SetupStateData(BaseModel):
    """setup-state 的有限响应数据，不返回 token 或 secret 明文。"""

    model_config = ConfigDict(extra="forbid")

    initialized: bool
    setup_status: str
    active_config_version: int | None = None
    setup_required: bool
    active_config_present: bool
    recovery_setup_allowed: bool = False
    recovery_reason: str | None = None
    system_token_expires_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class SetupStateResponse(BaseModel):
    """符合 OpenAPI 外层响应结构的 setup-state 响应。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: SetupStateData


class SetupConfigValidationData(BaseModel):
    """初始化配置校验响应。"""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[dict[str, object]] = Field(default_factory=list)


class SetupConfigValidationResponse(BaseModel):
    """初始化配置校验外层响应。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: SetupConfigValidationData


class SetupInitializationData(BaseModel):
    """初始化提交响应。"""

    model_config = ConfigDict(extra="forbid")

    initialized: bool
    active_config_version: int
    enterprise_id: str
    admin_user_id: str


class SetupInitializationResponse(BaseModel):
    """初始化提交外层响应。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: SetupInitializationData
