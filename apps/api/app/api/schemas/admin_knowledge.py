"""管理后台知识库与文件夹 API 请求和响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.admin_departments import DepartmentData
from app.api.schemas.common import PaginationData


class KnowledgeBaseAccessRuleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["department", "user", "role"]
    subject_id: str
    permission: Literal["discover", "query", "manage"]


class KnowledgeBaseAccessRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["department", "user", "role"]
    subject_id: str = Field(min_length=1)
    permission: Literal["discover", "query", "manage"]


class KnowledgeBaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]
    owner_department_id: str
    owner_department: DepartmentData | None = None
    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str
    default_document_owner_department: DepartmentData | None = None
    access_rules: list[KnowledgeBaseAccessRuleData] = Field(default_factory=list)
    config_scope_id: str | None = None
    policy_version: int = 1


class KnowledgeBaseListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]
    owner_department_id: str
    owner_department_name: str | None = None
    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str
    default_document_owner_department_name: str | None = None


class KnowledgeBaseOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]


class KnowledgeBaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    owner_department_id: str = Field(min_length=1)
    kb_visibility: Literal["enterprise", "department_acl", "private"] = "enterprise"
    default_document_visibility: Literal["department", "enterprise"] = "department"
    default_document_owner_department_id: str | None = Field(default=None, min_length=1)
    access_rules: list[KnowledgeBaseAccessRuleInput] = Field(default_factory=list)
    config_scope_id: str | None = Field(default=None, min_length=1, max_length=128)


class KnowledgeBasePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled", "archived"] | None = None
    kb_visibility: Literal["enterprise", "department_acl", "private"] | None = None
    default_document_visibility: Literal["department", "enterprise"] | None = None
    default_document_owner_department_id: str | None = Field(default=None, min_length=1)
    config_scope_id: str | None = Field(default=None, min_length=1, max_length=128)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: KnowledgeBaseData


class KnowledgeBaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseListItemData]
    pagination: PaginationData


class KnowledgeBaseOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseOptionData]
    pagination: PaginationData


class FolderData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str
    parent_id: str | None = None
    name: str
    status: Literal["active", "disabled", "archived"]


class FolderOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
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


class FolderOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[FolderOptionData]
    pagination: PaginationData
