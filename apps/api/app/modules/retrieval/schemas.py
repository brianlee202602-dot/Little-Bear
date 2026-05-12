"""Retrieval 模块内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RetrievalSource = Literal["keyword", "vector"]


@dataclass(frozen=True)
class RetrievalCandidate:
    source: RetrievalSource
    enterprise_id: str
    kb_id: str
    document_id: str
    document_version_id: str
    chunk_id: str
    title: str
    owner_department_id: str
    visibility: str
    document_lifecycle_status: str
    document_index_status: str
    chunk_status: str
    visibility_state: str
    index_version_id: str
    indexed_permission_version: int
    page_start: int | None
    page_end: int | None
    rank: int
    score: float


@dataclass(frozen=True)
class VectorSearchResult:
    candidates: tuple[RetrievalCandidate, ...]
    degraded: bool = False
    degrade_reason: str | None = None
