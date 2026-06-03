from __future__ import annotations

from app.modules.permissions.schemas import (
    CandidateGateResult,
    CandidateMetadata,
    PermissionContext,
)
from app.modules.query.retrieval_pipeline import QueryRetrievalPipeline
from app.modules.query.schemas import _CurrentCandidateFacts
from app.modules.retrieval import NoopCandidateReranker, RetrievalCandidate


def test_gate_candidates_with_diagnostics_counts_denials_and_missing_metadata() -> None:
    allowed = _candidate("chunk_allowed")
    denied = _candidate("chunk_denied")
    missing = _candidate("chunk_missing")
    pipeline = QueryRetrievalPipeline(
        permission_service=_PermissionService(),
        candidate_reranker=NoopCandidateReranker(),
        repository=_Repository(
            {
                (allowed.chunk_id, allowed.index_version_id): _CurrentCandidateFacts(
                    candidate=allowed,
                    access_blocked=False,
                ),
                (denied.chunk_id, denied.index_version_id): _CurrentCandidateFacts(
                    candidate=denied,
                    access_blocked=False,
                ),
            }
        ),
    )

    result = pipeline.gate_candidates_with_diagnostics(
        None,
        _permission_context(),
        (allowed, denied, missing),
        allowed_kb_ids=("kb",),
        active_index_version_ids=("index",),
        limit=10,
    )

    assert [item.candidate.chunk_id for item in result.allowed_candidates] == ["chunk_allowed"]
    assert result.diagnostics.input_count == 3
    assert result.diagnostics.allowed_count == 1
    assert result.diagnostics.rejected_count == 1
    assert result.diagnostics.missing_metadata_count == 1
    assert result.diagnostics.rejection_reasons == {"PERM_DENIED": 1}


class _PermissionService:
    def gate_candidate(
        self,
        _context: PermissionContext,
        candidate: CandidateMetadata,
        **_kwargs: object,
    ) -> CandidateGateResult:
        if candidate.chunk_id == "chunk_denied":
            return CandidateGateResult(
                allowed=False,
                reason="candidate owner department is not accessible",
                error_code="PERM_DENIED",
            )
        return CandidateGateResult(allowed=True, reason="enterprise_visible")


class _Repository:
    def __init__(self, facts: dict[tuple[str, str], _CurrentCandidateFacts]) -> None:
        self._facts = facts

    def load_current_candidate_facts(
        self,
        _session: object,
        _candidates: tuple[RetrievalCandidate, ...],
    ) -> dict[tuple[str, str], _CurrentCandidateFacts]:
        return self._facts


def _permission_context() -> PermissionContext:
    return PermissionContext(
        enterprise_id="enterprise",
        user_id="user",
        username="alice",
        status="active",
        department_ids=("dept",),
        departments=(),
        roles=(),
        scopes=("rag:query",),
        permission_version=1,
        org_version=1,
        permission_filter_hash="hash",
    )


def _candidate(chunk_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        source="keyword",
        enterprise_id="enterprise",
        kb_id="kb",
        document_id=f"doc_{chunk_id}",
        document_version_id=f"version_{chunk_id}",
        chunk_id=chunk_id,
        title="员工手册",
        owner_department_id="dept",
        visibility="enterprise",
        document_lifecycle_status="active",
        document_index_status="indexed",
        chunk_status="active",
        visibility_state="active",
        index_version_id="index",
        indexed_permission_version=1,
        page_start=1,
        page_end=1,
        rank=1,
        score=0.9,
        source_score=0.9,
    )
