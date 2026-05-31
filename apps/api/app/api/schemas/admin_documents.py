"""管理后台文档 API 请求和响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginationData


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
    current_version_no: int | None = None


class DocumentListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    folder_name: str | None = None
    lifecycle_status: Literal["draft", "active", "archived", "deleted"]
    index_status: Literal["none", "indexing", "indexed", "index_failed", "blocked"]
    visibility: Literal["department", "enterprise"]
    owner_department_name: str | None = None
    current_version_no: int | None = None
    can_rebuild_index: bool = False


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
    data: list[DocumentListItemData]
    pagination: PaginationData


class AdminDocumentVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    version_no: int
    status: str


class AdminDocumentVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[AdminDocumentVersionData]
    pagination: PaginationData


class AdminChunkData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    text_preview: str
    page_start: int | None = None
    page_end: int | None = None
    status: str
    ordinal: int


class AdminChunkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[AdminChunkData]
    pagination: PaginationData


class AdminDocumentPreviewChunkData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    text: str
    text_preview: str
    page_start: int | None = None
    page_end: int | None = None
    status: str
    ordinal: int
    heading_path: str | None = None
    source_offsets: dict[str, Any] | None = None
    text_status: Literal["object", "preview_only", "object_unavailable"]


class AdminDocumentPreviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    chunks: list[AdminDocumentPreviewChunkData]


class AdminDocumentPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: AdminDocumentPreviewData
    pagination: PaginationData
