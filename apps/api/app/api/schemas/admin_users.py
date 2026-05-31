"""管理后台用户 API 请求和响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.admin_departments import DepartmentData
from app.api.schemas.admin_roles import RoleData
from app.api.schemas.common import PaginationData


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


class UserListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    name: str
    status: Literal["active", "disabled", "locked", "deleted"]
    department_names: list[str] = Field(default_factory=list)
    role_names: list[str] = Field(default_factory=list)


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


class UserDepartmentsPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_ids: list[str] = Field(min_length=1)


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
    data: list[UserListItemData]
    pagination: PaginationData


class UserDepartmentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentData]
    pagination: PaginationData
