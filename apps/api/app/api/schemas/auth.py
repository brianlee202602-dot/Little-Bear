"""Auth API 的请求和响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    enterprise_code: str | None = Field(default=None, min_length=1)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class DepartmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    status: str
    is_primary: bool = False


class RoleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: str
    is_builtin: bool
    status: str


class CurrentUserData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    name: str
    status: str
    departments: list[DepartmentData] = Field(default_factory=list)
    roles: list[RoleData] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: CurrentUserData


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)
