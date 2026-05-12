from __future__ import annotations

from app.modules.retrieval import ReciprocalRankFusion, RetrievalCandidate

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


def _candidate(
    *,
    chunk_id: str,
    source: str,
    rank: int,
    score: float,
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
    )
