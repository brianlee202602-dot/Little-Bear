"""普通用户知识库浏览 API 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.api.schemas.common import PaginationData


class KnowledgeBaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]


class KnowledgeBaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseData]
    pagination: PaginationData


class DocumentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    lifecycle_status: str
    index_status: str
    updated_at: datetime | None = None
    can_view: bool = True
    can_cite: bool = True


class DocumentListItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    lifecycle_status: str
    index_status: str
    updated_at: datetime | None = None
    can_view: bool = True
    can_cite: bool = True


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DocumentListItemData]
    pagination: PaginationData


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DocumentData


class DocumentVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    version_no: int
    status: str


class DocumentVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DocumentVersionData]
    pagination: PaginationData


class ChunkData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    text_preview: str
    page_start: int | None = None
    page_end: int | None = None
    status: str
    ordinal: int


class ChunkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[ChunkData]
    pagination: PaginationData


class CitationSourceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    doc_id: str
    document_version_id: str
    title: str
    text: str
    text_preview: str
    page_start: int | None = None
    page_end: int | None = None
    ordinal: int
    heading_path: str | None = None
    source_offsets: dict[str, Any] | None = None
    text_status: Literal["object", "preview_only", "object_unavailable"]


class CitationSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: CitationSourceData
