"""向量存储适配器边界 DTO 与协议。

该文件只定义基础设施适配层自己的输入输出类型，避免 Qdrant adapter 直接依赖
permissions、retrieval、indexing 或 models 模块的内部数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class VectorStoreEmbeddingError(Exception):
    """向量化 provider 调用失败。"""


class VectorStoreEmbeddingClient(Protocol):
    def embed_query(self, query_text: str) -> list[float]:
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class VectorStoreSearchFilter:
    payload_filter: dict[str, Any]


@dataclass(frozen=True)
class VectorStoreCandidate:
    source: str
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
class VectorStoreSearchResult:
    candidates: tuple[VectorStoreCandidate, ...]
    degraded: bool = False
    degrade_reason: str | None = None


@dataclass(frozen=True)
class VectorStoreDraftPoint:
    collection_name: str
    vector_id: str
    text: str
    payload: dict[str, object]


@dataclass(frozen=True)
class VectorStorePayloadUpdate:
    collection_name: str
    vector_id: str
    payload: dict[str, object]
