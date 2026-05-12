"""导入任务 API 请求和响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.config import PaginationData


class DocumentImportItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=256)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: Literal["url", "metadata_batch"]
    owner_department_id: str | None = Field(default=None, min_length=1)
    visibility: Literal["department", "enterprise"] | None = None
    folder_id: str | None = Field(default=None, min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    items: list[DocumentImportItemData] = Field(min_length=1)


class ImportJobPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["cancelled"]


class ImportJobData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str | None = None
    status: Literal[
        "queued",
        "running",
        "retrying",
        "partial_success",
        "success",
        "failed",
        "cancelled",
    ]
    stage: Literal[
        "validate",
        "parse",
        "clean",
        "chunk",
        "embed",
        "index",
        "publish",
        "cleanup",
        "finished",
    ]
    document_ids: list[str] = Field(default_factory=list)
    error_summary: str | None = None


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: ImportJobData


class ImportJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[ImportJobData]
    pagination: PaginationData
