"""用户与角色管理 API 的请求和响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.config import PaginationData


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
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    is_builtin: bool
    status: Literal["active", "disabled", "archived"]
    scopes: list[str] = Field(default_factory=list)


class UserData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    name: str
    status: Literal["active", "disabled", "locked", "deleted"]
    enterprise_id: str
    email: str | None = None
    phone: str | None = None
    departments: list[DepartmentData] = Field(default_factory=list)
    roles: list[RoleData] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=128)
    initial_password: str = Field(min_length=1)
    department_ids: list[str] = Field(default_factory=list)
    role_ids: list[str] = Field(default_factory=list)


class UserPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled", "locked"] | None = None


class AdminPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=1)
    force_change_password: bool = True


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: UserData


class UserListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[UserData]
    pagination: PaginationData


class RoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: RoleData


class RoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[RoleData]


class RoleBindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role_id: str
    subject_type: Literal["user", "department"] = "user"
    subject_id: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    scope_id: str | None = None
    role_code: str | None = None
    role_name: str | None = None


class RoleBindingInputData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    scope_id: str | None = None


class RoleBindingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bindings: list[RoleBindingInputData] = Field(min_length=1)


class RoleBindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[RoleBindingData]
