"""Query Service P0 非流式闭环。

当前版本接入 PostgreSQL 关键词索引、向量召回端口、RRF 融合排序、上下文组装、
LLM 答案生成、引用校验和查询审计。向量或 LLM 运行时不可用时会显式降级，
不影响已通过权限 gate 的检索来源返回。
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any, Literal

from app.modules.answer import AnswerService
from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.context.schemas import QueryContext
from app.modules.context.service import ContextBuilder
from app.modules.permissions import CandidateMetadata, PermissionService, PermissionServiceError
from app.modules.permissions.schemas import PermissionContext, PermissionFilter
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import (
    ActiveIndexVersion,
    QueryAllowedCandidate,
    QueryCitation,
    QueryFilterClause,
    QueryResult,
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
from app.shared.json_utils import json_int, stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

MAX_QUERY_LENGTH = 4000
SUPPORTED_FILTERS = {"department_scope", "updated_after", "source_type", "tags"}
SOURCE_REF_PATTERN = re.compile(r"\[source:([^\]\s]+)\]")
SOURCE_REF_DISPLAY_PATTERN = re.compile(r"\s*\[source:[^\]\s]+\]")
REFERENCE_SOURCE_LINE_PATTERN = re.compile(
    r"(?:\n\s*)?参考来源：\s*(?:\[source:[^\]\s]+\]\s*)+",
    re.MULTILINE,
)
SOURCE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DEFAULT_RERANK_MIN_SCORE = 0.05


@dataclass(frozen=True)
class _CitationValidationResult:
    valid: bool
    degrade_reason: str
    referenced_source_ids: tuple[str, ...]
    invalid_source_ids: tuple[str, ...]
    allowed_source_count: int

    def summary(self) -> dict[str, object]:
        return {
            "degrade_reason": self.degrade_reason,
            "referenced_source_count": len(self.referenced_source_ids),
            "invalid_source_ids": list(self.invalid_source_ids[:10]),
            "invalid_source_count": len(self.invalid_source_ids),
            "allowed_source_count": self.allowed_source_count,
        }


@dataclass(frozen=True)
class _QueryAuditEvent:
    event_name: str
    result: Literal["failure", "denied"]
    risk_level: Literal["medium", "high", "critical"]
    error_code: str | None
    summary: dict[str, object]


@dataclass(frozen=True)
class _CurrentCandidateFacts:
    candidate: RetrievalCandidate
    access_blocked: bool


@dataclass(frozen=True)
class QueryStreamPlan:
    request_id: str
    trace_id: str
    mode: str
    started_at: float
    normalized_query: str
    normalized_kb_ids: tuple[str, ...]
    config_version: int
    context: PermissionContext
    query_context: QueryContext | None
    allowed_candidates: tuple[QueryAllowedCandidate, ...]
    citations: tuple[QueryCitation, ...]
    confidence: Literal["low", "medium", "high"]
    pre_degrade_reasons: tuple[str, ...]
    audit_events: tuple[_QueryAuditEvent, ...]
    rerank_model_call: RetrievalModelCall | None
    model_route_hash: str | None
    candidate_count: int
    permission_filter_hash: str
    permission_version: int
    index_version_hash: str | None
    conversation_id: str | None = None
    message_id: str | None = None


class QueryService:
    """非流式查询编排。"""

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
    ) -> None:
        self.permission_service = permission_service or PermissionService()
        self.vector_retriever = vector_retriever or UnavailableVectorRetriever()
        self.candidate_reranker = candidate_reranker or NoopCandidateReranker()
        self.rerank_input_top_k = max(rerank_input_top_k, 1)
        self.rerank_min_score = max(float(rerank_min_score), 0.0)
        self.fusion_service = fusion_service or ReciprocalRankFusion()
        self.context_builder = context_builder or ContextBuilder()
        self.answer_service = answer_service or AnswerService()

    def create_query(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_ids: list[str],
        query_text: str,
        mode: str,
        filters: dict[str, Any] | None,
        top_k: int,
        include_sources: bool,
        request_id: str,
        trace_id: str,
    ) -> QueryResult:
        started_at = time.monotonic()
        normalized_query = _normalize_query(query_text)
        normalized_kb_ids = _normalize_ids(kb_ids)
        normalized_top_k = min(max(top_k, 1), 50)
        request_filters = filters or {}
        filter_clause = _build_filter_clause(request_filters)
        config_version = self._load_active_config_version(session)

        try:
            context = self.permission_service.build_context(
                session,
                user_id=user_id,
                enterprise_id=enterprise_id,
                request_id=request_id,
            )
            queryable_kb_ids = self.permission_service.require_queryable_knowledge_bases(
                session,
                context,
                kb_ids=normalized_kb_ids,
                required_scope="rag:query",
            )
            active_indexes = self._load_active_index_versions(
                session,
                enterprise_id=context.enterprise_id,
                kb_ids=queryable_kb_ids,
            )
            active_index_ids = tuple(index.id for index in active_indexes)
            collection_names = tuple(index.collection_name for index in active_indexes)
            index_version_hash = _index_version_hash(active_index_ids)
            answer = ""
            citations: tuple[QueryCitation, ...] = ()
            query_context: QueryContext | None = None
            allowed_candidates: tuple[QueryAllowedCandidate, ...] = ()
            answer_result: AnswerGenerationResult | None = None
            rerank_model_call: RetrievalModelCall | None = None
            model_route_hash: str | None = None
            audit_events: list[_QueryAuditEvent] = []
            degrade_reasons: list[str] = []
            if active_index_ids:
                permission_filter = self.permission_service.build_filter(
                    context,
                    kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    required_scope="rag:query",
                )
                keyword_candidates = self._keyword_search(
                    session,
                    permission_filter=permission_filter,
                    query_text=normalized_query,
                    filter_clause=filter_clause,
                    limit=normalized_top_k * 3,
                )
                vector_result = self.vector_retriever.search(
                    query_text=normalized_query,
                    permission_filter=permission_filter,
                    collection_names=collection_names,
                    top_k=normalized_top_k * 3,
                )
                if vector_result.degraded:
                    degrade_reasons.append(
                        vector_result.degrade_reason or "vector_retrieval_degraded"
                    )
                candidates = self.fusion_service.fuse(
                    keyword_candidates + vector_result.candidates,
                    limit=normalized_top_k * 3,
                )
                allowed_candidates = self._gate_candidates(
                    session,
                    context,
                    candidates,
                    allowed_kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    limit=max(normalized_top_k, self.rerank_input_top_k),
                )
                rerank_result = self._rerank_allowed_candidates(
                    session,
                    query_text=normalized_query,
                    allowed_candidates=allowed_candidates,
                    top_k=normalized_top_k,
                )
                if rerank_result.degraded:
                    rerank_degrade_reason = (
                        rerank_result.degrade_reason or "rerank_degraded"
                    )
                    degrade_reasons.append(rerank_degrade_reason)
                    audit_events.append(
                        _QueryAuditEvent(
                            event_name="query.rerank_degraded",
                            result="failure",
                            risk_level="medium",
                            error_code=rerank_degrade_reason,
                            summary={
                                "degrade_reason": rerank_degrade_reason,
                                "candidate_count": len(allowed_candidates),
                            },
                        )
                    )
                rerank_model_call = rerank_result.model_call
                if rerank_model_call is not None and model_route_hash is None:
                    model_route_hash = rerank_model_call.model_route_hash
                relevant_candidates, relevance_audit_event = _apply_relevance_gate(
                    rerank_result,
                    min_score=self.rerank_min_score,
                    candidate_count=len(allowed_candidates),
                )
                if relevance_audit_event is not None:
                    degrade_reasons.append("retrieval_relevance_too_low")
                    audit_events.append(relevance_audit_event)
                allowed_candidates = _allowed_candidates_from_retrieval(relevant_candidates)
                citations = (
                    tuple(item.citation for item in allowed_candidates)
                    if include_sources
                    else ()
                )
                if mode == "answer":
                    query_context = self.context_builder.build(
                        session,
                        query_text=normalized_query,
                        allowed_candidates=allowed_candidates,
                    )
                candidate_count = len(candidates)
                permission_filter_hash = permission_filter.permission_filter_hash
                permission_version = permission_filter.permission_version
            else:
                candidate_count = 0
                permission_filter_hash = context.permission_filter_hash
                permission_version = context.permission_version

            if mode == "answer":
                answer_result = self.answer_service.generate(query_context=query_context)
                model_route_hash = answer_result.model_route_hash
                answer = answer_result.answer
                if answer_result.degraded:
                    degrade_reasons.append(answer_result.degrade_reason or "llm_degraded")
                    if answer_result.model_call_attempted:
                        summary: dict[str, object] = {
                            "model_name": answer_result.model_name,
                            "degrade_reason": answer_result.degrade_reason,
                        }
                        if answer_result.error_message:
                            summary["error_message"] = _truncate_error_message(
                                answer_result.error_message
                            )
                        audit_events.append(
                            _QueryAuditEvent(
                                event_name="query.llm_degraded",
                                result="failure",
                                risk_level="medium",
                                error_code=answer_result.degrade_reason,
                                summary=summary,
                            )
                        )
                elif answer:
                    citation_validation = _validate_answer_citations(
                        answer,
                        allowed_source_ids=tuple(
                            allowed.candidate.chunk_id for allowed in allowed_candidates
                        ),
                    )
                    if not citation_validation.valid:
                        citation_degrade_reason = citation_validation.degrade_reason
                        if citation_validation.degrade_reason == "citation_missing":
                            repaired_answer = _append_reference_sources(
                                answer,
                                allowed_candidates=allowed_candidates,
                            )
                            if repaired_answer != answer:
                                answer = repaired_answer
                                citation_degrade_reason = "citation_auto_attached"
                            else:
                                answer = ""
                        else:
                            answer = ""
                        degrade_reasons.append(citation_degrade_reason)
                        audit_events.append(
                            _QueryAuditEvent(
                                event_name="query.citation_validation_failed",
                                result="failure",
                                risk_level=_citation_validation_risk_level(
                                    citation_degrade_reason
                                ),
                                error_code=citation_degrade_reason,
                                summary=_citation_validation_summary(
                                    citation_validation,
                                    final_degrade_reason=citation_degrade_reason,
                                ),
                            )
                        )
            if mode == "answer" and not answer and degrade_reasons:
                answer = _degraded_answer(
                    query_text=normalized_query,
                    degrade_reasons=tuple(degrade_reasons),
                    citation_count=len(citations),
                    candidate_count=candidate_count,
                )
            if mode == "answer" and answer:
                answer = _strip_source_refs_for_display(answer)
            degraded = bool(degrade_reasons)
            degrade_reason = ";".join(degrade_reasons) if degrade_reasons else None
            result = QueryResult(
                request_id=request_id,
                answer=answer,
                citations=citations,
                confidence=_confidence(citations),
                degraded=degraded,
                degrade_reason=degrade_reason,
                trace_id=trace_id,
                context=query_context,
            )
            if answer_result is not None and answer_result.model_call_attempted:
                self._insert_model_call_log(
                    session,
                    request_id=request_id,
                    trace_id=trace_id,
                    enterprise_id=context.enterprise_id,
                    config_version=config_version,
                    caller="query.answer",
                    answer_result=answer_result,
                )
            if rerank_model_call is not None:
                self._insert_retrieval_model_call_log(
                    session,
                    request_id=request_id,
                    trace_id=trace_id,
                    enterprise_id=context.enterprise_id,
                    config_version=config_version,
                    caller="query.rerank",
                    model_call=rerank_model_call,
                )
            for audit_event in audit_events:
                self._insert_query_audit_log(
                    session,
                    request_id=request_id,
                    trace_id=trace_id,
                    enterprise_id=context.enterprise_id,
                    user_id=context.user_id,
                    config_version=config_version,
                    permission_version=permission_version,
                    index_version_hash=index_version_hash,
                    event=audit_event,
                )
            self._insert_query_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=context.enterprise_id,
                user_id=context.user_id,
                kb_ids=normalized_kb_ids,
                query_hash=_query_hash(normalized_query),
                status="success",
                degraded=degraded,
                degrade_reason=degrade_reason,
                config_version=config_version,
                permission_version=permission_version,
                permission_filter_hash=permission_filter_hash,
                index_version_hash=index_version_hash,
                model_route_hash=model_route_hash,
                latency_ms=_elapsed_ms(started_at),
                candidate_count=candidate_count,
                citation_count=len(citations),
                error_code=None,
            )
            return result
        except PermissionServiceError as exc:
            self._insert_denied_query_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=enterprise_id,
                user_id=user_id,
                kb_ids=normalized_kb_ids,
                query_text=normalized_query,
                config_version=config_version,
                latency_ms=_elapsed_ms(started_at),
                error_code=exc.error_code,
            )
            self._insert_query_audit_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=enterprise_id,
                user_id=user_id,
                config_version=config_version,
                permission_version=0,
                index_version_hash=None,
                event=_QueryAuditEvent(
                    event_name="query.denied",
                    result="denied",
                    risk_level="high",
                    error_code=exc.error_code,
                    summary={"kb_ids": list(normalized_kb_ids), "error_code": exc.error_code},
                ),
            )
            raise QueryServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def create_query_stream_plan(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_ids: list[str],
        query_text: str,
        mode: str,
        filters: dict[str, Any] | None,
        top_k: int,
        include_sources: bool,
        request_id: str,
        trace_id: str,
    ) -> QueryStreamPlan:
        started_at = time.monotonic()
        normalized_query = _normalize_query(query_text)
        normalized_kb_ids = _normalize_ids(kb_ids)
        normalized_top_k = min(max(top_k, 1), 50)
        request_filters = filters or {}
        filter_clause = _build_filter_clause(request_filters)
        config_version = self._load_active_config_version(session)

        try:
            context = self.permission_service.build_context(
                session,
                user_id=user_id,
                enterprise_id=enterprise_id,
                request_id=request_id,
            )
            queryable_kb_ids = self.permission_service.require_queryable_knowledge_bases(
                session,
                context,
                kb_ids=normalized_kb_ids,
                required_scope="rag:query",
            )
            query_context: QueryContext | None = None
            allowed_candidates: tuple[QueryAllowedCandidate, ...] = ()
            citations: tuple[QueryCitation, ...] = ()
            rerank_model_call: RetrievalModelCall | None = None
            model_route_hash: str | None = None
            audit_events: list[_QueryAuditEvent] = []
            degrade_reasons: list[str] = []
            active_indexes = self._load_active_index_versions(
                session,
                enterprise_id=context.enterprise_id,
                kb_ids=queryable_kb_ids,
            )
            active_index_ids = tuple(index.id for index in active_indexes)
            collection_names = tuple(index.collection_name for index in active_indexes)
            index_version_hash = _index_version_hash(active_index_ids)
            if active_index_ids:
                permission_filter = self.permission_service.build_filter(
                    context,
                    kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    required_scope="rag:query",
                )
                keyword_candidates = self._keyword_search(
                    session,
                    permission_filter=permission_filter,
                    query_text=normalized_query,
                    filter_clause=filter_clause,
                    limit=normalized_top_k * 3,
                )
                vector_result = self.vector_retriever.search(
                    query_text=normalized_query,
                    permission_filter=permission_filter,
                    collection_names=collection_names,
                    top_k=normalized_top_k * 3,
                )
                if vector_result.degraded:
                    degrade_reasons.append(
                        vector_result.degrade_reason or "vector_retrieval_degraded"
                    )
                candidates = self.fusion_service.fuse(
                    keyword_candidates + vector_result.candidates,
                    limit=normalized_top_k * 3,
                )
                allowed_candidates = self._gate_candidates(
                    session,
                    context,
                    candidates,
                    allowed_kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    limit=max(normalized_top_k, self.rerank_input_top_k),
                )
                rerank_result = self._rerank_allowed_candidates(
                    session,
                    query_text=normalized_query,
                    allowed_candidates=allowed_candidates,
                    top_k=normalized_top_k,
                )
                if rerank_result.degraded:
                    rerank_degrade_reason = (
                        rerank_result.degrade_reason or "rerank_degraded"
                    )
                    degrade_reasons.append(rerank_degrade_reason)
                    audit_events.append(
                        _QueryAuditEvent(
                            event_name="query.rerank_degraded",
                            result="failure",
                            risk_level="medium",
                            error_code=rerank_degrade_reason,
                            summary={
                                "degrade_reason": rerank_degrade_reason,
                                "candidate_count": len(allowed_candidates),
                            },
                        )
                    )
                rerank_model_call = rerank_result.model_call
                if rerank_model_call is not None:
                    model_route_hash = rerank_model_call.model_route_hash
                relevant_candidates, relevance_audit_event = _apply_relevance_gate(
                    rerank_result,
                    min_score=self.rerank_min_score,
                    candidate_count=len(allowed_candidates),
                )
                if relevance_audit_event is not None:
                    degrade_reasons.append("retrieval_relevance_too_low")
                    audit_events.append(relevance_audit_event)
                allowed_candidates = _allowed_candidates_from_retrieval(relevant_candidates)
                citations = (
                    tuple(item.citation for item in allowed_candidates)
                    if include_sources
                    else ()
                )
                if mode == "answer":
                    query_context = self.context_builder.build(
                        session,
                        query_text=normalized_query,
                        allowed_candidates=allowed_candidates,
                    )
                candidate_count = len(candidates)
                permission_filter_hash = permission_filter.permission_filter_hash
                permission_version = permission_filter.permission_version
            else:
                candidate_count = 0
                permission_filter_hash = context.permission_filter_hash
                permission_version = context.permission_version

            return QueryStreamPlan(
                request_id=request_id,
                trace_id=trace_id,
                mode=mode,
                started_at=started_at,
                normalized_query=normalized_query,
                normalized_kb_ids=normalized_kb_ids,
                config_version=config_version,
                context=context,
                query_context=query_context,
                allowed_candidates=allowed_candidates,
                citations=citations,
                confidence=_confidence(citations),
                pre_degrade_reasons=tuple(degrade_reasons),
                audit_events=tuple(audit_events),
                rerank_model_call=rerank_model_call,
                model_route_hash=model_route_hash,
                candidate_count=candidate_count,
                permission_filter_hash=permission_filter_hash,
                permission_version=permission_version,
                index_version_hash=index_version_hash,
            )
        except PermissionServiceError as exc:
            self._insert_denied_query_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=enterprise_id,
                user_id=user_id,
                kb_ids=normalized_kb_ids,
                query_text=normalized_query,
                config_version=config_version,
                latency_ms=_elapsed_ms(started_at),
                error_code=exc.error_code,
            )
            self._insert_query_audit_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=enterprise_id,
                user_id=user_id,
                config_version=config_version,
                permission_version=0,
                index_version_hash=None,
                event=_QueryAuditEvent(
                    event_name="query.denied",
                    result="denied",
                    risk_level="high",
                    error_code=exc.error_code,
                    summary={"kb_ids": list(normalized_kb_ids), "error_code": exc.error_code},
                ),
            )
            raise QueryServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def finalize_query_stream(
        self,
        session: Session,
        *,
        plan: QueryStreamPlan,
        answer_result: AnswerGenerationResult,
    ) -> QueryResult:
        answer = answer_result.answer
        model_route_hash = answer_result.model_route_hash or plan.model_route_hash
        audit_events = list(plan.audit_events)
        degrade_reasons = list(plan.pre_degrade_reasons)
        if answer_result.degraded:
            degrade_reasons.append(answer_result.degrade_reason or "llm_degraded")
            if answer_result.model_call_attempted:
                summary: dict[str, object] = {
                    "model_name": answer_result.model_name,
                    "degrade_reason": answer_result.degrade_reason,
                }
                if answer_result.error_message:
                    summary["error_message"] = _truncate_error_message(
                        answer_result.error_message
                    )
                audit_events.append(
                    _QueryAuditEvent(
                        event_name="query.llm_degraded",
                        result="failure",
                        risk_level="medium",
                        error_code=answer_result.degrade_reason,
                        summary=summary,
                    )
                )
        elif answer:
            citation_validation = _validate_answer_citations(
                answer,
                allowed_source_ids=tuple(
                    allowed.candidate.chunk_id for allowed in plan.allowed_candidates
                ),
            )
            if not citation_validation.valid:
                citation_degrade_reason = citation_validation.degrade_reason
                if citation_validation.degrade_reason == "citation_missing":
                    repaired_answer = _append_reference_sources(
                        answer,
                        allowed_candidates=plan.allowed_candidates,
                    )
                    if repaired_answer != answer:
                        answer = repaired_answer
                        citation_degrade_reason = "citation_auto_attached"
                    else:
                        answer = ""
                else:
                    answer = ""
                degrade_reasons.append(citation_degrade_reason)
                audit_events.append(
                    _QueryAuditEvent(
                        event_name="query.citation_validation_failed",
                        result="failure",
                        risk_level=_citation_validation_risk_level(
                            citation_degrade_reason
                        ),
                        error_code=citation_degrade_reason,
                        summary=_citation_validation_summary(
                            citation_validation,
                            final_degrade_reason=citation_degrade_reason,
                        ),
                    )
                )
        if plan.mode == "answer" and not answer and degrade_reasons:
            answer = _degraded_answer(
                query_text=plan.normalized_query,
                degrade_reasons=tuple(degrade_reasons),
                citation_count=len(plan.citations),
                candidate_count=plan.candidate_count,
            )
        if plan.mode == "answer" and answer:
            answer = _strip_source_refs_for_display(answer)
        degraded = bool(degrade_reasons)
        degrade_reason = ";".join(degrade_reasons) if degrade_reasons else None
        result = QueryResult(
            request_id=plan.request_id,
            answer=answer,
            citations=plan.citations,
            confidence=plan.confidence,
            degraded=degraded,
            degrade_reason=degrade_reason,
            trace_id=plan.trace_id,
            context=plan.query_context,
        )
        if answer_result.model_call_attempted:
            self._insert_model_call_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                config_version=plan.config_version,
                caller="query.answer_stream",
                answer_result=answer_result,
            )
        if plan.rerank_model_call is not None:
            self._insert_retrieval_model_call_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                config_version=plan.config_version,
                caller="query.rerank",
                model_call=plan.rerank_model_call,
            )
        for audit_event in audit_events:
            self._insert_query_audit_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                user_id=plan.context.user_id,
                config_version=plan.config_version,
                permission_version=plan.permission_version,
                index_version_hash=plan.index_version_hash,
                event=audit_event,
            )
        self._insert_query_log(
            session,
            request_id=plan.request_id,
            trace_id=plan.trace_id,
            enterprise_id=plan.context.enterprise_id,
            user_id=plan.context.user_id,
            kb_ids=plan.normalized_kb_ids,
            query_hash=_query_hash(plan.normalized_query),
            status="success",
            degraded=degraded,
            degrade_reason=degrade_reason,
            config_version=plan.config_version,
            permission_version=plan.permission_version,
            permission_filter_hash=plan.permission_filter_hash,
            index_version_hash=plan.index_version_hash,
            model_route_hash=model_route_hash,
            latency_ms=_elapsed_ms(plan.started_at),
            candidate_count=plan.candidate_count,
            citation_count=len(plan.citations),
            error_code=None,
        )
        return result

    def _load_active_config_version(self, session: Session) -> int:
        try:
            row = session.execute(
                text(
                    """
                    SELECT value_json
                    FROM system_state
                    WHERE key = 'active_config_version'
                    LIMIT 1
                    """
                )
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_CONFIG_UNAVAILABLE",
                "active config version cannot be loaded",
                exc,
            ) from exc
        version = json_int(row._mapping["value_json"], "version") if row else None
        if version is None:
            raise QueryServiceError(
                "QUERY_CONFIG_UNAVAILABLE",
                "active config version is missing",
                status_code=503,
                retryable=True,
            )
        return version

    def _load_active_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[ActiveIndexVersion, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS index_version_id,
                        collection_name
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = ANY(CAST(:kb_ids AS uuid[]))
                      AND status = 'active'
                    ORDER BY activated_at DESC NULLS LAST, id
                    """
                ),
                {"enterprise_id": enterprise_id, "kb_ids": list(kb_ids)},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_INDEX_UNAVAILABLE",
                "active index versions cannot be loaded",
                exc,
            ) from exc
        return tuple(
            ActiveIndexVersion(
                id=str(row._mapping["index_version_id"]),
                collection_name=str(row._mapping["collection_name"]),
            )
            for row in rows
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
        params = dict(permission_filter.params)
        params.update(filter_clause.params)
        params.update(
            {
                "query_text": query_text,
                "like_query": f"%{query_text}%",
                "limit": limit,
            }
        )
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        kie.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        c.id::text AS chunk_id,
                        d.title,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.lifecycle_status AS document_lifecycle_status,
                        d.index_status AS document_index_status,
                        c.status AS chunk_status,
                        kie.visibility_state,
                        iv.id::text AS index_version_id,
                        LEAST(
                            kie.indexed_permission_version,
                            cir.indexed_permission_version
                        ) AS indexed_permission_version,
                        c.page_start,
                        c.page_end,
                        GREATEST(
                            ts_rank_cd(kie.search_tsv, plainto_tsquery('simple', :query_text)),
                            CASE WHEN kie.search_text ILIKE :like_query THEN 0.05 ELSE 0 END
                        )::float AS score
                    FROM keyword_index_entries kie
                    JOIN chunks c ON c.id = kie.chunk_id
                    JOIN documents d ON d.id = kie.document_id
                    JOIN index_versions iv ON iv.id = kie.index_version_id
                    JOIN chunk_index_refs cir
                      ON cir.keyword_id = kie.id
                     AND cir.chunk_id = c.id
                     AND cir.index_version_id = iv.id
                    WHERE {permission_filter.keyword_where_sql}
                      AND iv.status = 'active'
                      AND (
                          kie.search_tsv @@ plainto_tsquery('simple', :query_text)
                          OR kie.search_text ILIKE :like_query
                      )
                      {filter_clause.sql}
                    ORDER BY score DESC, c.ordinal ASC
                    LIMIT :limit
                    """
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_KEYWORD_SEARCH_FAILED",
                "keyword search failed",
                exc,
            ) from exc
        return tuple(
            _candidate_from_mapping(dict(row._mapping), source="keyword", rank=rank)
            for rank, row in enumerate(rows, start=1)
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
        allowed: list[QueryAllowedCandidate] = []
        current_facts = self._load_current_candidate_facts(session, candidates)
        for candidate in candidates:
            facts = current_facts.get((candidate.chunk_id, candidate.index_version_id))
            if facts is None:
                continue
            candidate = facts.candidate
            gate_result = self.permission_service.gate_candidate(
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

    def _load_current_candidate_facts(
        self,
        session: Session,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> dict[tuple[str, str], _CurrentCandidateFacts]:
        if not candidates:
            return {}
        chunk_ids = [candidate.chunk_id for candidate in candidates]
        index_version_ids = [candidate.index_version_id for candidate in candidates]
        try:
            rows = session.execute(
                text(
                    """
                    WITH requested AS (
                        SELECT *
                        FROM unnest(
                            CAST(:chunk_ids AS uuid[]),
                            CAST(:index_version_ids AS uuid[])
                        ) AS item(chunk_id, index_version_id)
                    )
                    SELECT
                        c.id::text AS chunk_id,
                        d.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        d.title,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.lifecycle_status AS document_lifecycle_status,
                        d.index_status AS document_index_status,
                        c.status AS chunk_status,
                        cir.visibility_state,
                        iv.id::text AS index_version_id,
                        cir.indexed_permission_version,
                        c.page_start,
                        c.page_end,
                        EXISTS (
                            SELECT 1
                            FROM access_blocks ab
                            WHERE ab.enterprise_id = d.enterprise_id
                              AND (
                                  (ab.resource_type = 'knowledge_base'
                                      AND ab.resource_id = d.kb_id)
                                  OR (ab.resource_type = 'folder'
                                      AND ab.resource_id = d.folder_id)
                                  OR (ab.resource_type = 'document'
                                      AND ab.resource_id = d.id)
                                  OR (ab.resource_type = 'chunk'
                                      AND ab.resource_id = c.id)
                              )
                              AND ab.status = 'active'
                              AND (ab.expires_at IS NULL OR ab.expires_at > now())
                        ) AS access_blocked
                    FROM requested r
                    JOIN chunks c
                      ON c.id = r.chunk_id
                     AND c.deleted_at IS NULL
                    JOIN documents d
                      ON d.id = c.document_id
                     AND d.deleted_at IS NULL
                    JOIN index_versions iv
                      ON iv.id = r.index_version_id
                     AND iv.document_id = d.id
                     AND iv.document_version_id = c.document_version_id
                     AND iv.status = 'active'
                    JOIN chunk_index_refs cir
                      ON cir.chunk_id = c.id
                     AND cir.index_version_id = iv.id
                    """
                ),
                {"chunk_ids": chunk_ids, "index_version_ids": index_version_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_CANDIDATE_METADATA_UNAVAILABLE",
                "query candidate metadata cannot be loaded",
                exc,
            ) from exc
        by_candidate = {
            (candidate.chunk_id, candidate.index_version_id): candidate
            for candidate in candidates
        }
        facts: dict[tuple[str, str], _CurrentCandidateFacts] = {}
        for row in rows:
            mapping = row._mapping
            key = (str(mapping["chunk_id"]), str(mapping["index_version_id"]))
            original = by_candidate.get(key)
            if original is None:
                continue
            facts[key] = _CurrentCandidateFacts(
                candidate=replace(
                    original,
                    enterprise_id=str(mapping["enterprise_id"]),
                    kb_id=str(mapping["kb_id"]),
                    document_id=str(mapping["document_id"]),
                    document_version_id=str(mapping["document_version_id"]),
                    title=str(mapping["title"]),
                    owner_department_id=str(mapping["owner_department_id"]),
                    visibility=str(mapping["visibility"]),
                    document_lifecycle_status=str(mapping["document_lifecycle_status"]),
                    document_index_status=str(mapping["document_index_status"]),
                    chunk_status=str(mapping["chunk_status"]),
                    visibility_state=str(mapping["visibility_state"]),
                    index_version_id=str(mapping["index_version_id"]),
                    indexed_permission_version=int(mapping["indexed_permission_version"]),
                    page_start=_optional_int(mapping["page_start"]),
                    page_end=_optional_int(mapping["page_end"]),
                ),
                access_blocked=bool(mapping["access_blocked"]),
            )
        return facts

    def _rerank_allowed_candidates(
        self,
        session: Session,
        *,
        query_text: str,
        allowed_candidates: tuple[QueryAllowedCandidate, ...],
        top_k: int,
    ) -> RerankResult:
        candidates = tuple(allowed.candidate for allowed in allowed_candidates)
        if isinstance(self.candidate_reranker, NoopCandidateReranker):
            return self.candidate_reranker.rerank(
                query_text=query_text,
                candidates=candidates,
                texts=(),
                top_k=top_k,
            )
        try:
            texts_by_chunk_id = self._load_rerank_texts(
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
        return self.candidate_reranker.rerank(
            query_text=query_text,
            candidates=candidates,
            texts=texts,
            top_k=top_k,
        )

    def _load_rerank_texts(
        self,
        session: Session,
        *,
        chunk_ids: tuple[str, ...],
    ) -> dict[str, str]:
        if not chunk_ids:
            return {}
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS chunk_id,
                        text_preview
                    FROM chunks
                    WHERE id = ANY(CAST(:chunk_ids AS uuid[]))
                      AND deleted_at IS NULL
                    """
                ),
                {"chunk_ids": list(chunk_ids)},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_RERANK_INPUT_UNAVAILABLE",
                "rerank input chunks cannot be loaded",
                exc,
            ) from exc
        return {
            str(row._mapping["chunk_id"]): str(row._mapping["text_preview"] or "")
            for row in rows
        }

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
        self._insert_query_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            kb_ids=kb_ids,
            query_hash=_query_hash(query_text),
            status="denied",
            degraded=False,
            degrade_reason=None,
            config_version=config_version,
            permission_version=0,
            permission_filter_hash="unavailable",
            index_version_hash=None,
            model_route_hash=None,
            latency_ms=latency_ms,
            candidate_count=0,
            citation_count=0,
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
        try:
            session.execute(
                text(
                    """
                    INSERT INTO query_logs(
                        id, enterprise_id, request_id, trace_id, user_id, kb_ids,
                        query_hash, status, degraded, degrade_reason, config_version,
                        permission_version, permission_filter_hash, index_version_hash,
                        model_route_hash, latency_ms, candidate_count, citation_count,
                        error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, CAST(:user_id AS uuid), CAST(:kb_ids AS uuid[]),
                        :query_hash, :status, :degraded, :degrade_reason, :config_version,
                        :permission_version, :permission_filter_hash, :index_version_hash,
                        :model_route_hash, :latency_ms, :candidate_count, :citation_count,
                        :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "kb_ids": list(kb_ids),
                    "query_hash": query_hash,
                    "status": status,
                    "degraded": degraded,
                    "degrade_reason": degrade_reason,
                    "config_version": config_version,
                    "permission_version": permission_version,
                    "permission_filter_hash": permission_filter_hash,
                    "index_version_hash": index_version_hash,
                    "model_route_hash": model_route_hash,
                    "latency_ms": latency_ms,
                    "candidate_count": candidate_count,
                    "citation_count": citation_count,
                    "error_code": error_code,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_LOG_WRITE_FAILED",
                "query log cannot be written",
                exc,
            ) from exc

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
        status = "success" if not answer_result.degraded else "failed"
        try:
            session.execute(
                text(
                    """
                    INSERT INTO model_call_logs(
                        id, enterprise_id, request_id, trace_id, config_version,
                        caller, model_type, model_name, model_version, model_route_hash,
                        status, degraded, latency_ms, token_usage_json, prompt_hash,
                        input_hash, output_hash, error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, :config_version, :caller, :model_type, :model_name,
                        :model_version, :model_route_hash, :status, :degraded, :latency_ms,
                        CAST(:token_usage_json AS jsonb), :prompt_hash, :input_hash,
                        :output_hash, :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "config_version": config_version,
                    "caller": caller,
                    "model_type": answer_result.model_type,
                    "model_name": answer_result.model_name or "unknown",
                    "model_version": answer_result.model_version,
                    "model_route_hash": answer_result.model_route_hash or "unknown",
                    "status": status,
                    "degraded": answer_result.degraded,
                    "latency_ms": answer_result.latency_ms or 0,
                    "token_usage_json": json.dumps(
                        answer_result.token_usage,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if answer_result.token_usage is not None
                    else None,
                    "prompt_hash": answer_result.prompt_hash,
                    "input_hash": answer_result.input_hash,
                    "output_hash": answer_result.output_hash,
                    "error_code": answer_result.degrade_reason if answer_result.degraded else None,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_MODEL_CALL_LOG_WRITE_FAILED",
                "model call log cannot be written",
                exc,
            ) from exc

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
        try:
            session.execute(
                text(
                    """
                    INSERT INTO model_call_logs(
                        id, enterprise_id, request_id, trace_id, config_version,
                        caller, model_type, model_name, model_version, model_route_hash,
                        status, degraded, latency_ms, token_usage_json, prompt_hash,
                        input_hash, output_hash, error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, :config_version, :caller, :model_type, :model_name,
                        :model_version, :model_route_hash, :status, :degraded, :latency_ms,
                        CAST(:token_usage_json AS jsonb), :prompt_hash, :input_hash,
                        :output_hash, :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "config_version": config_version,
                    "caller": caller,
                    "model_type": model_call.model_type,
                    "model_name": model_call.model_name or "unknown",
                    "model_version": model_call.model_version,
                    "model_route_hash": model_call.model_route_hash or "unknown",
                    "status": model_call.status,
                    "degraded": model_call.degraded,
                    "latency_ms": model_call.latency_ms,
                    "token_usage_json": json.dumps(
                        model_call.token_usage,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if model_call.token_usage is not None
                    else None,
                    "prompt_hash": model_call.prompt_hash,
                    "input_hash": model_call.input_hash,
                    "output_hash": model_call.output_hash,
                    "error_code": model_call.error_code,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_MODEL_CALL_LOG_WRITE_FAILED",
                "model call log cannot be written",
                exc,
            ) from exc

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
        try:
            session.execute(
                text(
                    """
                    INSERT INTO audit_logs(
                        id, enterprise_id, request_id, trace_id, event_name, actor_type,
                        actor_id, resource_type, resource_id, action, result, risk_level,
                        config_version, permission_version, index_version_hash, summary_json,
                        error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, :event_name, 'user', :actor_id, 'query', :resource_id,
                        'query', :result, :risk_level, :config_version, :permission_version,
                        :index_version_hash, CAST(:summary_json AS jsonb), :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "event_name": event.event_name,
                    "actor_id": user_id,
                    "resource_id": request_id,
                    "result": event.result,
                    "risk_level": event.risk_level,
                    "config_version": config_version,
                    "permission_version": permission_version,
                    "index_version_hash": index_version_hash,
                    "summary_json": json.dumps(
                        event.summary,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "error_code": event.error_code,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_AUDIT_LOG_WRITE_FAILED",
                "query audit log cannot be written",
                exc,
            ) from exc


def _normalize_query(value: str) -> str:
    query = value.strip()
    if not query:
        raise QueryServiceError("QUERY_INVALID_REQUEST", "query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryServiceError(
            "QUERY_TOO_LONG",
            "query is too long",
            status_code=413,
            details={"max_length": MAX_QUERY_LENGTH},
        )
    return query


def _normalize_ids(values: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    if not normalized:
        raise QueryServiceError("QUERY_INVALID_REQUEST", "kb_ids must not be empty")
    return tuple(normalized)


def _build_filter_clause(filters: dict[str, Any]) -> QueryFilterClause:
    unsupported = sorted(set(filters) - SUPPORTED_FILTERS)
    if unsupported:
        raise QueryServiceError(
            "QUERY_FILTER_UNSUPPORTED",
            "query filter is not supported",
            details={"unsupported_filters": unsupported},
        )
    conditions: list[str] = []
    params: dict[str, Any] = {}
    department_scope = filters.get("department_scope")
    if department_scope not in (None, "my_accessible"):
        raise QueryServiceError(
            "QUERY_FILTER_UNSUPPORTED",
            "department_scope only supports my_accessible in P0",
            details={"department_scope": department_scope},
        )
    source_types = _string_list(filters.get("source_type"))
    if source_types:
        conditions.append("d.source_type = ANY(CAST(:source_types AS text[]))")
        params["source_types"] = source_types
    tags = _string_list(filters.get("tags"))
    if tags:
        conditions.append("d.tags && CAST(:tags AS text[])")
        params["tags"] = tags
    updated_after = filters.get("updated_after")
    if updated_after is not None:
        if not isinstance(updated_after, str) or not updated_after.strip():
            raise QueryServiceError(
                "QUERY_INVALID_REQUEST",
                "updated_after must be a non-empty string",
            )
        conditions.append("d.updated_at >= CAST(:updated_after AS timestamptz)")
        params["updated_after"] = updated_after.strip()
    sql = "".join(f"\n                      AND {condition}" for condition in conditions)
    return QueryFilterClause(sql=sql, params=params)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _candidate_from_mapping(
    row: dict[str, Any],
    *,
    source: Literal["keyword", "vector"],
    rank: int,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        source=source,
        enterprise_id=str(row["enterprise_id"]),
        kb_id=str(row["kb_id"]),
        document_id=str(row["document_id"]),
        document_version_id=str(row["document_version_id"]),
        chunk_id=str(row["chunk_id"]),
        title=str(row["title"]),
        owner_department_id=str(row["owner_department_id"]),
        visibility=str(row["visibility"]),
        document_lifecycle_status=str(row["document_lifecycle_status"]),
        document_index_status=str(row["document_index_status"]),
        chunk_status=str(row["chunk_status"]),
        visibility_state=str(row["visibility_state"]),
        index_version_id=str(row["index_version_id"]),
        indexed_permission_version=int(row["indexed_permission_version"]),
        page_start=_optional_int(row.get("page_start")),
        page_end=_optional_int(row.get("page_end")),
        rank=rank,
        score=float(row["score"] or 0),
    )


def _citation_from_candidate(candidate: RetrievalCandidate) -> QueryCitation:
    page_start = candidate.page_start or 0
    return QueryCitation(
        source_id=candidate.chunk_id,
        doc_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        title=candidate.title,
        page_start=page_start,
        page_end=candidate.page_end or page_start,
        score=candidate.score,
    )


def _allowed_candidates_from_retrieval(
    candidates: tuple[RetrievalCandidate, ...],
) -> tuple[QueryAllowedCandidate, ...]:
    return tuple(
        QueryAllowedCandidate(candidate=candidate, citation=_citation_from_candidate(candidate))
        for candidate in candidates
    )


def _apply_relevance_gate(
    rerank_result: RerankResult,
    *,
    min_score: float,
    candidate_count: int,
) -> tuple[tuple[RetrievalCandidate, ...], _QueryAuditEvent | None]:
    candidates = rerank_result.candidates
    model_call = rerank_result.model_call
    if (
        min_score <= 0
        or not candidates
        or rerank_result.degraded
        or model_call is None
        or model_call.status != "success"
        or model_call.degraded
    ):
        return candidates, None

    relevant = tuple(candidate for candidate in candidates if candidate.score >= min_score)
    if relevant:
        return relevant, None

    top_score = max((candidate.score for candidate in candidates), default=0.0)
    return (
        (),
        _QueryAuditEvent(
            event_name="query.relevance_gate_failed",
            result="failure",
            risk_level="medium",
            error_code="retrieval_relevance_too_low",
            summary={
                "degrade_reason": "retrieval_relevance_too_low",
                "min_score": min_score,
                "top_score": top_score,
                "candidate_count": candidate_count,
                "reranked_count": len(candidates),
            },
        ),
    )


def _candidate_rerank_text(candidate: RetrievalCandidate, text_preview: str | None) -> str:
    if isinstance(text_preview, str) and text_preview.strip():
        return text_preview.strip()
    return candidate.title


def _truncate_error_message(message: str, *, limit: int = 500) -> str:
    compact = " ".join(message.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def _validate_answer_citations(
    answer: str,
    *,
    allowed_source_ids: tuple[str, ...],
) -> _CitationValidationResult:
    referenced = tuple(dict.fromkeys(SOURCE_REF_PATTERN.findall(answer)))
    allowed = set(allowed_source_ids)
    if not referenced:
        return _CitationValidationResult(
            valid=False,
            degrade_reason="citation_missing",
            referenced_source_ids=(),
            invalid_source_ids=(),
            allowed_source_count=len(allowed),
        )
    invalid_format = tuple(
        source_id for source_id in referenced if not SOURCE_ID_PATTERN.fullmatch(source_id)
    )
    if invalid_format:
        return _CitationValidationResult(
            valid=False,
            degrade_reason="citation_invalid_format",
            referenced_source_ids=referenced,
            invalid_source_ids=invalid_format,
            allowed_source_count=len(allowed),
        )
    invalid = tuple(source_id for source_id in referenced if source_id not in allowed)
    if invalid:
        return _CitationValidationResult(
            valid=False,
            degrade_reason="citation_unauthorized",
            referenced_source_ids=referenced,
            invalid_source_ids=invalid,
            allowed_source_count=len(allowed),
        )
    return _CitationValidationResult(
        valid=True,
        degrade_reason="",
        referenced_source_ids=referenced,
        invalid_source_ids=(),
        allowed_source_count=len(allowed),
    )


def _append_reference_sources(
    answer: str,
    *,
    allowed_candidates: tuple[QueryAllowedCandidate, ...],
    max_sources: int = 3,
) -> str:
    answer = answer.strip()
    if not answer or not allowed_candidates:
        return answer
    source_ids: list[str] = []
    seen: set[str] = set()
    for allowed in allowed_candidates:
        source_id = allowed.candidate.chunk_id
        if source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
        if len(source_ids) >= max_sources:
            break
    if not source_ids:
        return answer
    source_refs = " ".join(f"[source:{source_id}]" for source_id in source_ids)
    return f"{answer}\n\n参考来源：{source_refs}"


def _strip_source_refs_for_display(answer: str) -> str:
    """移除 LLM 引用校验标记，只保留用户可读答案。

    QueryService 会先用 [source:...] 完成 citation 防伪校验；校验后这些内部标记
    由结构化 citations 承担展示职责，不应继续混在自然语言答案里。
    """

    without_reference_line = REFERENCE_SOURCE_LINE_PATTERN.sub("", answer)
    without_inline_refs = SOURCE_REF_DISPLAY_PATTERN.sub("", without_reference_line)
    lines = [line.rstrip() for line in without_inline_refs.splitlines()]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compact_lines.append(line)
        previous_blank = blank
    return "\n".join(compact_lines).strip()


def _citation_validation_summary(
    validation: _CitationValidationResult,
    *,
    final_degrade_reason: str,
) -> dict[str, object]:
    summary = validation.summary()
    if final_degrade_reason != validation.degrade_reason:
        summary["original_degrade_reason"] = validation.degrade_reason
        summary["degrade_reason"] = final_degrade_reason
        summary["auto_attached_sources"] = True
    return summary


def _degraded_answer(
    *,
    query_text: str,
    degrade_reasons: tuple[str, ...],
    citation_count: int,
    candidate_count: int,
) -> str:
    reason_messages = _degrade_reason_messages(degrade_reasons)
    query_summary = _brief_query(query_text)
    if citation_count > 0:
        retrieval_summary = (
            f"系统找到了 {citation_count} 条当前账号可访问的引用资料，"
            "但没有生成可直接采信的业务答案。"
        )
        next_step = "你可以先查看下方引用资料，或换一种更具体的问题重新查询。"
    elif candidate_count > 0:
        retrieval_summary = (
            "系统找到了一些候选片段，但这些片段没有形成可用于回答的最终上下文。"
        )
        next_step = "请检查相关文档是否已完成索引、权限快照是否已刷新，或缩小问题范围后重试。"
    else:
        retrieval_summary = (
            "系统没有在当前账号可访问、已发布且已索引的知识库内容中找到匹配资料。"
        )
        next_step = "请确认知识库中已有可访问文档、文档已索引完成，或选择其他知识库后重试。"

    return "\n".join(
        [
            f"我没有得到可以直接回答“{query_summary}”的可靠答案。",
            f"本次处理结果：{retrieval_summary}",
            f"没有答案的原因：{'；'.join(reason_messages)}。",
            next_step,
        ]
    )


def _degrade_reason_messages(reasons: tuple[str, ...]) -> tuple[str, ...]:
    messages: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        message = _degrade_reason_message(reason)
        if message in seen:
            continue
        seen.add(message)
        messages.append(message)
    return tuple(messages) or ("系统进入降级流程，但没有提供更具体的原因",)


def _degrade_reason_message(reason: str) -> str:
    if reason == "llm_context_empty":
        return "没有可用于生成答案的上下文，通常是文档为空、未检索到内容或权限过滤后无可用片段"
    if reason == "llm_runtime_config_unavailable":
        return "回答生成服务未完成可用配置"
    if reason == "llm_stream_result_missing":
        return "流式回答结束时没有得到有效的模型输出"
    if reason == "citation_missing":
        return "模型生成的回答缺少可验证引用，系统已拦截原回答"
    if reason == "citation_auto_attached":
        return "模型生成的回答缺少引用标记，系统已自动附加本次已授权来源"
    if reason == "citation_invalid_format":
        return "模型生成的回答使用了不存在的引用占位符，系统已拦截原回答"
    if reason == "citation_unauthorized":
        return "模型生成的回答引用了本次查询未授权或未命中的资料，系统已拦截原回答"
    if reason in {
        "vector_retriever_unavailable",
        "vector_runtime_config_unavailable",
        "vector_runtime_config_incomplete",
    }:
        return "向量检索能力不可用，本次只能依赖关键词检索"
    if reason == "vector_collection_unavailable":
        return "当前知识库没有可用的向量集合"
    if reason == "query_embedding_failed":
        return "问题向量化失败，本次只能依赖关键词检索"
    if reason == "vector_search_failed":
        return "向量数据库检索失败，本次只能依赖关键词检索"
    if reason == "retrieval_relevance_too_low":
        return "召回片段与问题相关性过低，系统未将这些片段交给模型生成答案"
    if reason in {
        "RERANK_PROVIDER_UNAVAILABLE",
        "RERANK_PROVIDER_HTTP_ERROR",
        "RERANK_PROVIDER_RESPONSE_INVALID",
        "QUERY_RERANK_INPUT_UNAVAILABLE",
        "rerank_input_mismatch",
    }:
        return "候选精排不可用，系统已使用检索排序继续处理"
    if reason in {
        "LLM_PROVIDER_HTTP_ERROR",
        "LLM_PROVIDER_UNAVAILABLE",
        "LLM_PROVIDER_RESPONSE_INVALID",
    }:
        return "回答生成模型不可用、超时或返回异常"
    return f"系统降级原因代码为 {reason}"


def _citation_validation_risk_level(reason: str) -> Literal["medium", "high", "critical"]:
    if reason == "citation_unauthorized":
        return "high"
    return "medium"


def _brief_query(query_text: str, *, limit: int = 80) -> str:
    compact = " ".join(query_text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _query_hash(query_text: str) -> str:
    return stable_json_hash({"query": query_text})


def _index_version_hash(index_version_ids: tuple[str, ...]) -> str:
    return stable_json_hash({"active_index_version_ids": sorted(index_version_ids)})


def _confidence(citations: tuple[QueryCitation, ...]) -> Literal["low", "medium", "high"]:
    if len(citations) >= 3:
        return "medium"
    return "low"


def _elapsed_ms(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)


def _database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> QueryServiceError:
    return QueryServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
