"""权限管理 API 模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourcePermissionPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: Literal["department", "enterprise"]
    owner_department_id: str | None = Field(default=None, min_length=1)


class KnowledgeBaseAccessRulePutData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["department", "user", "role"]
    subject_id: str = Field(min_length=1)
    permission: Literal["discover", "query", "manage"]


class KnowledgeBasePermissionPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str = Field(min_length=1)
    access_rules: list[KnowledgeBaseAccessRulePutData] = Field(default_factory=list)


class PermissionPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: Literal["document"]
    resource_id: str
    visibility: Literal["department", "enterprise"]
    permission_version: int


class KnowledgeBaseAccessRuleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["department", "user", "role"]
    subject_id: str
    permission: Literal["discover", "query", "manage"]


class KnowledgeBasePermissionPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: Literal["knowledge_base"]
    resource_id: str
    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str
    access_rules: list[KnowledgeBaseAccessRuleData]
    permission_version: int


class PermissionPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: PermissionPolicyData


class KnowledgeBasePermissionPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: KnowledgeBasePermissionPolicyData
