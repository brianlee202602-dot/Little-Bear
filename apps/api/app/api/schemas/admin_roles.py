"""管理后台角色 API 请求和响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginationData


class RoleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    is_builtin: bool
    status: Literal["active", "disabled", "archived"]
    scopes: list[str] = Field(default_factory=list)


class RoleListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    is_builtin: bool
    status: Literal["active", "disabled", "archived"]


class AssignableRoleOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    scope_type: Literal["enterprise", "department", "knowledge_base"]
    status: Literal["active", "disabled", "archived"]
    risk_level: Literal["low", "high"]


class RoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: RoleData


class RoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[RoleListItemData]
    pagination: PaginationData


class AssignableRoleOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[AssignableRoleOptionData]
    pagination: PaginationData


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
    pagination: PaginationData
