"""Facade for query workflows."""

from __future__ import annotations

from typing import Any

from app.modules.answer import AnswerService
from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.context.schemas import QueryContext
from app.modules.context.service import ContextBuilder
from app.modules.permissions import PermissionService
from app.modules.permissions.schemas import PermissionContext, PermissionFilter
from app.modules.query import citation_validator, degrade_policy
from app.modules.query.log_writer import QueryLogWriter
from app.modules.query.orchestrator import QueryOrchestrator
from app.modules.query.repository import QueryRepository
from app.modules.query.retrieval_pipeline import QueryRetrievalPipeline
from app.modules.query.schemas import (
    ActiveIndexVersion,
    QueryAllowedCandidate,
    QueryCitation,
    QueryFilterClause,
    QueryResult,
    QueryStreamPlan,
    _CitationValidationResult,
    _CurrentCandidateFacts,
    _QueryAuditEvent,
)
from app.modules.query.utils import (
    DEFAULT_RERANK_MIN_SCORE,
    MAX_QUERY_LENGTH,
    SUPPORTED_FILTERS,
    _allowed_candidates_from_retrieval,
    _apply_relevance_gate,
    _build_filter_clause,
    _candidate_from_mapping,
    _candidate_rerank_text,
    _citation_from_candidate,
    _confidence,
    _database_error,
    _elapsed_ms,
    _index_version_hash,
    _normalize_ids,
    _normalize_query,
    _optional_int,
    _query_hash,
    _string_list,
    _truncate_error_message,
)
from app.modules.retrieval import (
    CandidateReranker,
    NoopCandidateReranker,
    ReciprocalRankFusion,
    RerankResult,
    RetrievalCandidate,
    RetrievalModelCall,
    UnavailableVectorRetriever,
    VectorRetriever,
)
from sqlalchemy.orm import Session


