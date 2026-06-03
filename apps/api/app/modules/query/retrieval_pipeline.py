"""Retrieval gating and rerank pipeline for query workflows."""

from __future__ import annotations

from collections import Counter

from app.modules.permissions import CandidateMetadata, PermissionService
from app.modules.permissions.schemas import PermissionContext
from app.modules.query.errors import QueryServiceError
from app.modules.query.repository import QueryRepository
from app.modules.query.schemas import (
    QueryAllowedCandidate,
    QueryCandidateGateDiagnostics,
    QueryCandidateGateResult,
)
from app.modules.query.utils import (
    _candidate_rerank_text,
    _citation_from_candidate,
)
from app.modules.retrieval import (
    CandidateReranker,
    NoopCandidateReranker,
    RerankResult,
    RetrievalCandidate,
)
from sqlalchemy.orm import Session


class QueryRetrievalPipeline:
    """Apply permission gates and optional reranking to retrieval candidates."""

    def __init__(
        self,
        *,
        permission_service: PermissionService,
        candidate_reranker: CandidateReranker,
        repository: QueryRepository | None = None,
    ) -> None:
        self._permission_service = permission_service
        self._candidate_reranker = candidate_reranker
        self._repository = repository or QueryRepository()

    def gate_candidates(
        self,
        session: Session,
        context: PermissionContext,
        candidates: tuple[RetrievalCandidate, ...],
        *,
        allowed_kb_ids: tuple[str, ...],
        active_index_version_ids: tuple[str, ...],
        limit: int,
    ) -> tuple[QueryAllowedCandidate, ...]:
        return self.gate_candidates_with_diagnostics(
            session,
            context,
            candidates,
            allowed_kb_ids=allowed_kb_ids,
            active_index_version_ids=active_index_version_ids,
            limit=limit,
        ).allowed_candidates

    def gate_candidates_with_diagnostics(
        self,
        session: Session,
        context: PermissionContext,
        candidates: tuple[RetrievalCandidate, ...],
        *,
        allowed_kb_ids: tuple[str, ...],
        active_index_version_ids: tuple[str, ...],
        limit: int,
    ) -> QueryCandidateGateResult:
        allowed: list[QueryAllowedCandidate] = []
        rejection_reasons: Counter[str] = Counter()
        missing_metadata_count = 0
        rejected_count = 0
        current_facts = self._repository.load_current_candidate_facts(session, candidates)
        for candidate in candidates:
            facts = current_facts.get((candidate.chunk_id, candidate.index_version_id))
            if facts is None:
                missing_metadata_count += 1
                continue
            candidate = facts.candidate
            gate_result = self._permission_service.gate_candidate(
                context,
                CandidateMetadata(
                    enterprise_id=candidate.enterprise_id,
                    kb_id=candidate.kb_id,
                    document_id=candidate.document_id,
                    chunk_id=candidate.chunk_id,
                    owner_department_id=candidate.owner_department_id,
                    visibility=candidate.visibility,
                    document_lifecycle_status=candidate.document_lifecycle_status,
                    document_index_status=candidate.document_index_status,
                    chunk_status=candidate.chunk_status,
                    visibility_state=candidate.visibility_state,
                    index_version_id=candidate.index_version_id,
                    indexed_permission_version=candidate.indexed_permission_version,
                    access_blocked=facts.access_blocked,
                ),
                allowed_kb_ids=allowed_kb_ids,
                active_index_version_ids=active_index_version_ids,
            )
            if not gate_result.allowed:
                rejected_count += 1
                rejection_reasons[gate_result.error_code or gate_result.reason] += 1
                continue
            allowed.append(
                QueryAllowedCandidate(
                    candidate=candidate,
                    citation=_citation_from_candidate(candidate),
                )
            )
            if len(allowed) >= limit:
                break
        return QueryCandidateGateResult(
            allowed_candidates=tuple(allowed),
            diagnostics=QueryCandidateGateDiagnostics(
                input_count=len(candidates),
                allowed_count=len(allowed),
                rejected_count=rejected_count,
                missing_metadata_count=missing_metadata_count,
                rejection_reasons=dict(rejection_reasons),
            ),
        )

    def expand_context_candidates(
        self,
        session: Session,
        context: PermissionContext,
        allowed_candidates: tuple[QueryAllowedCandidate, ...],
        *,
        allowed_kb_ids: tuple[str, ...],
        active_index_version_ids: tuple[str, ...],
        neighbor_window: int,
        limit: int,
    ) -> tuple[QueryAllowedCandidate, ...]:
        if not allowed_candidates or neighbor_window <= 0:
            return allowed_candidates
        primary_candidates = tuple(item.candidate for item in allowed_candidates)
        try:
            neighbor_candidates = self._repository.load_neighbor_candidates(
                session,
                candidates=primary_candidates,
                window=neighbor_window,
            )
        except QueryServiceError:
            return allowed_candidates
        if not neighbor_candidates:
            return allowed_candidates
        remaining_limit = max(limit - len(allowed_candidates), 0)
        if remaining_limit <= 0:
            return allowed_candidates
        gated_neighbors = self.gate_candidates(
            session,
            context,
            neighbor_candidates,
            allowed_kb_ids=allowed_kb_ids,
            active_index_version_ids=active_index_version_ids,
            limit=remaining_limit,
        )
        return _merge_allowed_candidates(allowed_candidates, gated_neighbors)

    def rerank_allowed_candidates(
        self,
        session: Session,
        *,
        query_text: str,
        allowed_candidates: tuple[QueryAllowedCandidate, ...],
        top_k: int,
    ) -> RerankResult:
        candidates = tuple(allowed.candidate for allowed in allowed_candidates)
        if isinstance(self._candidate_reranker, NoopCandidateReranker):
            return self._candidate_reranker.rerank(
                query_text=query_text,
                candidates=candidates,
                texts=(),
                top_k=top_k,
            )
        try:
            texts_by_chunk_id = self._repository.load_rerank_texts(
                session,
                chunk_ids=tuple(candidate.chunk_id for candidate in candidates),
            )
        except QueryServiceError as exc:
            return RerankResult(
                candidates=candidates[: max(top_k, 0)],
                degraded=True,
                degrade_reason=exc.error_code,
            )
        texts = tuple(
            _candidate_rerank_text(candidate, texts_by_chunk_id.get(candidate.chunk_id))
            for candidate in candidates
        )
        return self._candidate_reranker.rerank(
            query_text=query_text,
            candidates=candidates,
            texts=texts,
            top_k=top_k,
        )


def _merge_allowed_candidates(
    primary: tuple[QueryAllowedCandidate, ...],
    expanded: tuple[QueryAllowedCandidate, ...],
) -> tuple[QueryAllowedCandidate, ...]:
    merged: list[QueryAllowedCandidate] = []
    seen: set[str] = set()
    for item in (*primary, *expanded):
        if item.candidate.chunk_id in seen:
            continue
        seen.add(item.candidate.chunk_id)
        merged.append(item)
    return tuple(merged)
