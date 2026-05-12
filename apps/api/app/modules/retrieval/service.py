"""Retrieval 编排中的可替换组件。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Protocol

from app.modules.permissions.schemas import PermissionFilter
from app.modules.retrieval.schemas import RetrievalCandidate, VectorSearchResult

DEFAULT_RRF_K = 60


class VectorRetriever(Protocol):
    """向量召回端口。

    P0 查询链路先依赖该端口，不在 Query Service 内直接绑定 Qdrant 或模型 SDK。
    """

    def search(
        self,
        *,
        query_text: str,
        permission_filter: PermissionFilter,
        collection_names: tuple[str, ...],
        top_k: int,
    ) -> VectorSearchResult:
        ...


class UnavailableVectorRetriever:
    """默认向量召回实现：显式降级到关键词召回。"""

    def __init__(self, *, reason: str = "vector_retriever_unavailable") -> None:
        self.reason = reason

    def search(
        self,
        *,
        query_text: str,
        permission_filter: PermissionFilter,
        collection_names: tuple[str, ...],
        top_k: int,
    ) -> VectorSearchResult:
        return VectorSearchResult(candidates=(), degraded=True, degrade_reason=self.reason)


class ReciprocalRankFusion:
    """Reciprocal Rank Fusion，按 chunk 去重后融合多路召回。"""

    def fuse(
        self,
        candidates: tuple[RetrievalCandidate, ...],
        *,
        limit: int,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> tuple[RetrievalCandidate, ...]:
        if not candidates:
            return ()

        scores: dict[str, float] = defaultdict(float)
        best_candidate: dict[str, RetrievalCandidate] = {}
        best_raw_score: dict[str, float] = defaultdict(float)
        for index, candidate in enumerate(candidates, start=1):
            rank = candidate.rank if candidate.rank > 0 else index
            scores[candidate.chunk_id] += 1.0 / (max(rrf_k, 1) + rank)
            if candidate.chunk_id not in best_candidate or candidate.score > best_raw_score[
                candidate.chunk_id
            ]:
                best_candidate[candidate.chunk_id] = candidate
                best_raw_score[candidate.chunk_id] = candidate.score

        fused = [
            replace(best_candidate[chunk_id], score=score)
            for chunk_id, score in sorted(
                scores.items(),
                key=lambda item: (-item[1], best_candidate[item[0]].rank),
            )
        ]
        return tuple(
            replace(candidate, rank=rank)
            for rank, candidate in enumerate(fused[: max(limit, 0)], start=1)
        )
