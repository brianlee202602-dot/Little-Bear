"""索引模块。"""

from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.ops_service import IndexOpsService
from app.modules.indexing.schemas import (
    DraftIndexChunk,
    DraftVectorPoint,
    IndexCollectionHealth,
    IndexCollectionHealthList,
    IndexCollectionOperationResult,
    IndexCollectionSnapshot,
    IndexCollectionSnapshotList,
    IndexTarget,
    ReadyIndexVersion,
)
from app.modules.indexing.service import IndexingService, NoopVectorIndexWriter, VectorIndexWriter


def build_indexing_service(*args: Any, **kwargs: Any) -> IndexingService:
    from app.modules.indexing.runtime import build_indexing_service as _build_indexing_service

    return _build_indexing_service(*args, **kwargs)


def build_index_ops_service(*args: Any, **kwargs: Any) -> IndexOpsService:
    from app.modules.indexing.ops_runtime import build_index_ops_service as _build_index_ops_service

    return _build_index_ops_service(*args, **kwargs)


__all__ = [
    "DraftIndexChunk",
    "DraftVectorPoint",
    "IndexCollectionHealth",
    "IndexCollectionHealthList",
    "IndexCollectionOperationResult",
    "IndexCollectionSnapshot",
    "IndexCollectionSnapshotList",
    "IndexOpsService",
    "IndexTarget",
    "IndexingService",
    "IndexingServiceError",
    "NoopVectorIndexWriter",
    "ReadyIndexVersion",
    "VectorIndexWriter",
    "build_index_ops_service",
    "build_indexing_service",
]
