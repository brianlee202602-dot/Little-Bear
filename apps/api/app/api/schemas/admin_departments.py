"""管理后台部门 API 请求和响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginationData


class DepartmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    status: Literal["active", "disabled", "deleted"]
    is_primary: bool = False
    is_default: bool = False


class DepartmentListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "deleted"]
    is_default: bool = False


class DepartmentOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "deleted"]
    is_default: bool = False


class DepartmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)


class DepartmentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["active", "disabled"] | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DepartmentData


class DepartmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentListItemData]
    pagination: PaginationData


class DepartmentOptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DepartmentOptionData]
    pagination: PaginationData
