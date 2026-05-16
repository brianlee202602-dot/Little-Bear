"""Retrieval 编排中的可替换组件。"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import replace
from typing import Protocol

from app.modules.models import ModelClientError, RerankClient
from app.modules.permissions.schemas import PermissionFilter
from app.modules.retrieval.schemas import (
    RerankResult,
    RetrievalCandidate,
    RetrievalModelCall,
    VectorSearchResult,
)
from app.shared.json_utils import stable_json_hash

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


class CandidateReranker(Protocol):
    """候选精排端口。"""

    def rerank(
        self,
        *,
        query_text: str,
        candidates: tuple[RetrievalCandidate, ...],
        texts: tuple[str, ...],
        top_k: int,
    ) -> RerankResult:
        ...


class NoopCandidateReranker:
    """默认精排实现：保持融合排序。"""

    def rerank(
        self,
        *,
        query_text: str,
        candidates: tuple[RetrievalCandidate, ...],
        texts: tuple[str, ...],
        top_k: int,
    ) -> RerankResult:
        return RerankResult(candidates=candidates[: max(top_k, 0)])


class ModelCandidateReranker:
    """使用外部 rerank provider 对权限 gate 后的候选重排。"""

    def __init__(self, *, rerank_client: RerankClient) -> None:
        self.rerank_client = rerank_client

    def rerank(
        self,
        *,
        query_text: str,
        candidates: tuple[RetrievalCandidate, ...],
        texts: tuple[str, ...],
        top_k: int,
    ) -> RerankResult:
        limit = max(top_k, 0)
        if not candidates or limit <= 0:
            return RerankResult(candidates=())
        if len(candidates) != len(texts):
            return RerankResult(
                candidates=candidates[:limit],
                degraded=True,
                degrade_reason="rerank_input_mismatch",
            )
        started_at = time.monotonic()
        try:
            result = self.rerank_client.rerank(
                query_text=query_text,
                texts=texts,
                top_k=limit,
            )
        except ModelClientError as exc:
            return RerankResult(
                candidates=candidates[:limit],
                degraded=True,
                degrade_reason=exc.error_code,
                model_call=_failed_model_call(
                    self.rerank_client,
                    query_text=query_text,
                    texts=texts,
                    error_code=exc.error_code,
                    latency_ms=_elapsed_ms(started_at),
                ),
            )
        reranked: list[RetrievalCandidate] = []
        used_indexes: set[int] = set()
        for rank, item in enumerate(result.items, start=1):
            if item.index < 0 or item.index >= len(candidates) or item.index in used_indexes:
                continue
            used_indexes.add(item.index)
            reranked.append(replace(candidates[item.index], rank=rank, score=item.score))
            if len(reranked) >= limit:
                break
        if len(reranked) < limit:
            for index, candidate in enumerate(candidates):
                if index in used_indexes:
                    continue
                reranked.append(replace(candidate, rank=len(reranked) + 1))
                if len(reranked) >= limit:
                    break
        return RerankResult(
            candidates=tuple(reranked),
            model_call=RetrievalModelCall(
                model_type="rerank",
                model_name=result.model_name,
                model_version=None,
                model_route_hash=result.model_route_hash,
                status="success",
                degraded=False,
                latency_ms=result.latency_ms,
                input_hash=result.input_hash,
                output_hash=result.output_hash,
            ),
        )


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


def _failed_model_call(
    rerank_client: RerankClient,
    *,
    query_text: str,
    texts: tuple[str, ...],
    error_code: str,
    latency_ms: int,
) -> RetrievalModelCall:
    model_name = _client_attr(rerank_client, "model", default="unknown")
    model_route_hash = _client_attr(rerank_client, "model_route_hash", default=None)
    if model_route_hash is None:
        model_route_hash = stable_json_hash(
            {
                "base_url": _client_attr(rerank_client, "base_url", default=None),
                "path": _client_attr(rerank_client, "path", default=None),
                "model": model_name,
            }
        )
    return RetrievalModelCall(
        model_type="rerank",
        model_name=model_name,
        model_version=None,
        model_route_hash=model_route_hash,
        status="failed",
        degraded=True,
        latency_ms=latency_ms,
        input_hash=stable_json_hash({"query": query_text, "texts": list(texts)}),
        error_code=error_code,
    )


def _client_attr(client: object, name: str, *, default: str | None) -> str | None:
    value = getattr(client, name, default)
    return value if isinstance(value, str) and value else default


def _elapsed_ms(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)
