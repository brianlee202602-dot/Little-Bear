"""管理后台索引运维 API 请求和响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginationData


class IndexVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_version_id: str
    embedding_model: str
    model_version: str
    dimension: int
    collection_name: str
    status: Literal["draft", "ready", "active", "archived", "pending_delete", "failed"]
    chunk_count: int
    created_at: datetime | None = None
    activated_at: datetime | None = None


class IndexVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[IndexVersionData]
    pagination: PaginationData


class IndexCollectionHealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str
    expected_dimension: int | None = None
    qdrant_reachable: bool
    qdrant_exists: bool | None = None
    qdrant_status: str | None = None
    qdrant_vector_size: int | None = None
    qdrant_points_count: int | None = None
    db_index_version_count: int
    active_index_version_count: int
    pending_delete_index_version_count: int
    failed_index_version_count: int
    active_ref_count: int
    draft_ref_count: int
    deleted_ref_count: int
    pending_delete_ref_count: int
    active_ref_mismatch_count: int
    issues: list[str]


class IndexHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[IndexCollectionHealthData]
    pagination: PaginationData


class IndexCollectionSnapshotData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str
    name: str
    size: int | None = None
    creation_time: str | None = None
    checksum: str | None = None


class IndexCollectionSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: IndexCollectionSnapshotData


class IndexCollectionSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[IndexCollectionSnapshotData]
    pagination: PaginationData


class IndexCollectionSnapshotRecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1, max_length=2048)
    priority: Literal["Snapshot", "Replica"] | None = "Snapshot"
    checksum: str | None = Field(default=None, min_length=1, max_length=128)


class IndexCollectionOperationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str
    operation: Literal["snapshot_recover"]
    accepted: bool
    result: bool | None = None


class IndexCollectionOperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: IndexCollectionOperationData


class IndexJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kb_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=200)


class IndexVersionCleanupJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_version_ids: list[str] = Field(min_length=1, max_length=200)
