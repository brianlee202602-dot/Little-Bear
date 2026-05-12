"""索引模块。"""

from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import (
    DraftIndexChunk,
    DraftVectorPoint,
    IndexTarget,
    ReadyIndexVersion,
)
from app.modules.indexing.service import IndexingService, NoopVectorIndexWriter, VectorIndexWriter


def build_indexing_service(*args: Any, **kwargs: Any) -> IndexingService:
    from app.modules.indexing.runtime import build_indexing_service as _build_indexing_service

    return _build_indexing_service(*args, **kwargs)

__all__ = [
    "DraftIndexChunk",
    "DraftVectorPoint",
    "IndexTarget",
    "IndexingService",
    "IndexingServiceError",
    "NoopVectorIndexWriter",
    "ReadyIndexVersion",
    "VectorIndexWriter",
    "build_indexing_service",
]