class QueryService:
    """Route-facing query service.

    Public query orchestration remains compatible with the original implementation,
    while SQL reads, permission gating/rerank, and log writes are delegated to
    narrower services.
    """

    def __init__(
        self,
        *,
        permission_service: PermissionService | None = None,
        vector_retriever: VectorRetriever | None = None,
        candidate_reranker: CandidateReranker | None = None,
        rerank_input_top_k: int = 20,
        rerank_min_score: float = DEFAULT_RERANK_MIN_SCORE,
        fusion_service: ReciprocalRankFusion | None = None,
        context_builder: ContextBuilder | None = None,
        answer_service: AnswerService | None = None,
        repository: QueryRepository | None = None,
        log_writer: QueryLogWriter | None = None,
    ) -> None:
        self.permission_service = permission_service or PermissionService()
        self.vector_retriever = vector_retriever or UnavailableVectorRetriever()
        self.candidate_reranker = candidate_reranker or NoopCandidateReranker()
        self.rerank_input_top_k = max(rerank_input_top_k, 1)
        self.rerank_min_score = max(float(rerank_min_score), 0.0)
        self.fusion_service = fusion_service or ReciprocalRankFusion()
        self.context_builder = context_builder or ContextBuilder()
        self.answer_service = answer_service or AnswerService()
        self._query_repository = repository or QueryRepository()
        self._query_log_writer = log_writer or QueryLogWriter()

    def create_query(self, session: Session, **kwargs: Any) -> QueryResult:
        return QueryOrchestrator(self).create_query(session, **kwargs)

    def create_query_stream_plan(self, session: Session, **kwargs: Any) -> QueryStreamPlan:
        return QueryOrchestrator(self).create_query_stream_plan(session, **kwargs)

    def finalize_query_stream(
        self,
        session: Session,
        *,
        plan: QueryStreamPlan,
        answer_result: AnswerGenerationResult,
    ) -> QueryResult:
        return QueryOrchestrator(self).finalize_query_stream(
            session,
            plan=plan,
            answer_result=answer_result,
        )

    def _load_active_config_version(self, session: Session) -> int:
        return self._query_repository.load_active_config_version(session)

    def _load_active_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[ActiveIndexVersion, ...]:
        return self._query_repository.load_active_index_versions(
            session,
            enterprise_id=enterprise_id,
            kb_ids=kb_ids,
        )

    def _keyword_search(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        query_text: str,
        filter_clause: QueryFilterClause,
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        return self._query_repository.keyword_search(
            session,
            permission_filter=permission_filter,
            query_text=query_text,
            filter_clause=filter_clause,
            limit=limit,
        )

    def _gate_candidates(
        self,
        session: Session,
        context: PermissionContext,
        candidates: tuple[RetrievalCandidate, ...],
        *,
        allowed_kb_ids: tuple[str, ...],
        active_index_version_ids: tuple[str, ...],
        limit: int,
    ) -> tuple[QueryAllowedCandidate, ...]:
        return self._retrieval_pipeline().gate_candidates(
            session,
            context,
            candidates,
            allowed_kb_ids=allowed_kb_ids,
            active_index_version_ids=active_index_version_ids,
            limit=limit,
        )

    def _load_current_candidate_facts(
        self,
        session: Session,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> dict[tuple[str, str], _CurrentCandidateFacts]:
        return self._query_repository.load_current_candidate_facts(session, candidates)

    def _rerank_allowed_candidates(
        self,
        session: Session,
        *,
        query_text: str,
        allowed_candidates: tuple[QueryAllowedCandidate, ...],
        top_k: int,
    ) -> RerankResult:
        return self._retrieval_pipeline().rerank_allowed_candidates(
            session,
            query_text=query_text,
            allowed_candidates=allowed_candidates,
            top_k=top_k,
        )

    def _load_rerank_texts(
        self,
        session: Session,
        *,
        chunk_ids: tuple[str, ...],
    ) -> dict[str, str]:
        return self._query_repository.load_rerank_texts(session, chunk_ids=chunk_ids)

    def _insert_denied_query_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        user_id: str,
        kb_ids: tuple[str, ...],
        query_text: str,
        config_version: int,
        latency_ms: int,
        error_code: str,
    ) -> None:
        self._query_log_writer.insert_denied_query_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            kb_ids=kb_ids,
            query_text=query_text,
            config_version=config_version,
            latency_ms=latency_ms,
            error_code=error_code,
        )

    def _insert_query_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        user_id: str,
        kb_ids: tuple[str, ...],
        query_hash: str,
        status: str,
        degraded: bool,
        degrade_reason: str | None,
        config_version: int,
        permission_version: int,
        permission_filter_hash: str,
        index_version_hash: str | None,
        model_route_hash: str | None,
        latency_ms: int,
        candidate_count: int,
        citation_count: int,
        error_code: str | None,
    ) -> None:
        self._query_log_writer.insert_query_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            kb_ids=kb_ids,
            query_hash=query_hash,
            status=status,
            degraded=degraded,
            degrade_reason=degrade_reason,
            config_version=config_version,
            permission_version=permission_version,
            permission_filter_hash=permission_filter_hash,
            index_version_hash=index_version_hash,
            model_route_hash=model_route_hash,
            latency_ms=latency_ms,
            candidate_count=candidate_count,
            citation_count=citation_count,
            error_code=error_code,
        )

    def _insert_model_call_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        config_version: int,
        caller: str,
        answer_result: AnswerGenerationResult,
    ) -> None:
        self._query_log_writer.insert_model_call_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            config_version=config_version,
            caller=caller,
            answer_result=answer_result,
        )

    def _insert_retrieval_model_call_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        config_version: int,
        caller: str,
        model_call: RetrievalModelCall,
    ) -> None:
        self._query_log_writer.insert_retrieval_model_call_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            config_version=config_version,
            caller=caller,
            model_call=model_call,
        )

    def _insert_query_audit_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        user_id: str,
        config_version: int,
        permission_version: int,
        index_version_hash: str | None,
        event: _QueryAuditEvent,
    ) -> None:
        self._query_log_writer.insert_query_audit_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            config_version=config_version,
            permission_version=permission_version,
            index_version_hash=index_version_hash,
            event=event,
        )

    def _retrieval_pipeline(self) -> QueryRetrievalPipeline:
        return QueryRetrievalPipeline(
            permission_service=self.permission_service,
            candidate_reranker=self.candidate_reranker,
            repository=self._query_repository,
        )


_validate_answer_citations = citation_validator.validate_answer_citations
_append_reference_sources = citation_validator.append_reference_sources
_strip_source_refs_for_display = citation_validator.strip_source_refs_for_display
_citation_validation_summary = citation_validator.citation_validation_summary
_citation_validation_risk_level = citation_validator.citation_validation_risk_level
_degraded_answer = degrade_policy.degraded_answer
_degrade_reason_messages = degrade_policy.degrade_reason_messages
_degrade_reason_message = degrade_policy.degrade_reason_message
_brief_query = degrade_policy.brief_query


__all__ = [
    "DEFAULT_RERANK_MIN_SCORE",
    "MAX_QUERY_LENGTH",
    "SUPPORTED_FILTERS",
    "QueryAllowedCandidate",
    "QueryCitation",
    "QueryContext",
    "QueryFilterClause",
    "QueryResult",
    "QueryService",
    "QueryStreamPlan",
    "_CitationValidationResult",
    "_CurrentCandidateFacts",
    "_QueryAuditEvent",
    "_allowed_candidates_from_retrieval",
    "_apply_relevance_gate",
    "_brief_query",
    "_build_filter_clause",
    "_candidate_from_mapping",
    "_candidate_rerank_text",
    "_citation_from_candidate",
    "_citation_validation_risk_level",
    "_confidence",
    "_database_error",
    "_degrade_reason_message",
    "_degrade_reason_messages",
    "_degraded_answer",
    "_elapsed_ms",
    "_index_version_hash",
    "_normalize_ids",
    "_normalize_query",
    "_optional_int",
    "_query_hash",
    "_string_list",
    "_truncate_error_message",
    "_validate_answer_citations",
]
