"""Indexing Service 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexTarget:
    enterprise_id: str
    kb_id: str
    document_id: str
    document_version_id: str
    created_by: str | None
    chunk_count: int
    permission_snapshot_hash: str


@dataclass(frozen=True)
class DraftIndexChunk:
    enterprise_id: str
    kb_id: str
    chunk_id: str
    document_id: str
    document_version_id: str
    index_version_id: str
    title: str
    collection_name: str
    text: str
    owner_department_id: str
    visibility: str
    indexed_permission_version: int
    chunk_content_hash: str
    index_payload_hash: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class DraftVectorPoint:
    collection_name: str
    vector_id: str
    text: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ReadyIndexVersion:
    enterprise_id: str
    kb_id: str
    document_id: str
    document_version_id: str
    index_version_id: str
    collection_name: str
    dimension: int
    chunk_count: int
    permission_version: int
