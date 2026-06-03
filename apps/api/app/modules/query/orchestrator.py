"""Query workflow orchestration boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any

from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.permissions import PermissionServiceError
from app.modules.query import citation_validator, degrade_policy
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import (
    QueryAllowedCandidate,
    QueryCitation,
    QueryResult,
    QueryScopeSummary,
    QueryStreamPlan,
    _QueryAuditEvent,
)
from app.modules.query.utils import (
    _allowed_candidates_from_retrieval,
    _apply_relevance_gate,
    _build_filter_clause,
    _confidence,
    _elapsed_ms,
    _index_version_hash,
    _normalize_ids,
    _normalize_query,
    _query_hash,
    _truncate_error_message,
)
from app.modules.query_rewrite import (
    QueryRewriteInput,
    QueryRewriteItem,
    RewriteConversationMessage,
)
from app.modules.retrieval import RerankResult, RetrievalCandidate, RetrievalModelCall
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class _AnswerFinalization:
    answer: str
    answer_result: AnswerGenerationResult | None
    model_route_hash: str | None
    audit_events: list[_QueryAuditEvent]
    degrade_reasons: list[str]


@dataclass(frozen=True)
class _RetrievalQuery:
    query: str
    index: int
    intent: str | None
    weight: float


@dataclass(frozen=True)
class _RerankExecution:
    result: RerankResult
    model_calls: tuple[RetrievalModelCall, ...]
    diagnostics: tuple[dict[str, object], ...] = ()


class QueryOrchestrator:
    """编排查询计划构建、答案生成收束和查询审计写入。"""

    def __init__(self, service: Any) -> None:
        self._service = service

    def create_query(self, session: Session, **kwargs: Any) -> QueryResult:
        plan = self.create_query_stream_plan(session, **kwargs)
        answer_result = None
        if plan.mode == "answer":
            answer_result = self._service.answer_service.generate(
                query_context=plan.query_context
            )
        return self._finalize_query(
            session,
            plan=plan,
            answer_result=answer_result,
            answer_caller="query.answer",
            fallback_to_plan_model_route=False,
        )

    def create_query_stream_plan(self, session: Session, **kwargs: Any) -> QueryStreamPlan:
        return self._build_query_plan(session, **kwargs)

    def finalize_query_stream(
        self,
        session: Session,
        *,
        plan: QueryStreamPlan,
        answer_result: AnswerGenerationResult,
    ) -> QueryResult:
        return self._finalize_query(
            session,
            plan=plan,
            answer_result=answer_result,
            answer_caller="query.answer_stream",
            fallback_to_plan_model_route=True,
        )

    def _build_query_plan(
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
        history: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
    ) -> QueryStreamPlan:
        started_at = time.monotonic()
        normalized_query = _normalize_query(query_text)
        normalized_kb_ids = _normalize_ids(kb_ids)
        normalized_top_k = min(max(top_k, 1), 50)
        request_filters = filters or {}
        filter_clause = _build_filter_clause(request_filters)
        config_version = self._service._load_active_config_version(session)

        try:
            context = self._service.permission_service.build_context(
                session,
                user_id=user_id,
                enterprise_id=enterprise_id,
                request_id=request_id,
            )
            if normalized_kb_ids:
                queryable_kb_ids = (
                    self._service.permission_service.require_queryable_knowledge_bases(
                        session,
                        context,
                        kb_ids=normalized_kb_ids,
                        required_scope="rag:query",
                    )
                )
                query_scope_mode = "explicit"
            else:
                queryable_kb_ids = (
                    self._service.permission_service.list_queryable_knowledge_base_ids(
                        session,
                        context,
                        required_scope="rag:query",
                    )
                )
                query_scope_mode = "auto_all_accessible"
            if not queryable_kb_ids:
                degrade_reasons = (
                    ["query_scope_empty"] if query_scope_mode == "auto_all_accessible" else []
                )
                return QueryStreamPlan(
                    request_id=request_id,
                    trace_id=trace_id,
                    mode=mode,
                    started_at=started_at,
                    normalized_query=normalized_query,
                    normalized_kb_ids=queryable_kb_ids,
                    config_version=config_version,
                    context=context,
                    query_context=None,
                    allowed_candidates=(),
                    citations=(),
                    confidence=_confidence(()),
                    pre_degrade_reasons=tuple(degrade_reasons),
                    audit_events=(),
                    rerank_model_calls=(),
                    model_route_hash=None,
                    candidate_count=0,
                    permission_filter_hash=context.permission_filter_hash,
                    permission_version=context.permission_version,
                    index_version_hash=_index_version_hash(()),
                    query_scope_mode=query_scope_mode,
                    rewritten_queries=(normalized_query,),
                    retrieval_diagnostics={
                        "rewrite_queries": [],
                        "stage_counts": {
                            "resolved_kb_count": 0,
                            "candidate_count": 0,
                            "citation_count": 0,
                        },
                        "quality_gate": {"reason": "query_scope_empty"},
                        "selected_chunks": [],
                    },
                )
            query_context = None
            allowed_candidates: tuple[QueryAllowedCandidate, ...] = ()
            citations: tuple[QueryCitation, ...] = ()
            rerank_model_calls: tuple[RetrievalModelCall, ...] = ()
            query_rewrite_model_call: RetrievalModelCall | None = None
            model_route_hash: str | None = None
            audit_events: list[_QueryAuditEvent] = []
            degrade_reasons: list[str] = []
            active_indexes = self._service._load_active_index_versions(
                session,
                enterprise_id=context.enterprise_id,
                kb_ids=queryable_kb_ids,
            )
            active_index_ids = tuple(index.id for index in active_indexes)
            collection_names = tuple(index.collection_name for index in active_indexes)
            index_version_hash = _index_version_hash(active_index_ids)
            if active_index_ids:
                rewrite_result = self._service.query_rewrite_service.rewrite(
                    QueryRewriteInput(
                        original_query=normalized_query,
                        conversation_messages=_rewrite_history_messages(history or ()),
                        max_queries=self._service.query_rewrite_service.max_queries,
                    )
                )
                retrieval_queries = _retrieval_queries(
                    rewrite_result.rewritten_queries,
                    original_query=normalized_query,
                    weights=self._service.retrieval_weights,
                )
                rewritten_queries = tuple(item.query for item in retrieval_queries)
                query_rewrite_model_call = rewrite_result.model_call
                permission_filter = self._service.permission_service.build_filter(
                    context,
                    kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    required_scope="rag:query",
                )
                keyword_candidates: tuple[Any, ...] = ()
                vector_candidates: tuple[Any, ...] = ()
                per_query_recall: list[dict[str, object]] = []
                per_query_limit = normalized_top_k * 3
                for retrieval_query in retrieval_queries:
                    keyword_result = self._service._keyword_search(
                        session,
                        permission_filter=permission_filter,
                        query_text=retrieval_query.query,
                        filter_clause=filter_clause,
                        limit=per_query_limit,
                    )
                    query_vector_degraded = False
                    query_vector_degrade_reason: str | None = None
                    keyword_candidates += _annotate_candidates(
                        keyword_result,
                        retrieval_query=retrieval_query,
                        source_weight=_source_weight(self._service.retrieval_weights, "keyword"),
                    )
                    vector_result = self._service.vector_retriever.search(
                        query_text=retrieval_query.query,
                        permission_filter=permission_filter,
                        collection_names=collection_names,
                        top_k=per_query_limit,
                    )
                    if vector_result.degraded:
                        query_vector_degraded = True
                        query_vector_degrade_reason = (
                            vector_result.degrade_reason or "vector_retrieval_degraded"
                        )
                        _append_unique(
                            degrade_reasons,
                            query_vector_degrade_reason,
                        )
                    vector_candidates += _annotate_candidates(
                        vector_result.candidates,
                        retrieval_query=retrieval_query,
                        source_weight=_source_weight(self._service.retrieval_weights, "vector"),
                    )
                    per_query_recall.append(
                        {
                            "index": retrieval_query.index,
                            "query": retrieval_query.query,
                            "intent": retrieval_query.intent,
                            "weight": retrieval_query.weight,
                            "keyword_candidate_count": len(keyword_result),
                            "vector_candidate_count": len(vector_result.candidates),
                            "vector_degraded": query_vector_degraded,
                            "vector_degrade_reason": query_vector_degrade_reason,
                        }
                    )
                raw_candidates = keyword_candidates + vector_candidates
                fusion_limit = max(normalized_top_k * 3, len(raw_candidates))
                candidates = self._service.fusion_service.fuse(
                    raw_candidates,
                    limit=fusion_limit,
                )
                coverage_indexes = _coverage_query_indexes(
                    retrieval_queries,
                    original_query=normalized_query,
                )
                rerank_input_candidates = _prioritize_query_quota(
                    candidates,
                    retrieval_queries=retrieval_queries,
                    original_query=normalized_query,
                    per_query_limit=_per_query_top_k(
                        self._service.rerank_input_top_k,
                        coverage_indexes,
                    ),
                )
                gate_execution = self._service._gate_candidates_with_diagnostics(
                    session,
                    context,
                    rerank_input_candidates,
                    allowed_kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    limit=max(
                        normalized_top_k,
                        self._service.rerank_input_top_k,
                        len(coverage_indexes),
                    ),
                )
                allowed_candidates = gate_execution.allowed_candidates
                gated_allowed_candidates = allowed_candidates
                rerank_execution = _rerank_allowed_candidates_for_retrieval_queries(
                    self._service,
                    session,
                    original_query=normalized_query,
                    retrieval_queries=retrieval_queries,
                    allowed_candidates=allowed_candidates,
                    top_k=max(len(allowed_candidates), normalized_top_k),
                    per_query_top_k=max(
                        _per_query_top_k(normalized_top_k, coverage_indexes),
                        1,
                    ),
                )
                rerank_result = rerank_execution.result
                if rerank_result.degraded:
                    rerank_degrade_reason = rerank_result.degrade_reason or "rerank_degraded"
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
                rerank_model_calls = rerank_execution.model_calls
                model_route_hash = _model_route_hash_from_calls(rerank_model_calls)
                relevant_candidates, relevance_audit_event = _apply_relevance_gate(
                    rerank_result,
                    min_score=self._service.rerank_min_score,
                    candidate_count=len(allowed_candidates),
                )
                if relevance_audit_event is not None:
                    degrade_reasons.append("retrieval_relevance_too_low")
                    audit_events.append(relevance_audit_event)
                relevant_candidates = _select_candidates_with_query_coverage(
                    relevant_candidates,
                    retrieval_queries=retrieval_queries,
                    original_query=normalized_query,
                    limit=max(normalized_top_k, len(coverage_indexes)),
                )
                quality_result = self._service.candidate_quality_gate.evaluate(
                    relevant_candidates,
                    rerank_result=rerank_result,
                )
                if quality_result.quality_reason is not None:
                    degrade_reasons.append(quality_result.quality_reason)
                    audit_events.append(
                        _QueryAuditEvent(
                            event_name="query.quality_gate_failed",
                            result="failure",
                            risk_level="medium",
                            error_code=quality_result.quality_reason,
                            summary={
                                "degrade_reason": quality_result.quality_reason,
                                "top_score": quality_result.top_score,
                                "candidate_count": len(relevant_candidates),
                                "rejected_count": quality_result.rejected_count,
                                "min_fusion_score": (
                                    self._service.candidate_quality_gate.min_fusion_score
                                ),
                                "min_source_score": (
                                    self._service.candidate_quality_gate.min_source_score
                                ),
                            },
                        )
                    )
                final_primary_candidates = _select_candidates_with_query_coverage(
                    quality_result.accepted_candidates,
                    retrieval_queries=retrieval_queries,
                    original_query=normalized_query,
                    limit=max(normalized_top_k, len(coverage_indexes)),
                )
                primary_allowed_candidates = _allowed_candidates_from_retrieval(
                    final_primary_candidates
                )
                expanded_allowed_candidates = (
                    self._service._expand_context_candidates(
                        session,
                        context,
                        primary_allowed_candidates,
                        allowed_kb_ids=queryable_kb_ids,
                        active_index_version_ids=active_index_ids,
                        limit=max(
                            normalized_top_k,
                            self._service.context_builder.max_chunks
                            * (1 + self._service.context_expand_neighbors * 2),
                        ),
                    )
                    if mode == "answer"
                    else primary_allowed_candidates
                )
                allowed_candidates = expanded_allowed_candidates
                if mode == "answer":
                    query_context = self._service.context_builder.build(
                        session,
                        query_text=normalized_query,
                        allowed_candidates=expanded_allowed_candidates,
                    )
                    allowed_candidates = _allowed_candidates_for_context(
                        query_context,
                        expanded_allowed_candidates,
                    )
                citations = (
                    tuple(item.citation for item in allowed_candidates)
                    if include_sources
                    else ()
                )
                candidate_count = len(candidates)
                retrieval_diagnostics = _retrieval_diagnostics(
                    retrieval_queries=retrieval_queries,
                    resolved_kb_count=len(queryable_kb_ids),
                    keyword_candidate_count=len(keyword_candidates),
                    vector_candidate_count=len(vector_candidates),
                    fused_candidate_count=len(candidates),
                    gated_candidate_count=len(gated_allowed_candidates),
                    relevant_candidate_count=len(relevant_candidates),
                    quality_rejected_count=quality_result.rejected_count,
                    context_candidate_count=len(expanded_allowed_candidates),
                    citation_count=len(citations),
                    quality_reason=quality_result.quality_reason,
                    quality_top_score=quality_result.top_score,
                    per_query_recall=tuple(per_query_recall),
                    fused_candidates=candidates,
                    gated_candidates=gated_allowed_candidates,
                    relevant_candidates=relevant_candidates,
                    gate_diagnostics=gate_execution.diagnostics,
                    rerank_diagnostics=rerank_execution.diagnostics,
                    query_context=query_context,
                )
                permission_filter_hash = permission_filter.permission_filter_hash
                permission_version = permission_filter.permission_version
            else:
                candidate_count = 0
                permission_filter_hash = context.permission_filter_hash
                permission_version = context.permission_version
                rewritten_queries = (normalized_query,)
                retrieval_diagnostics = {
                    "rewrite_queries": [],
                    "stage_counts": {
                        "resolved_kb_count": len(queryable_kb_ids),
                        "candidate_count": 0,
                        "citation_count": 0,
                    },
                    "quality_gate": {"reason": "active_index_empty"},
                    "selected_chunks": [],
                }

            return QueryStreamPlan(
                request_id=request_id,
                trace_id=trace_id,
                mode=mode,
                started_at=started_at,
                normalized_query=normalized_query,
                normalized_kb_ids=queryable_kb_ids,
                config_version=config_version,
                context=context,
                query_context=query_context,
                allowed_candidates=allowed_candidates,
                citations=citations,
                confidence=_confidence(citations),
                pre_degrade_reasons=tuple(degrade_reasons),
                audit_events=tuple(audit_events),
                rerank_model_calls=rerank_model_calls,
                model_route_hash=model_route_hash,
                candidate_count=candidate_count,
                permission_filter_hash=permission_filter_hash,
                permission_version=permission_version,
                index_version_hash=index_version_hash,
                query_scope_mode=query_scope_mode,
                rewritten_queries=rewritten_queries,
                query_rewrite_model_call=query_rewrite_model_call,
                retrieval_diagnostics=retrieval_diagnostics,
            )
        except PermissionServiceError as exc:
            self._service._insert_denied_query_log(
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
                query_scope_mode=(
                    "explicit" if normalized_kb_ids else "auto_all_accessible"
                ),
            )
            self._service._insert_query_audit_log(
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

    def _finalize_query(
        self,
        session: Session,
        *,
        plan: QueryStreamPlan,
        answer_result: AnswerGenerationResult | None,
        answer_caller: str,
        fallback_to_plan_model_route: bool,
    ) -> QueryResult:
        finalization = self._finalize_answer(
            plan,
            answer_result=answer_result,
            fallback_to_plan_model_route=fallback_to_plan_model_route,
        )
        degraded = bool(finalization.degrade_reasons)
        degrade_reason = (
            ";".join(finalization.degrade_reasons)
            if finalization.degrade_reasons
            else None
        )
        result = QueryResult(
            request_id=plan.request_id,
            answer=finalization.answer,
            citations=plan.citations,
            confidence=plan.confidence,
            degraded=degraded,
            degrade_reason=degrade_reason,
            trace_id=plan.trace_id,
            query_scope=QueryScopeSummary(
                mode=plan.query_scope_mode,
                resolved_kb_count=len(plan.normalized_kb_ids),
            ),
            kb_ids=plan.normalized_kb_ids,
            context=plan.query_context,
        )
        if (
            finalization.answer_result is not None
            and finalization.answer_result.model_call_attempted
        ):
            self._service._insert_model_call_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                config_version=plan.config_version,
                caller=answer_caller,
                answer_result=finalization.answer_result,
            )
        for rerank_model_call in plan.rerank_model_calls:
            self._service._insert_retrieval_model_call_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                config_version=plan.config_version,
                caller="query.rerank",
                model_call=rerank_model_call,
            )
        if plan.query_rewrite_model_call is not None:
            self._service._insert_retrieval_model_call_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                config_version=plan.config_version,
                caller="query.rewrite",
                model_call=plan.query_rewrite_model_call,
            )
        for audit_event in finalization.audit_events:
            self._service._insert_query_audit_log(
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
        self._service._insert_query_log(
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
            model_route_hash=finalization.model_route_hash,
            latency_ms=_elapsed_ms(plan.started_at),
            candidate_count=plan.candidate_count,
            citation_count=len(plan.citations),
            error_code=None,
            query_scope_mode=plan.query_scope_mode,
            resolved_kb_count=len(plan.normalized_kb_ids),
            rewrite_count=len(plan.rewritten_queries),
            retrieval_diagnostics=plan.retrieval_diagnostics,
        )
        return result

    def _finalize_answer(
        self,
        plan: QueryStreamPlan,
        *,
        answer_result: AnswerGenerationResult | None,
        fallback_to_plan_model_route: bool,
    ) -> _AnswerFinalization:
        answer = answer_result.answer if answer_result is not None else ""
        if answer_result is None:
            model_route_hash = plan.model_route_hash
        elif fallback_to_plan_model_route:
            model_route_hash = answer_result.model_route_hash or plan.model_route_hash
        else:
            model_route_hash = answer_result.model_route_hash
        audit_events = list(plan.audit_events)
        degrade_reasons = list(plan.pre_degrade_reasons)
        if answer_result is not None and answer_result.degraded:
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
            citation_validation = citation_validator.validate_answer_citations(
                answer,
                allowed_source_ids=tuple(
                    allowed.candidate.chunk_id for allowed in plan.allowed_candidates
                ),
            )
            if not citation_validation.valid:
                citation_degrade_reason = citation_validation.degrade_reason
                if citation_validation.degrade_reason in {
                    "citation_missing",
                    "citation_invalid_format",
                }:
                    if citation_validation.degrade_reason == "citation_invalid_format":
                        answer = citation_validator.strip_source_refs_for_display(answer)
                    repaired_answer = citation_validator.append_reference_sources(
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
                if citation_degrade_reason != "citation_auto_attached":
                    degrade_reasons.append(citation_degrade_reason)
                audit_events.append(
                    _QueryAuditEvent(
                        event_name="query.citation_validation_failed",
                        result="failure",
                        risk_level=citation_validator.citation_validation_risk_level(
                            citation_degrade_reason
                        ),
                        error_code=citation_degrade_reason,
                        summary=citation_validator.citation_validation_summary(
                            citation_validation,
                            final_degrade_reason=citation_degrade_reason,
                        ),
                    )
                )
        if plan.mode == "answer" and not answer and degrade_reasons:
            answer = degrade_policy.degraded_answer(
                query_text=plan.normalized_query,
                degrade_reasons=tuple(degrade_reasons),
                citation_count=len(plan.citations),
                candidate_count=plan.candidate_count,
            )
        if plan.mode == "answer" and answer:
            answer = citation_validator.strip_source_refs_for_display(answer)
        return _AnswerFinalization(
            answer=answer,
            answer_result=answer_result,
            model_route_hash=model_route_hash,
            audit_events=audit_events,
            degrade_reasons=degrade_reasons,
        )


def _rewrite_history_messages(
    history: list[dict[str, str]] | tuple[dict[str, str], ...],
) -> tuple[RewriteConversationMessage, ...]:
    messages: list[RewriteConversationMessage] = []
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        compact = " ".join(content.split()).strip()
        if not compact:
            continue
        messages.append(RewriteConversationMessage(role=role, content=compact[:1000]))
    return tuple(messages)


def _append_unique(values: list[str], item: str) -> None:
    if item not in values:
        values.append(item)


def _allowed_candidates_for_context(
    query_context: Any,
    allowed_candidates: tuple[QueryAllowedCandidate, ...],
) -> tuple[QueryAllowedCandidate, ...]:
    if query_context is None or not getattr(query_context, "chunks", ()):
        return ()
    by_chunk_id = {item.candidate.chunk_id: item for item in allowed_candidates}
    selected: list[QueryAllowedCandidate] = []
    seen: set[str] = set()
    for chunk in query_context.chunks:
        if chunk.chunk_id in seen:
            continue
        item = by_chunk_id.get(chunk.chunk_id)
        if item is None:
            continue
        selected.append(item)
        seen.add(chunk.chunk_id)
    return tuple(selected)


def _rerank_allowed_candidates_for_retrieval_queries(
    service: Any,
    session: Session,
    *,
    original_query: str,
    retrieval_queries: tuple[_RetrievalQuery, ...],
    allowed_candidates: tuple[QueryAllowedCandidate, ...],
    top_k: int,
    per_query_top_k: int,
) -> _RerankExecution:
    coverage_indexes = _coverage_query_indexes(
        retrieval_queries,
        original_query=original_query,
    )
    if len(coverage_indexes) <= 1:
        result = service._rerank_allowed_candidates(
            session,
            query_text=original_query,
            allowed_candidates=allowed_candidates,
            top_k=top_k,
        )
        query = retrieval_queries[0] if retrieval_queries else None
        return _RerankExecution(
            result=result,
            model_calls=_model_calls(result),
            diagnostics=(
                _rerank_diagnostic(
                    query_index=query.index if query else 0,
                    query_text=query.query if query else original_query,
                    input_count=len(allowed_candidates),
                    result=result,
                ),
            ),
        )

    query_by_index = {item.index: item for item in retrieval_queries}
    groups = _allowed_candidates_by_query_index(allowed_candidates)
    reranked_groups: list[tuple[RetrievalCandidate, ...]] = []
    model_calls: list[RetrievalModelCall] = []
    diagnostics: list[dict[str, object]] = []
    degraded = False
    degrade_reason: str | None = None
    primary_model_call: RetrievalModelCall | None = None

    for query_index in coverage_indexes:
        group = groups.get(query_index, ())
        query = query_by_index.get(query_index)
        if not group or query is None:
            continue
        group_result = service._rerank_allowed_candidates(
            session,
            query_text=query.query,
            allowed_candidates=group,
            top_k=max(per_query_top_k, 1),
        )
        diagnostics.append(
            _rerank_diagnostic(
                query_index=query.index,
                query_text=query.query,
                input_count=len(group),
                result=group_result,
            )
        )
        if group_result.model_call is not None:
            model_calls.append(group_result.model_call)
            if primary_model_call is None:
                primary_model_call = group_result.model_call
        if group_result.degraded:
            degraded = True
            if degrade_reason is None:
                degrade_reason = group_result.degrade_reason
        reranked_groups.append(group_result.candidates)

    filler_candidates = tuple(
        item.candidate
        for item in allowed_candidates
        if item.candidate.matched_query_index not in set(coverage_indexes)
    )
    merged_candidates = _interleave_reranked_groups(
        tuple(reranked_groups),
        filler_candidates=filler_candidates,
        limit=top_k,
    )
    if not merged_candidates and allowed_candidates:
        merged_candidates = tuple(item.candidate for item in allowed_candidates[:top_k])
    return _RerankExecution(
        result=RerankResult(
            candidates=merged_candidates,
            degraded=degraded,
            degrade_reason=degrade_reason,
            model_call=primary_model_call,
        ),
        model_calls=tuple(model_calls),
        diagnostics=tuple(diagnostics),
    )


def _model_calls(result: RerankResult) -> tuple[RetrievalModelCall, ...]:
    return (result.model_call,) if result.model_call is not None else ()


def _rerank_diagnostic(
    *,
    query_index: int,
    query_text: str,
    input_count: int,
    result: RerankResult,
) -> dict[str, object]:
    model_call = result.model_call
    return {
        "query_index": query_index,
        "query": query_text,
        "input_candidate_count": input_count,
        "output_candidate_count": len(result.candidates),
        "degraded": result.degraded,
        "degrade_reason": result.degrade_reason,
        "model_status": model_call.status if model_call is not None else "not_called",
        "scores": _candidate_score_summaries(result.candidates),
    }


def _model_route_hash_from_calls(calls: tuple[RetrievalModelCall, ...]) -> str | None:
    for call in calls:
        if call.model_route_hash:
            return call.model_route_hash
    return None


def _allowed_candidates_by_query_index(
    allowed_candidates: tuple[QueryAllowedCandidate, ...],
) -> dict[int, tuple[QueryAllowedCandidate, ...]]:
    grouped: dict[int, list[QueryAllowedCandidate]] = {}
    for item in allowed_candidates:
        grouped.setdefault(item.candidate.matched_query_index, []).append(item)
    return {index: tuple(items) for index, items in grouped.items()}


def _interleave_reranked_groups(
    groups: tuple[tuple[RetrievalCandidate, ...], ...],
    *,
    filler_candidates: tuple[RetrievalCandidate, ...],
    limit: int,
) -> tuple[RetrievalCandidate, ...]:
    selected: list[RetrievalCandidate] = []
    seen: set[str] = set()
    max_group_length = max((len(group) for group in groups), default=0)
    for offset in range(max_group_length):
        for group in groups:
            if offset >= len(group):
                continue
            _append_candidate_if_new(selected, seen, group[offset], limit=limit)
            if len(selected) >= limit:
                return _rerank_ranked(selected)
    for candidate in filler_candidates:
        _append_candidate_if_new(selected, seen, candidate, limit=limit)
        if len(selected) >= limit:
            break
    return _rerank_ranked(selected)


def _append_candidate_if_new(
    selected: list[RetrievalCandidate],
    seen: set[str],
    candidate: RetrievalCandidate,
    *,
    limit: int,
) -> None:
    if len(selected) >= max(limit, 0):
        return
    if candidate.chunk_id in seen:
        return
    seen.add(candidate.chunk_id)
    selected.append(candidate)


def _rerank_ranked(candidates: list[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        replace(candidate, rank=rank)
        for rank, candidate in enumerate(candidates, start=1)
    )


def _per_query_top_k(top_k: int, coverage_indexes: tuple[int, ...]) -> int:
    query_count = len(coverage_indexes)
    if query_count <= 0:
        return max(top_k, 1)
    return max((max(top_k, 1) + query_count - 1) // query_count, 1)


def _coverage_query_indexes(
    retrieval_queries: tuple[_RetrievalQuery, ...],
    *,
    original_query: str,
) -> tuple[int, ...]:
    if not retrieval_queries:
        return ()
    specific_indexes = tuple(
        item.index
        for item in retrieval_queries
        if item.intent != "original" and item.query != original_query
    )
    if specific_indexes:
        return specific_indexes
    return (retrieval_queries[0].index,)


def _prioritize_query_coverage(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    retrieval_queries: tuple[_RetrievalQuery, ...],
    original_query: str,
) -> tuple[RetrievalCandidate, ...]:
    coverage_indexes = _coverage_query_indexes(
        retrieval_queries,
        original_query=original_query,
    )
    if len(coverage_indexes) <= 1 or not candidates:
        return candidates
    coverage_candidates = _first_candidate_per_query(candidates, coverage_indexes)
    return _merge_candidates(coverage_candidates, candidates)


def _prioritize_query_quota(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    retrieval_queries: tuple[_RetrievalQuery, ...],
    original_query: str,
    per_query_limit: int,
) -> tuple[RetrievalCandidate, ...]:
    coverage_indexes = _coverage_query_indexes(
        retrieval_queries,
        original_query=original_query,
    )
    if len(coverage_indexes) <= 1 or not candidates:
        return candidates
    groups = _candidates_by_query_index(candidates)
    prioritized: list[RetrievalCandidate] = []
    for offset in range(max(per_query_limit, 1)):
        for query_index in coverage_indexes:
            group = groups.get(query_index, ())
            if offset < len(group):
                prioritized.append(group[offset])
    return _merge_candidates(tuple(prioritized), candidates)


def _select_candidates_with_query_coverage(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    retrieval_queries: tuple[_RetrievalQuery, ...],
    original_query: str,
    limit: int,
) -> tuple[RetrievalCandidate, ...]:
    if not candidates or limit <= 0:
        return ()
    coverage_indexes = _coverage_query_indexes(
        retrieval_queries,
        original_query=original_query,
    )
    effective_limit = max(limit, len(coverage_indexes), 1)
    coverage_candidates = _first_candidate_per_query(candidates, coverage_indexes)
    selected = list(_merge_candidates(coverage_candidates, candidates))
    return tuple(selected[:effective_limit])


def _candidates_by_query_index(
    candidates: tuple[RetrievalCandidate, ...],
) -> dict[int, tuple[RetrievalCandidate, ...]]:
    grouped: dict[int, list[RetrievalCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.matched_query_index, []).append(candidate)
    return {index: tuple(items) for index, items in grouped.items()}


def _first_candidate_per_query(
    candidates: tuple[RetrievalCandidate, ...],
    query_indexes: tuple[int, ...],
) -> tuple[RetrievalCandidate, ...]:
    selected: list[RetrievalCandidate] = []
    seen: set[int] = set()
    wanted = set(query_indexes)
    for candidate in candidates:
        query_index = candidate.matched_query_index
        if query_index not in wanted or query_index in seen:
            continue
        selected.append(candidate)
        seen.add(query_index)
        if len(seen) >= len(wanted):
            break
    return tuple(selected)


def _merge_candidates(
    first: tuple[RetrievalCandidate, ...],
    rest: tuple[RetrievalCandidate, ...],
) -> tuple[RetrievalCandidate, ...]:
    merged: list[RetrievalCandidate] = []
    seen: set[str] = set()
    for candidate in (*first, *rest):
        if candidate.chunk_id in seen:
            continue
        seen.add(candidate.chunk_id)
        merged.append(candidate)
    return tuple(merged)


def _retrieval_queries(
    items: tuple[QueryRewriteItem, ...],
    *,
    original_query: str,
    weights: dict[str, float],
) -> tuple[_RetrievalQuery, ...]:
    prepared: list[_RetrievalQuery] = []
    seen: set[str] = set()
    source_items = items or (QueryRewriteItem(query=original_query, intent="original"),)
    for index, item in enumerate(source_items):
        query = " ".join(item.query.split()).strip()
        if not query or query in seen:
            continue
        seen.add(query)
        is_original = item.intent == "original" or query == original_query
        base_weight = _source_weight(weights, "original_query" if is_original else "rewrite_query")
        prepared.append(
            _RetrievalQuery(
                query=query,
                index=index,
                intent=item.intent,
                weight=max(float(item.weight), 0.0) * base_weight,
            )
        )
    if prepared:
        return tuple(prepared)
    return (
        _RetrievalQuery(
            query=original_query,
            index=0,
            intent="original",
            weight=_source_weight(weights, "original_query"),
        ),
    )


def _annotate_candidates(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    retrieval_query: _RetrievalQuery,
    source_weight: float,
) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        replace(
            candidate,
            matched_query=retrieval_query.query,
            matched_query_index=retrieval_query.index,
            query_weight=retrieval_query.weight,
            source_weight=source_weight,
            source_score=candidate.source_score or candidate.score,
        )
        for candidate in candidates
    )


def _source_weight(weights: dict[str, float], key: str) -> float:
    value = weights.get(key)
    return max(float(value), 0.0) if isinstance(value, int | float) else 1.0


def _retrieval_diagnostics(
    *,
    retrieval_queries: tuple[_RetrievalQuery, ...],
    resolved_kb_count: int,
    keyword_candidate_count: int,
    vector_candidate_count: int,
    fused_candidate_count: int,
    gated_candidate_count: int,
    relevant_candidate_count: int,
    quality_rejected_count: int,
    context_candidate_count: int,
    citation_count: int,
    quality_reason: str | None,
    quality_top_score: float,
    per_query_recall: tuple[dict[str, object], ...],
    fused_candidates: tuple[RetrievalCandidate, ...],
    gated_candidates: tuple[QueryAllowedCandidate, ...],
    relevant_candidates: tuple[RetrievalCandidate, ...],
    gate_diagnostics: Any,
    rerank_diagnostics: tuple[dict[str, object], ...],
    query_context: Any,
) -> dict[str, object]:
    fused_by_query = _candidate_counts_by_query_index(fused_candidates)
    gated_by_query = _allowed_candidate_counts_by_query_index(gated_candidates)
    relevant_by_query = _candidate_counts_by_query_index(relevant_candidates)
    context_by_query = _context_chunk_counts_by_query_index(query_context)
    return {
        "rewrite_queries": [
            {
                "query": item.query,
                "index": item.index,
                "intent": item.intent,
                "weight": item.weight,
            }
            for item in retrieval_queries
        ],
        "stage_counts": {
            "resolved_kb_count": resolved_kb_count,
            "keyword_candidate_count": keyword_candidate_count,
            "vector_candidate_count": vector_candidate_count,
            "fused_candidate_count": fused_candidate_count,
            "gated_candidate_count": gated_candidate_count,
            "relevant_candidate_count": relevant_candidate_count,
            "quality_rejected_count": quality_rejected_count,
            "context_candidate_count": context_candidate_count,
            "context_chunk_count": len(query_context.chunks) if query_context else 0,
            "citation_count": citation_count,
            "per_query": [
                {
                    **item,
                    "fused_candidate_count": fused_by_query.get(
                        _diagnostic_query_index(item), 0
                    ),
                    "gated_candidate_count": gated_by_query.get(
                        _diagnostic_query_index(item), 0
                    ),
                    "relevant_candidate_count": relevant_by_query.get(
                        _diagnostic_query_index(item), 0
                    ),
                    "context_chunk_count": context_by_query.get(
                        _diagnostic_query_index(item), 0
                    ),
                }
                for item in per_query_recall
            ],
            "gate": {
                "input_count": gate_diagnostics.input_count,
                "allowed_count": gate_diagnostics.allowed_count,
                "rejected_count": gate_diagnostics.rejected_count,
                "missing_metadata_count": gate_diagnostics.missing_metadata_count,
                "rejection_reasons": [
                    {"reason": reason, "count": count}
                    for reason, count in sorted(
                        gate_diagnostics.rejection_reasons.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                ],
            },
            "rerank": list(rerank_diagnostics),
        },
        "quality_gate": {
            "reason": quality_reason,
            "top_score": quality_top_score,
            "rejected_count": quality_rejected_count,
        },
        "selected_chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "document_version_id": chunk.document_version_id,
                "title": chunk.title,
                "heading_path": chunk.heading_path,
                "matched_query": chunk.matched_query,
                "matched_query_index": chunk.matched_query_index,
                "rank": chunk.rank,
                "score": chunk.score,
            }
            for chunk in (query_context.chunks if query_context else ())
        ],
    }


def _diagnostic_query_index(item: dict[str, object]) -> int:
    value = item.get("index")
    return value if isinstance(value, int) else 0


def _candidate_counts_by_query_index(
    candidates: tuple[RetrievalCandidate, ...],
) -> dict[int, int]:
    counts: dict[int, int] = {}
    for candidate in candidates:
        counts[candidate.matched_query_index] = counts.get(candidate.matched_query_index, 0) + 1
    return counts


def _allowed_candidate_counts_by_query_index(
    candidates: tuple[QueryAllowedCandidate, ...],
) -> dict[int, int]:
    return _candidate_counts_by_query_index(tuple(item.candidate for item in candidates))


def _context_chunk_counts_by_query_index(query_context: Any) -> dict[int, int]:
    counts: dict[int, int] = {}
    if query_context is None:
        return counts
    for chunk in getattr(query_context, "chunks", ()):
        query_index = getattr(chunk, "matched_query_index", 0)
        if not isinstance(query_index, int):
            query_index = 0
        counts[query_index] = counts.get(query_index, 0) + 1
    return counts


def _candidate_score_summaries(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    return [
        {
            "chunk_id": candidate.chunk_id,
            "document_id": candidate.document_id,
            "title": candidate.title,
            "rank": candidate.rank,
            "score": candidate.score,
            "source_score": candidate.source_score,
            "matched_query": candidate.matched_query,
            "matched_query_index": candidate.matched_query_index,
        }
        for candidate in candidates[: max(limit, 0)]
    ]
