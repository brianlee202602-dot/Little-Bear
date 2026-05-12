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
    status: Literal["active", "disabled", "deleted"]
    is_primary: bool = False
    is_default: bool = False


class DepartmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)


class DepartmentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled"] | None = None


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
    data: list[UserData]
    pagination: PaginationData


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DepartmentData


class DepartmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentData]
    pagination: PaginationData


class KnowledgeBaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]
    owner_department_id: str
    default_visibility: Literal["department", "enterprise"]
    config_scope_id: str | None = None
    policy_version: int = 1


class KnowledgeBaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    owner_department_id: str = Field(min_length=1)
    default_visibility: Literal["department", "enterprise"]
    config_scope_id: str | None = Field(default=None, min_length=1, max_length=128)


class KnowledgeBasePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled", "archived"] | None = None
    default_visibility: Literal["department", "enterprise"] | None = None
    config_scope_id: str | None = Field(default=None, min_length=1, max_length=128)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: KnowledgeBaseData


class KnowledgeBaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseData]
    pagination: PaginationData


class AcceptedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    job_id: str | None = None


class AcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: AcceptedData


class FolderData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str
    parent_id: str | None = None
    name: str
    status: Literal["active", "disabled", "archived"]


class FolderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, min_length=1)


class FolderPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, min_length=1)
    status: Literal["active", "disabled", "archived"] | None = None


class FolderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: FolderData


class FolderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[FolderData]
    pagination: PaginationData


class DocumentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str
    folder_id: str | None = None
    title: str
    lifecycle_status: Literal["draft", "active", "archived", "deleted"]
    index_status: Literal["none", "indexing", "indexed", "index_failed", "blocked"]
    owner_department_id: str
    visibility: Literal["department", "enterprise"]
    current_version_id: str | None = None


class DocumentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=256)
    folder_id: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    owner_department_id: str | None = Field(default=None, min_length=1)
    visibility: Literal["department", "enterprise"] | None = None
    lifecycle_status: Literal["active", "archived", "deleted"] | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DocumentData


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DocumentData]
    pagination: PaginationData


class UserDepartmentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentData]


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
