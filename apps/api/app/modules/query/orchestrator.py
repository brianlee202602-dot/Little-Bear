"""Query workflow orchestration boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.permissions import PermissionServiceError
from app.modules.query import citation_validator, degrade_policy
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import (
    QueryAllowedCandidate,
    QueryCitation,
    QueryResult,
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
from app.modules.retrieval import RetrievalModelCall
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class _AnswerFinalization:
    answer: str
    answer_result: AnswerGenerationResult | None
    model_route_hash: str | None
    audit_events: list[_QueryAuditEvent]
    degrade_reasons: list[str]


class QueryOrchestrator:
    """Orchestrate query workflows outside the legacy core implementation."""

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
            queryable_kb_ids = (
                self._service.permission_service.require_queryable_knowledge_bases(
                    session,
                    context,
                    kb_ids=normalized_kb_ids,
                    required_scope="rag:query",
                )
            )
            query_context = None
            allowed_candidates: tuple[QueryAllowedCandidate, ...] = ()
            citations: tuple[QueryCitation, ...] = ()
            rerank_model_call: RetrievalModelCall | None = None
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
                permission_filter = self._service.permission_service.build_filter(
                    context,
                    kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    required_scope="rag:query",
                )
                keyword_candidates = self._service._keyword_search(
                    session,
                    permission_filter=permission_filter,
                    query_text=normalized_query,
                    filter_clause=filter_clause,
                    limit=normalized_top_k * 3,
                )
                vector_result = self._service.vector_retriever.search(
                    query_text=normalized_query,
                    permission_filter=permission_filter,
                    collection_names=collection_names,
                    top_k=normalized_top_k * 3,
                )
                if vector_result.degraded:
                    degrade_reasons.append(
                        vector_result.degrade_reason or "vector_retrieval_degraded"
                    )
                candidates = self._service.fusion_service.fuse(
                    keyword_candidates + vector_result.candidates,
                    limit=normalized_top_k * 3,
                )
                allowed_candidates = self._service._gate_candidates(
                    session,
                    context,
                    candidates,
                    allowed_kb_ids=queryable_kb_ids,
                    active_index_version_ids=active_index_ids,
                    limit=max(normalized_top_k, self._service.rerank_input_top_k),
                )
                rerank_result = self._service._rerank_allowed_candidates(
                    session,
                    query_text=normalized_query,
                    allowed_candidates=allowed_candidates,
                    top_k=normalized_top_k,
                )
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
                rerank_model_call = rerank_result.model_call
                if rerank_model_call is not None:
                    model_route_hash = rerank_model_call.model_route_hash
                relevant_candidates, relevance_audit_event = _apply_relevance_gate(
                    rerank_result,
                    min_score=self._service.rerank_min_score,
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
                    query_context = self._service.context_builder.build(
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
        if plan.rerank_model_call is not None:
            self._service._insert_retrieval_model_call_log(
                session,
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                enterprise_id=plan.context.enterprise_id,
                config_version=plan.config_version,
                caller="query.rerank",
                model_call=plan.rerank_model_call,
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
                if citation_validation.degrade_reason == "citation_missing":
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
