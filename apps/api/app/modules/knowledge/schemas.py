"""普通用户知识库浏览内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessibleKnowledgeBase:
    id: str
    name: str
    status: str
    owner_department_id: str
    default_visibility: str
    config_scope_id: str | None
    policy_version: int


@dataclass(frozen=True)
class AccessibleKnowledgeBaseList:
    items: list[AccessibleKnowledgeBase]
    total: int


@dataclass(frozen=True)
class AccessibleDocument:
    id: str
    kb_id: str
    folder_id: str | None
    title: str
    lifecycle_status: str
    index_status: str
    owner_department_id: str
    visibility: str
    current_version_id: str | None


@dataclass(frozen=True)
class AccessibleDocumentList:
    items: list[AccessibleDocument]
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
