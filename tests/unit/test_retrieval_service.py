from __future__ import annotations

from app.modules.retrieval import (
    CandidateQualityGate,
    ReciprocalRankFusion,
    RerankResult,
    RetrievalCandidate,
    RetrievalModelCall,
)

ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_ID = "44444444-4444-4444-4444-444444444444"
DOC_VERSION_ID = "55555555-5555-5555-5555-555555555555"
INDEX_VERSION_ID = "88888888-8888-8888-8888-888888888888"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"


def test_reciprocal_rank_fusion_deduplicates_and_boosts_cross_source_hits() -> None:
    keyword_only = _candidate(chunk_id="chunk_keyword", source="keyword", rank=1, score=0.9)
    shared_keyword = _candidate(chunk_id="chunk_shared", source="keyword", rank=2, score=0.7)
    shared_vector = _candidate(chunk_id="chunk_shared", source="vector", rank=1, score=0.8)

    fused = ReciprocalRankFusion().fuse(
        (keyword_only, shared_keyword, shared_vector),
        limit=2,
        rrf_k=60,
    )

    assert [candidate.chunk_id for candidate in fused] == ["chunk_shared", "chunk_keyword"]
    assert fused[0].rank == 1
    assert fused[0].score > fused[1].score
    assert fused[0].source_score == 0.8


def test_reciprocal_rank_fusion_preserves_embedding_from_duplicate_vector_hit() -> None:
    shared_keyword = _candidate(
        chunk_id="chunk_shared",
        source="keyword",
        rank=1,
        score=0.9,
    )
    shared_vector = _candidate(
        chunk_id="chunk_shared",
        source="vector",
        rank=2,
        score=0.8,
        embedding=(0.1, 0.2),
    )

    fused = ReciprocalRankFusion().fuse(
        (shared_keyword, shared_vector),
        limit=1,
        rrf_k=60,
    )

    assert fused[0].chunk_id == "chunk_shared"
    assert fused[0].source_score == 0.9
    assert fused[0].embedding == (0.1, 0.2)


def test_reciprocal_rank_fusion_respects_query_and_source_weights() -> None:
    low_rank_vector = _candidate(
        chunk_id="chunk_vector",
        source="vector",
        rank=3,
        score=0.5,
        query_weight=1.2,
        source_weight=1.2,
    )
    high_rank_keyword = _candidate(
        chunk_id="chunk_keyword",
        source="keyword",
        rank=1,
        score=0.9,
        query_weight=0.5,
        source_weight=1.0,
    )

    fused = ReciprocalRankFusion().fuse(
        (low_rank_vector, high_rank_keyword),
        limit=2,
        rrf_k=60,
    )

    assert [candidate.chunk_id for candidate in fused] == ["chunk_vector", "chunk_keyword"]
    assert fused[0].matched_query is None
    assert fused[0].score > fused[1].score


def test_candidate_quality_gate_blocks_low_source_score_without_successful_rerank() -> None:
    candidate = _candidate(
        chunk_id="chunk_low",
        source="vector",
        rank=1,
        score=0.02,
        source_score=0.005,
    )

    result = CandidateQualityGate(
        min_fusion_score=0.01,
        min_source_score=0.02,
    ).evaluate((candidate,), rerank_result=RerankResult(candidates=(candidate,)))

    assert result.accepted_candidates == ()
    assert result.rejected_count == 1
    assert result.quality_reason == "retrieval_quality_too_low"


def test_candidate_quality_gate_keeps_successful_rerank_results() -> None:
    candidate = _candidate(
        chunk_id="chunk_reranked",
        source="vector",
        rank=1,
        score=0.001,
        source_score=0.001,
    )
    model_call = RetrievalModelCall(
        model_type="rerank",
        model_name="bge",
        model_version=None,
        model_route_hash="route",
        status="success",
        degraded=False,
        latency_ms=1,
    )

    result = CandidateQualityGate(
        min_fusion_score=0.01,
        min_source_score=0.02,
    ).evaluate(
        (candidate,),
        rerank_result=RerankResult(candidates=(candidate,), model_call=model_call),
    )

    assert result.accepted_candidates == (candidate,)
    assert result.quality_reason is None


def _candidate(
    *,
    chunk_id: str,
    source: str,
    rank: int,
    score: float,
    source_score: float | None = None,
    query_weight: float = 1.0,
    source_weight: float = 1.0,
    embedding: tuple[float, ...] | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        source=source,  # type: ignore[arg-type]
        enterprise_id=ENTERPRISE_ID,
        kb_id=KB_ID,
        document_id=DOC_ID,
        document_version_id=DOC_VERSION_ID,
        chunk_id=chunk_id,
        title=chunk_id,
        owner_department_id=DEPARTMENT_ID,
        visibility="department",
        document_lifecycle_status="active",
        document_index_status="indexed",
        chunk_status="active",
        visibility_state="active",
        index_version_id=INDEX_VERSION_ID,
        indexed_permission_version=42,
        page_start=1,
        page_end=1,
        rank=rank,
        score=score,
        source_score=source_score if source_score is not None else score,
        query_weight=query_weight,
        source_weight=source_weight,
        embedding=embedding,
    )
