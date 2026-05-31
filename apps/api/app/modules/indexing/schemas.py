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
class VectorPayloadUpdate:
    collection_name: str
    vector_id: str
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


@dataclass(frozen=True)
class IndexCollectionHealth:
    collection_name: str
    expected_dimension: int | None
    qdrant_reachable: bool
    qdrant_exists: bool | None
    qdrant_status: str | None
    qdrant_vector_size: int | None
    qdrant_points_count: int | None
    db_index_version_count: int
    active_index_version_count: int
    pending_delete_index_version_count: int
    failed_index_version_count: int
    active_ref_count: int
    draft_ref_count: int
    deleted_ref_count: int
    pending_delete_ref_count: int
    active_ref_mismatch_count: int
    issues: tuple[str, ...]


@dataclass(frozen=True)
class IndexCollectionHealthList:
    items: tuple[IndexCollectionHealth, ...]
    total: int


@dataclass(frozen=True)
class IndexCollectionSnapshot:
    collection_name: str
    name: str
    size: int | None = None
    creation_time: str | None = None
    checksum: str | None = None


@dataclass(frozen=True)
class IndexCollectionSnapshotList:
    items: tuple[IndexCollectionSnapshot, ...]
    total: int


@dataclass(frozen=True)
class IndexCollectionOperationResult:
    collection_name: str
    operation: str
    accepted: bool
    result: bool | None = None
