"""Retrieval gating and rerank pipeline for query workflows."""

from __future__ import annotations

from app.modules.permissions import CandidateMetadata, PermissionService
from app.modules.permissions.schemas import PermissionContext
from app.modules.query.errors import QueryServiceError
from app.modules.query.repository import QueryRepository
from app.modules.query.schemas import QueryAllowedCandidate
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
        allowed: list[QueryAllowedCandidate] = []
        current_facts = self._repository.load_current_candidate_facts(session, candidates)
        for candidate in candidates:
            facts = current_facts.get((candidate.chunk_id, candidate.index_version_id))
            if facts is None:
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
                continue
            allowed.append(
                QueryAllowedCandidate(
                    candidate=candidate,
                    citation=_citation_from_candidate(candidate),
                )
            )
            if len(allowed) >= limit:
                break
        return tuple(allowed)

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
