"""普通用户知识库浏览内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AccessibleKnowledgeBase:
    id: str
    name: str
    status: str


@dataclass(frozen=True)
class AccessibleKnowledgeBaseList:
    items: list[AccessibleKnowledgeBase]
    total: int


@dataclass(frozen=True)
class AccessibleDocument:
    id: str
    title: str
    lifecycle_status: str
    index_status: str
    updated_at: datetime | None
    can_view: bool = True
    can_cite: bool = True


@dataclass(frozen=True)
class AccessibleDocumentListItem:
    id: str
    title: str
    lifecycle_status: str
    index_status: str
    updated_at: datetime | None
    can_view: bool = True
    can_cite: bool = True


@dataclass(frozen=True)
class AccessibleDocumentList:
    items: list[AccessibleDocumentListItem]
    total: int


@dataclass(frozen=True)
class AccessibleDocumentVersion:
    id: str
    document_id: str
    version_no: int
    status: str


@dataclass(frozen=True)
class AccessibleDocumentVersionList:
    items: list[AccessibleDocumentVersion]
    total: int


@dataclass(frozen=True)
class AccessibleChunk:
    id: str
    document_id: str
    document_version_id: str
    text_preview: str
    page_start: int | None
    page_end: int | None
    status: str
    ordinal: int


@dataclass(frozen=True)
class AccessibleChunkList:
    items: list[AccessibleChunk]
    total: int


@dataclass(frozen=True)
class AccessibleCitationSource:
    source_id: str
    doc_id: str
    document_version_id: str
    title: str
    text: str
    text_preview: str
    page_start: int | None
    page_end: int | None
    ordinal: int
    heading_path: str | None
    source_offsets: dict[str, Any] | None
    text_status: str

