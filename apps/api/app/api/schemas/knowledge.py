"""普通用户知识库浏览 API 模型。"""

from __future__ import annotations

from typing import Literal

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
    default_visibility: Literal["department", "enterprise"]
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
