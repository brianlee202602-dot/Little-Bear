"""普通用户知识库浏览 API 模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.api.schemas.query import CitationData


class PaginationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    page_size: int
    total: int


class KnowledgeBaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: Literal["active", "disabled", "archived"]
    owner_department_id: str
    kb_visibility: Literal["enterprise", "department_acl", "private"]
    default_document_visibility: Literal["department", "enterprise"]
    default_document_owner_department_id: str
    config_scope_id: str | None = None
    policy_version: int = 1


class KnowledgeBaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[KnowledgeBaseData]
    pagination: PaginationData


class DocumentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kb_id: str
    folder_id: str | None = None
    title: str
    lifecycle_status: str
    index_status: str
    owner_department_id: str
    visibility: Literal["department", "enterprise"]
    current_version_id: str | None = None


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[DocumentData]
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


class ChunkData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    text_preview: str
    page_start: int | None = None
    page_end: int | None = None
    status: str


class ChunkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[ChunkData]


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


class DocumentPreviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    preview: str
    citations: list[CitationData]


class DocumentPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DocumentPreviewData
