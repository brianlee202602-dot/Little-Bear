"""权限管理 API 模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourcePermissionPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: Literal["department", "enterprise"]
    owner_department_id: str | None = Field(default=None, min_length=1)


class PermissionPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: Literal["knowledge_base", "document"]
    resource_id: str
    visibility: Literal["department", "enterprise"]
    permission_version: int


class PermissionPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: PermissionPolicyData
