from __future__ import annotations

import json
from dataclasses import replace

import pytest
from app.modules.answer import AnswerService
from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.context.schemas import ContextChunk, QueryContext
from app.modules.models import ChatCompletionResult, ChatMessage, ModelClientError
from app.modules.permissions.schemas import CandidateGateResult, PermissionContext, PermissionFilter
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import ActiveIndexVersion, _CurrentCandidateFacts
from app.modules.query.service import QueryService
from app.modules.query_rewrite import QueryRewriteItem, QueryRewriteResult
from app.modules.retrieval import (
    CandidateQualityGate,
    RerankResult,
    RetrievalCandidate,
    RetrievalModelCall,
    VectorSearchResult,
)


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(
        self,
        *,
        one_or_none: _Row | None = None,
        all_rows: list[_Row] | None = None,
    ) -> None:
        self._one_or_none = one_or_none
        self._all_rows = all_rows or []

    def one_or_none(self) -> _Row | None:
        return self._one_or_none

    def all(self) -> list[_Row]:
        return self._all_rows


class _FakeSession:
    def __init__(self, results: list[_Result]) -> None:
        self.results = results
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        if self.results:
            return self.results.pop(0)
        return _Result()


def _query_log_params(session: _FakeSession) -> dict[str, object]:
    for statement, params in reversed(session.executed):
        if "INSERT INTO query_logs" in statement:
            return params
    raise AssertionError("query log insert was not executed")


ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"
KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_ID = "44444444-4444-4444-4444-444444444444"
DOC_VERSION_ID = "55555555-5555-5555-5555-555555555555"
CHUNK_ID = "66666666-6666-6666-6666-666666666666"
VECTOR_CHUNK_ID = "77777777-7777-7777-7777-777777777777"
NEIGHBOR_CHUNK_ID = "99999999-9999-9999-9999-999999999999"
INDEX_VERSION_ID = "88888888-8888-8888-8888-888888888888"


class _FakeVectorRetriever:
    def __init__(
        self,
        *,
        candidates: tuple[RetrievalCandidate, ...] = (),
        degraded: bool = False,
        degrade_reason: str | None = None,
    ) -> None:
        self.candidates = candidates
        self.degraded = degraded
        self.degrade_reason = degrade_reason
        self.calls: list[dict[str, object]] = []

    def search(self, *, query_text, permission_filter, collection_names, top_k):
        self.calls.append(
            {
                "query_text": query_text,
                "permission_filter": permission_filter,
                "collection_names": collection_names,
                "top_k": top_k,
            }
        )
        return VectorSearchResult(
            candidates=self.candidates,
            degraded=self.degraded,
            degrade_reason=self.degrade_reason,
        )


class _FakeChatClient:
    def __init__(
        self,
        *,
        content: str = "员工年假需要提前申请。[source:66666666-6666-6666-6666-666666666666]",
    ) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, temperature, max_tokens) -> ChatCompletionResult:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return ChatCompletionResult(
            content=self.content,
            token_usage={"prompt_tokens": 20, "completion_tokens": 10},
        )


class _CountingChatClient(_FakeChatClient):
    pass


class _FailingChatClient:
    def complete(self, *, messages, temperature, max_tokens) -> ChatCompletionResult:
        raise ModelClientError("LLM_PROVIDER_UNAVAILABLE", "provider unavailable")


class _FakeCandidateReranker:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def rerank(self, *, query_text, candidates, texts, top_k) -> RerankResult:
        self.calls.append(
            {
                "query_text": query_text,
                "candidates": candidates,
                "texts": texts,
                "top_k": top_k,
            }
        )
        ranked = tuple(
            replace(candidate, rank=rank, score=float(10 - rank))
            for rank, candidate in enumerate(reversed(candidates[:top_k]), start=1)
        )
        return RerankResult(
            candidates=ranked,
            model_call=RetrievalModelCall(
                model_type="rerank",
                model_name="bge-reranker",
                model_version=None,
                model_route_hash="rerank-route",
                status="success",
                degraded=False,
                latency_ms=12,
                input_hash="rerank-input",
                output_hash="rerank-output",
            ),
        )


class _FailingCandidateReranker:
    def rerank(self, *, query_text, candidates, texts, top_k) -> RerankResult:
        return RerankResult(
            candidates=candidates[:top_k],
            degraded=True,
            degrade_reason="RERANK_PROVIDER_UNAVAILABLE",
            model_call=RetrievalModelCall(
                model_type="rerank",
                model_name="bge-reranker",
                model_version=None,
                model_route_hash="rerank-route",
                status="failed",
                degraded=True,
                latency_ms=801,
                input_hash="rerank-input",
                output_hash=None,
                error_code="RERANK_PROVIDER_UNAVAILABLE",
            ),
        )


class _LowScoreCandidateReranker:
    def rerank(self, *, query_text, candidates, texts, top_k) -> RerankResult:
        ranked = tuple(
            replace(candidate, rank=rank, score=0.01 / rank)
            for rank, candidate in enumerate(candidates[:top_k], start=1)
        )
        return RerankResult(
            candidates=ranked,
            model_call=RetrievalModelCall(
                model_type="rerank",
                model_name="bge-reranker",
                model_version=None,
                model_route_hash="rerank-route",
                status="success",
                degraded=False,
                latency_ms=12,
                input_hash="rerank-input",
                output_hash="rerank-output",
            ),
        )


def test_create_query_returns_fused_permission_gated_citations_and_logs() -> None:
    vector_retriever = _FakeVectorRetriever(candidates=(_vector_candidate(),))
    session = _FakeSession(
        [
            _Result(one_or_none=_Row({"value_json": {"version": 3}})),
            _Result(
                one_or_none=_Row(
                    {
                        "user_id": USER_ID,
                        "enterprise_id": ENTERPRISE_ID,
                        "username": "alice",
                        "status": "active",
                    }
                )
            ),
            _Result(one_or_none=_Row({"org_version": 7, "permission_version": 42})),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "department_id": DEPARTMENT_ID,
                            "code": "sales",
                            "name": "销售部",
                            "is_primary": True,
                        }
                    )
                ]
            ),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "role_id": "role_employee",
                            "code": "employee",
                            "name": "Employee",
                            "scope_type": "enterprise",
                            "scope_id": None,
                            "scopes": ["rag:query"],
                        }
                    )
                ]
            ),
            _Result(all_rows=[_Row({"kb_id": KB_ID})]),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "index_version_id": INDEX_VERSION_ID,
                            "collection_name": "little_bear_p0",
                        }
                    )
                ]
            ),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "enterprise_id": ENTERPRISE_ID,
                            "kb_id": KB_ID,
                            "document_id": DOC_ID,
                            "document_version_id": DOC_VERSION_ID,
                            "chunk_id": CHUNK_ID,
                            "title": "员工手册",
                            "owner_department_id": DEPARTMENT_ID,
                            "visibility": "department",
                            "document_lifecycle_status": "active",
                            "document_index_status": "indexed",
                            "chunk_status": "active",
                            "visibility_state": "active",
                            "index_version_id": INDEX_VERSION_ID,
                            "indexed_permission_version": 42,
                            "page_start": 1,
                            "page_end": 2,
                            "score": 0.9,
                        }
                    )
                ]
            ),
            _Result(all_rows=_candidate_fact_rows(include_vector=True)),
            _Result(),
        ]
    )

    result = QueryService(vector_retriever=vector_retriever).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="search",
        filters={"tags": ["HR"]},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.degraded is False
    assert result.citations[0].source_id == VECTOR_CHUNK_ID
    assert result.citations[0].title == "员工手册"
    assert {citation.source_id for citation in result.citations} == {CHUNK_ID, VECTOR_CHUNK_ID}
    assert vector_retriever.calls[0]["query_text"] == "员工手册"
    assert vector_retriever.calls[0]["collection_names"] == ("little_bear_p0",)
    keyword_statement = next(
        statement
        for statement, _params in session.executed
        if "FROM keyword_index_entries" in statement
    )
    assert "d.tags && CAST(:tags AS text[])" in keyword_statement
    assert "d.title ILIKE :like_query" in keyword_statement
    assert "c.heading_path ILIKE :like_query" in keyword_statement
    assert "array_to_string(d.tags, ' ') ILIKE :like_query" in keyword_statement
    log_params = _query_log_params(session)
    assert log_params["status"] == "success"
    assert log_params["candidate_count"] == 2
    assert log_params["citation_count"] == 2
    assert log_params["config_version"] == 3
    diagnostics_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO query_retrieval_diagnostics" in statement
    )
    stage_counts = json.loads(str(diagnostics_params["stage_counts"]))
    rewrite_queries = json.loads(str(diagnostics_params["rewrite_queries"]))
    assert stage_counts["keyword_candidate_count"] == 1
    assert stage_counts["vector_candidate_count"] == 1
    assert stage_counts["fused_candidate_count"] == 2
    assert stage_counts["per_query"][0]["query"] == "员工手册"
    assert stage_counts["per_query"][0]["keyword_candidate_count"] == 1
    assert stage_counts["per_query"][0]["vector_candidate_count"] == 1
    assert stage_counts["gate"]["input_count"] == 2
    assert stage_counts["gate"]["allowed_count"] == 2
    assert stage_counts["gate"]["rejected_count"] == 0
    assert stage_counts["rerank"][0]["query"] == "员工手册"
    assert stage_counts["rerank"][0]["input_candidate_count"] == 2
    assert stage_counts["rerank"][0]["output_candidate_count"] == 2
    assert rewrite_queries[0]["query"] == "员工手册"


def test_create_query_auto_resolves_all_accessible_knowledge_bases() -> None:
    session = _session_with_one_keyword_candidate()

    result = QueryService().create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[],
        query_text="员工手册",
        mode="search",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.kb_ids == (KB_ID,)
    assert result.citations[0].source_id == CHUNK_ID
    kb_scope_statement = next(
        statement
        for statement, _params in session.executed
        if "FROM knowledge_bases kb" in statement
    )
    assert "kb.id = ANY" not in kb_scope_statement
    log_params = _query_log_params(session)
    assert log_params["kb_ids"] == [KB_ID]


def test_create_query_auto_scope_empty_returns_degraded_answer() -> None:
    session = _FakeSession(
        [
            _Result(one_or_none=_Row({"value_json": {"version": 3}})),
            _Result(
                one_or_none=_Row(
                    {
                        "user_id": USER_ID,
                        "enterprise_id": ENTERPRISE_ID,
                        "username": "alice",
                        "status": "active",
                    }
                )
            ),
            _Result(one_or_none=_Row({"org_version": 7, "permission_version": 42})),
            _Result(all_rows=[]),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "role_id": "role_employee",
                            "code": "employee",
                            "name": "Employee",
                            "scope_type": "enterprise",
                            "scope_id": None,
                            "scopes": ["rag:query"],
                        }
                    )
                ]
            ),
            _Result(all_rows=[]),
        ]
    )

    result = QueryService().create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.kb_ids == ()
    assert result.citations == ()
    assert result.degraded is True
    assert result.degrade_reason == "query_scope_empty;llm_context_empty"
    assert "当前账号没有可用于问答检索的知识库" in result.answer
    assert _query_log_params(session)["kb_ids"] == []


def test_create_query_uses_rewritten_queries_for_keyword_and_vector_retrieval() -> None:
    repository = _RewriteAwareRepository()
    vector_retriever = _RewriteAwareVectorRetriever()
    rewrite_service = _FakeQueryRewriteService()
    log_writer = _NoopQueryLogWriter()

    result = QueryService(
        permission_service=_RewritePermissionService(),
        vector_retriever=vector_retriever,
        query_rewrite_service=rewrite_service,
        repository=repository,
        log_writer=log_writer,
    ).create_query(
        _FakeSession([]),
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="采购项目审批和预算分别是什么",
        mode="search",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
        history=[{"role": "user", "content": "上一轮采购项目怎么启动"}],
    )

    assert rewrite_service.inputs[0].conversation_messages[0].content == (
        "上一轮采购项目怎么启动"
    )
    assert repository.keyword_queries == ["采购项目审批流程", "采购项目预算限制"]
    assert vector_retriever.queries == ["采购项目审批流程", "采购项目预算限制"]
    assert repository.loaded_candidates[0].matched_query == "采购项目审批流程"
    assert repository.loaded_candidates[0].matched_query_index == 0
    assert repository.loaded_candidates[0].query_weight == 1.0
    assert repository.loaded_candidates[0].source_weight == 1.0
    assert repository.loaded_candidates[1].matched_query == "采购项目预算限制"
    assert repository.loaded_candidates[1].query_weight == 0.9
    assert result.citations
    assert result.degraded is False
    assert log_writer.retrieval_model_calls[0]["caller"] == "query.rewrite"
    assert log_writer.retrieval_model_calls[0]["model_call"].model_type == "query_rewrite"


def test_create_query_preserves_rewrite_query_coverage_through_rerank() -> None:
    repository = _CoverageRepository()
    reranker = _CoverageReranker()

    result = QueryService(
        permission_service=_RewritePermissionService(),
        query_rewrite_service=_FakeQueryRewriteService(),
        repository=repository,
        candidate_reranker=reranker,
        rerank_input_top_k=1,
        log_writer=_NoopQueryLogWriter(),
    ).create_query(
        _FakeSession([]),
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="采购项目审批和预算分别是什么",
        mode="search",
        filters={},
        top_k=1,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert [call["query_text"] for call in reranker.calls] == [
        "采购项目审批流程",
        "采购项目预算限制",
    ]
    assert [call["top_k"] for call in reranker.calls] == [1, 1]
    assert [candidate.matched_query for candidate in reranker.calls[0]["candidates"]] == [
        "采购项目审批流程",
    ]
    assert [candidate.matched_query for candidate in reranker.calls[1]["candidates"]] == [
        "采购项目预算限制",
    ]
    assert [citation.source_id for citation in result.citations] == [
        "10000000-0000-0000-0000-000000000001",
        "20000000-0000-0000-0000-000000000001",
    ]


def test_create_query_keeps_per_query_quota_for_joint_question() -> None:
    reranker = _CoverageReranker()

    result = QueryService(
        permission_service=_RewritePermissionService(),
        vector_retriever=_RewriteAwareVectorRetriever(),
        query_rewrite_service=_FakeQueryRewriteService(),
        repository=_CoverageRepository(),
        candidate_reranker=reranker,
        rerank_input_top_k=20,
        log_writer=_NoopQueryLogWriter(),
    ).create_query(
        _FakeSession([]),
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="采购项目审批和预算分别是什么",
        mode="search",
        filters={},
        top_k=4,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert [call["query_text"] for call in reranker.calls] == [
        "采购项目审批流程",
        "采购项目预算限制",
    ]
    assert [call["top_k"] for call in reranker.calls] == [2, 2]
    assert [citation.source_id for citation in result.citations] == [
        "10000000-0000-0000-0000-000000000001",
        "20000000-0000-0000-0000-000000000001",
        "10000000-0000-0000-0000-000000000002",
    ]


def test_create_query_expands_neighbor_chunks_before_context_build() -> None:
    repository = _NeighborExpansionRepository()
    context_builder = _RecordingContextBuilder()

    QueryService(
        permission_service=_RewritePermissionService(),
        repository=repository,
        log_writer=_NoopQueryLogWriter(),
        context_builder=context_builder,
        context_expand_neighbors=1,
    ).create_query(
        _FakeSession([]),
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="采购制度",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert repository.neighbor_window == 1
    assert context_builder.chunk_ids == (CHUNK_ID, NEIGHBOR_CHUNK_ID)


def test_create_query_answer_citations_follow_actual_context_chunks() -> None:
    selected_chunk_id = "20000000-0000-0000-0000-000000000001"

    result = QueryService(
        permission_service=_RewritePermissionService(),
        vector_retriever=_RewriteAwareVectorRetriever(),
        query_rewrite_service=_FakeQueryRewriteService(),
        repository=_CoverageRepository(),
        context_builder=_RecordingContextBuilder(selected_chunk_ids=(selected_chunk_id,)),
        answer_service=AnswerService(
            chat_client=_FakeChatClient(
                content=f"采购预算需要按制度限制执行。[source:{selected_chunk_id}]"
            )
        ),
        log_writer=_NoopQueryLogWriter(),
    ).create_query(
        _FakeSession([]),
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="采购项目审批和预算分别是什么",
        mode="answer",
        filters={},
        top_k=1,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert [citation.source_id for citation in result.citations] == [selected_chunk_id]
    assert result.context is not None
    assert [chunk.chunk_id for chunk in result.context.chunks] == [selected_chunk_id]


def test_create_query_reranks_permission_gated_candidates_and_logs_model_call() -> None:
    vector_retriever = _FakeVectorRetriever(candidates=(_vector_candidate(),))
    reranker = _FakeCandidateReranker()
    session = _session_with_one_keyword_candidate(rerank_chunks=True)

    result = QueryService(
        vector_retriever=vector_retriever,
        candidate_reranker=reranker,
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="search",
        filters={},
        top_k=2,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.degraded is False
    assert [citation.source_id for citation in result.citations] == [
        CHUNK_ID,
        VECTOR_CHUNK_ID,
    ]
    assert reranker.calls[0]["texts"] == ("向量召回内容", "员工年假需要提前申请")
    model_log_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO model_call_logs" in statement
    )
    assert model_log_params["caller"] == "query.rerank"
    assert model_log_params["model_type"] == "rerank"
    assert model_log_params["status"] == "success"
    assert model_log_params["input_hash"] == "rerank-input"
    assert _query_log_params(session)["model_route_hash"] == "rerank-route"


def test_create_query_degrades_when_reranker_fails() -> None:
    session = _session_with_one_keyword_candidate(rerank_chunks=True)

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        candidate_reranker=_FailingCandidateReranker(),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="search",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.degraded is True
    assert result.degrade_reason == "RERANK_PROVIDER_UNAVAILABLE"
    assert result.citations[0].source_id == CHUNK_ID
    model_log_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO model_call_logs" in statement
    )
    assert model_log_params["caller"] == "query.rerank"
    assert model_log_params["status"] == "failed"
    assert model_log_params["error_code"] == "RERANK_PROVIDER_UNAVAILABLE"
    audit_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO audit_logs" in statement
    )
    assert audit_params["event_name"] == "query.rerank_degraded"
    assert audit_params["error_code"] == "RERANK_PROVIDER_UNAVAILABLE"
    query_log_params = _query_log_params(session)
    assert query_log_params["degraded"] is True
    assert query_log_params["degrade_reason"] == "RERANK_PROVIDER_UNAVAILABLE"


def test_create_query_filters_low_relevance_rerank_candidates_before_llm() -> None:
    session = _session_with_one_keyword_candidate(rerank_chunks=True)

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        candidate_reranker=_LowScoreCandidateReranker(),
        rerank_min_score=0.05,
        answer_service=AnswerService(chat_client=_FakeChatClient()),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="怎么开始采购项目",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.citations == ()
    assert result.context is not None
    assert result.context.chunks == ()
    assert "相关性过低" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "retrieval_relevance_too_low;llm_context_empty"
    model_log_params = [
        params
        for statement, params in session.executed
        if "INSERT INTO model_call_logs" in statement
    ]
    assert [params["caller"] for params in model_log_params] == ["query.rerank"]
    audit_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO audit_logs" in statement
    )
    assert audit_params["event_name"] == "query.relevance_gate_failed"
    assert audit_params["error_code"] == "retrieval_relevance_too_low"
    query_log_params = _query_log_params(session)
    assert query_log_params["degrade_reason"] == (
        "retrieval_relevance_too_low;llm_context_empty"
    )
    assert query_log_params["citation_count"] == 0


def test_create_query_quality_gate_blocks_low_source_score_without_rerank() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)
    chat_client = _CountingChatClient()

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        candidate_quality_gate=CandidateQualityGate(
            min_fusion_score=0.01,
            min_source_score=0.95,
        ),
        answer_service=AnswerService(chat_client=chat_client),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="完全无关的问题",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert chat_client.calls == []
    assert result.citations == ()
    assert result.context is not None
    assert result.context.chunks == ()
    assert "检索到的片段与问题相关性过低" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "retrieval_quality_too_low;llm_context_empty"
    audit_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO audit_logs" in statement
    )
    assert audit_params["event_name"] == "query.quality_gate_failed"
    assert audit_params["error_code"] == "retrieval_quality_too_low"
    query_log_params = _query_log_params(session)
    assert query_log_params["degrade_reason"] == (
        "retrieval_quality_too_low;llm_context_empty"
    )
    assert query_log_params["citation_count"] == 0


def test_create_query_degrades_to_keyword_when_vector_retriever_unavailable() -> None:
    session = _session_with_one_keyword_candidate()

    result = QueryService().create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="search",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.degraded is True
    assert result.degrade_reason == "vector_retriever_unavailable"
    assert result.citations[0].source_id == CHUNK_ID
    assert _query_log_params(session)["degraded"] is True


def test_create_query_without_active_index_returns_empty_keyword_only_result() -> None:
    session = _FakeSession(
        [
            _Result(one_or_none=_Row({"value_json": {"version": 3}})),
            _Result(
                one_or_none=_Row(
                    {
                        "user_id": USER_ID,
                        "enterprise_id": ENTERPRISE_ID,
                        "username": "alice",
                        "status": "active",
                    }
                )
            ),
            _Result(one_or_none=_Row({"org_version": 7, "permission_version": 42})),
            _Result(all_rows=[]),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "role_id": "role",
                            "code": "employee",
                            "name": "Employee",
                            "scope_type": "enterprise",
                            "scope_id": None,
                            "scopes": ["rag:query"],
                        }
                    )
                ]
            ),
            _Result(all_rows=[_Row({"kb_id": KB_ID})]),
            _Result(all_rows=[]),
            _Result(),
        ]
    )

    result = QueryService().create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="找不到",
        mode="answer",
        filters={},
        top_k=8,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.citations == ()
    assert "没有在当前账号可访问" in result.answer
    assert "没有可用于生成答案的上下文" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "llm_context_empty"
    assert _query_log_params(session)["candidate_count"] == 0


def test_create_query_calls_llm_for_answer_mode() -> None:
    chat_client = _FakeChatClient()
    session = _session_with_one_keyword_candidate(context_chunks=True)

    result = QueryService(
        answer_service=AnswerService(
            chat_client=chat_client,
            temperature=0.2,
            max_tokens=128,
        )
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert result.degraded is True
    assert result.degrade_reason == "vector_retriever_unavailable"
    assert result.answer == "员工年假需要提前申请。"
    assert result.citations[0].source_id == CHUNK_ID
    assert result.context is not None
    assert result.context.chunks[0].content == "员工年假需要提前申请"
    assert result.context.chunks[0].heading_path == "制度/请假"
    assert chat_client.calls[0]["temperature"] == 0.2
    assert chat_client.calls[0]["max_tokens"] == 128
    messages = chat_client.calls[0]["messages"]
    assert isinstance(messages[0], ChatMessage)
    assert "只能基于用户可访问的资料回答" in messages[0].content
    assert "[source:66666666-6666-6666-6666-666666666666]" in messages[1].content
    model_log_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO model_call_logs" in statement
    )
    assert model_log_params["status"] == "success"
    assert model_log_params["model_type"] == "llm"
    assert model_log_params["token_usage_json"] is not None
    assert _query_log_params(session)["model_route_hash"] == model_log_params["model_route_hash"]


def test_create_query_degrades_and_audits_unauthorized_llm_citation() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        answer_service=AnswerService(
            chat_client=_FakeChatClient(
                content="员工年假需要提前申请。[source:00000000-0000-0000-0000-000000000000]"
            )
        ),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert "未授权或未命中的资料" in result.answer
    assert "系统已拦截原回答" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "citation_unauthorized"
    audit_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO audit_logs" in statement
    )
    assert audit_params["event_name"] == "query.citation_validation_failed"
    assert audit_params["risk_level"] == "high"
    assert audit_params["error_code"] == "citation_unauthorized"
    assert "00000000-0000-0000-0000-000000000000" in audit_params["summary_json"]
    query_log_params = _query_log_params(session)
    assert query_log_params["degraded"] is True
    assert query_log_params["degrade_reason"] == "citation_unauthorized"


def test_create_query_repairs_invalid_llm_citation_format_without_permission_alarm() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        answer_service=AnswerService(
            chat_client=_FakeChatClient(
                content="根据资料未找到明确规定。[source:无相关资料]"
            )
        ),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert "根据资料未找到明确规定。" in result.answer
    assert "不存在的引用占位符" not in result.answer
    assert "source:无相关资料" not in result.answer
    assert result.degraded is False
    assert result.degrade_reason is None
    audit_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO audit_logs" in statement
    )
    assert audit_params["event_name"] == "query.citation_validation_failed"
    assert audit_params["risk_level"] == "medium"
    assert audit_params["error_code"] == "citation_auto_attached"
    assert "original_degrade_reason" in audit_params["summary_json"]
    assert "citation_invalid_format" in audit_params["summary_json"]
    assert "无相关资料" in audit_params["summary_json"]
    query_log_params = _query_log_params(session)
    assert query_log_params["degraded"] is False
    assert query_log_params["degrade_reason"] is None


def test_create_query_still_degrades_invalid_citation_when_answer_cannot_be_repaired() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        answer_service=AnswerService(
            chat_client=_FakeChatClient(content="[source:无相关资料]")
        ),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert "不存在的引用占位符" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "citation_invalid_format"


def test_create_query_auto_attaches_sources_when_llm_omits_citations() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)

    result = QueryService(
        vector_retriever=_FakeVectorRetriever(),
        answer_service=AnswerService(
            chat_client=_FakeChatClient(content="员工年假需要提前在系统中提交申请。")
        ),
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert "员工年假需要提前在系统中提交申请。" in result.answer
    assert f"[source:{CHUNK_ID}]" not in result.answer
    assert "参考来源" not in result.answer
    assert result.degraded is False
    assert result.degrade_reason is None
    audit_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO audit_logs" in statement
    )
    assert audit_params["event_name"] == "query.citation_validation_failed"
    assert audit_params["risk_level"] == "medium"
    assert audit_params["error_code"] == "citation_auto_attached"
    assert "original_degrade_reason" in audit_params["summary_json"]
    query_log_params = _query_log_params(session)
    assert query_log_params["degraded"] is False
    assert query_log_params["degrade_reason"] is None


def test_create_query_degrades_when_llm_provider_fails() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)

    result = QueryService(
        answer_service=AnswerService(chat_client=_FailingChatClient())
    ).create_query(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    assert "回答生成模型不可用" in result.answer
    assert "系统找到了 1 条当前账号可访问的引用资料" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "vector_retriever_unavailable;LLM_PROVIDER_UNAVAILABLE"
    assert result.citations[0].source_id == CHUNK_ID


def test_finalize_query_stream_returns_degraded_answer_when_llm_provider_fails() -> None:
    session = _session_with_one_keyword_candidate(context_chunks=True)
    service = QueryService()
    plan = service.create_query_stream_plan(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        kb_ids=[KB_ID],
        query_text="员工手册",
        mode="answer",
        filters={},
        top_k=3,
        include_sources=True,
        request_id="req_query",
        trace_id="trace_query",
    )

    result = service.finalize_query_stream(
        session,
        plan=plan,
        answer_result=AnswerGenerationResult(
            answer="",
            degraded=True,
            degrade_reason="LLM_PROVIDER_UNAVAILABLE",
            model_call_attempted=True,
            model_name="qwen",
            model_route_hash="llm-route",
        ),
    )

    assert "回答生成模型不可用" in result.answer
    assert "系统找到了 1 条当前账号可访问的引用资料" in result.answer
    assert result.degraded is True
    assert result.degrade_reason == "vector_retriever_unavailable;LLM_PROVIDER_UNAVAILABLE"


def test_create_query_rejects_unsupported_filter() -> None:
    with pytest.raises(QueryServiceError) as exc_info:
        QueryService().create_query(
            _FakeSession([]),
            user_id=USER_ID,
            enterprise_id=ENTERPRISE_ID,
            kb_ids=[KB_ID],
            query_text="员工手册",
            mode="search",
            filters={"custom_acl": "x"},
            top_k=8,
            include_sources=True,
            request_id="req_query",
            trace_id="trace_query",
        )

    assert exc_info.value.error_code == "QUERY_FILTER_UNSUPPORTED"


class _FakeQueryRewriteService:
    max_queries = 2

    def __init__(self) -> None:
        self.inputs = []

    def rewrite(self, input_data):
        self.inputs.append(input_data)
        return QueryRewriteResult(
            original_query=input_data.original_query,
            rewritten_queries=(
                QueryRewriteItem(query="采购项目审批流程", intent="approval", weight=1.0),
                QueryRewriteItem(query="采购项目预算限制", intent="budget", weight=0.9),
            ),
            model_call=RetrievalModelCall(
                model_type="query_rewrite",
                model_name="qwen-rewrite",
                model_version=None,
                model_route_hash="rewrite-route",
                status="success",
                degraded=False,
                latency_ms=7,
                prompt_hash="rewrite-prompt",
                input_hash="rewrite-input",
                output_hash="rewrite-output",
            ),
        )


class _RewritePermissionService:
    def build_context(self, _session, *, user_id, enterprise_id, request_id):
        return PermissionContext(
            enterprise_id=enterprise_id,
            user_id=user_id,
            username="alice",
            status="active",
            department_ids=(DEPARTMENT_ID,),
            departments=(),
            roles=(),
            scopes=("rag:query",),
            permission_version=42,
            org_version=7,
            permission_filter_hash="permission_hash",
            request_id=request_id,
        )

    def require_queryable_knowledge_bases(self, _session, _context, *, kb_ids, required_scope):
        assert required_scope == "rag:query"
        return tuple(kb_ids)

    def build_filter(
        self,
        context,
        *,
        kb_ids,
        active_index_version_ids,
        required_scope,
    ):
        assert required_scope == "rag:query"
        return PermissionFilter(
            enterprise_id=context.enterprise_id,
            department_ids=context.department_ids,
            kb_ids=tuple(kb_ids),
            active_index_version_ids=tuple(active_index_version_ids),
            permission_version=context.permission_version,
            permission_filter_hash=context.permission_filter_hash,
            qdrant_filter={"must": []},
            keyword_where_sql="TRUE",
            metadata_where_sql="TRUE",
            params={},
        )

    def gate_candidate(
        self,
        _context,
        _candidate,
        *,
        allowed_kb_ids=None,
        active_index_version_ids=None,
    ):
        return CandidateGateResult(allowed=True, reason="allowed")


class _RewriteAwareRepository:
    def __init__(self) -> None:
        self.keyword_queries: list[str] = []
        self.loaded_candidates: tuple[RetrievalCandidate, ...] = ()

    def load_active_config_version(self, _session) -> int:
        return 3

    def load_active_index_versions(self, _session, *, enterprise_id, kb_ids):
        assert enterprise_id == ENTERPRISE_ID
        assert kb_ids == (KB_ID,)
        return (ActiveIndexVersion(id=INDEX_VERSION_ID, collection_name="little_bear_p0"),)

    def keyword_search(
        self,
        _session,
        *,
        permission_filter,
        query_text,
        filter_clause,
        limit,
    ):
        self.keyword_queries.append(query_text)
        return (
            _rewrite_candidate(
                chunk_id=f"10000000-0000-0000-0000-00000000000{len(self.keyword_queries)}"
            ),
        )

    def load_current_candidate_facts(self, _session, candidates):
        self.loaded_candidates = candidates
        return {
            (candidate.chunk_id, candidate.index_version_id): _CurrentCandidateFacts(
                candidate=candidate,
                access_blocked=False,
            )
            for candidate in candidates
        }


class _RewriteAwareVectorRetriever:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, *, query_text, permission_filter, collection_names, top_k):
        self.queries.append(query_text)
        return VectorSearchResult(candidates=())


class _CoverageRepository:
    def load_active_config_version(self, _session) -> int:
        return 3

    def load_active_index_versions(self, _session, *, enterprise_id, kb_ids):
        assert enterprise_id == ENTERPRISE_ID
        assert kb_ids == (KB_ID,)
        return (ActiveIndexVersion(id=INDEX_VERSION_ID, collection_name="little_bear_p0"),)

    def keyword_search(
        self,
        _session,
        *,
        permission_filter,
        query_text,
        filter_clause,
        limit,
    ):
        if query_text == "采购项目审批流程":
            return tuple(
                replace(
                    _rewrite_candidate(
                        chunk_id=f"10000000-0000-0000-0000-00000000000{index}"
                    ),
                    title="采购审批",
                    rank=index,
                    score=1.0 - index / 100,
                )
                for index in range(1, 6)
            )
        if query_text == "采购项目预算限制":
            return (
                replace(
                    _rewrite_candidate(
                        chunk_id="20000000-0000-0000-0000-000000000001"
                    ),
                    title="采购预算",
                    rank=1,
                    score=0.8,
                ),
            )
        return ()

    def load_current_candidate_facts(self, _session, candidates):
        return {
            (candidate.chunk_id, candidate.index_version_id): _CurrentCandidateFacts(
                candidate=candidate,
                access_blocked=False,
            )
            for candidate in candidates
        }

    def load_rerank_texts(self, _session, *, chunk_ids):
        return {chunk_id: f"text {chunk_id}" for chunk_id in chunk_ids}


class _CoverageReranker:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def rerank(self, *, query_text, candidates, texts, top_k) -> RerankResult:
        self.calls.append(
            {
                "query_text": query_text,
                "candidates": candidates,
                "texts": texts,
                "top_k": top_k,
            }
        )
        return RerankResult(
            candidates=tuple(
                replace(candidate, rank=rank, score=1.0 / rank)
                for rank, candidate in enumerate(candidates[:top_k], start=1)
            ),
            model_call=RetrievalModelCall(
                model_type="rerank",
                model_name="bge-reranker",
                model_version=None,
                model_route_hash="rerank-route",
                status="success",
                degraded=False,
                latency_ms=12,
                input_hash="coverage-rerank-input",
                output_hash="coverage-rerank-output",
            ),
        )


class _NeighborExpansionRepository:
    def __init__(self) -> None:
        self.neighbor_window: int | None = None

    def load_active_config_version(self, _session) -> int:
        return 3

    def load_active_index_versions(self, _session, *, enterprise_id, kb_ids):
        assert enterprise_id == ENTERPRISE_ID
        assert kb_ids == (KB_ID,)
        return (ActiveIndexVersion(id=INDEX_VERSION_ID, collection_name="little_bear_p0"),)

    def keyword_search(
        self,
        _session,
        *,
        permission_filter,
        query_text,
        filter_clause,
        limit,
    ):
        return (_rewrite_candidate(chunk_id=CHUNK_ID),)

    def load_current_candidate_facts(self, _session, candidates):
        return {
            (candidate.chunk_id, candidate.index_version_id): _CurrentCandidateFacts(
                candidate=candidate,
                access_blocked=False,
            )
            for candidate in candidates
        }

    def load_neighbor_candidates(self, _session, *, candidates, window):
        self.neighbor_window = window
        assert [candidate.chunk_id for candidate in candidates] == [CHUNK_ID]
        return (
            replace(
                _rewrite_candidate(chunk_id=NEIGHBOR_CHUNK_ID),
                source="context_expansion",
                rank=2,
                score=0.5,
                source_score=0.5,
                matched_query=candidates[0].matched_query,
            ),
        )


class _RecordingContextBuilder:
    max_chunks = 6

    def __init__(self, *, selected_chunk_ids: tuple[str, ...] | None = None) -> None:
        self.chunk_ids: tuple[str, ...] = ()
        self.selected_chunk_ids = selected_chunk_ids

    def build(self, _session, *, query_text, allowed_candidates):
        self.chunk_ids = tuple(item.candidate.chunk_id for item in allowed_candidates)
        if self.selected_chunk_ids is not None:
            allowed_candidates = tuple(
                item
                for item in allowed_candidates
                if item.candidate.chunk_id in set(self.selected_chunk_ids)
            )
        return QueryContext(
            query_text=query_text,
            chunks=tuple(
                ContextChunk(
                    chunk_id=item.candidate.chunk_id,
                    document_id=item.candidate.document_id,
                    document_version_id=item.candidate.document_version_id,
                    title=item.candidate.title,
                    content=f"context {item.candidate.chunk_id}",
                    heading_path=None,
                    page_start=item.candidate.page_start,
                    page_end=item.candidate.page_end,
                    score=item.candidate.score,
                    rank=item.candidate.rank,
                    source_offsets=None,
                    matched_query=item.candidate.matched_query,
                    matched_query_index=item.candidate.matched_query_index,
                )
                for item in allowed_candidates
            ),
            estimated_tokens=10,
            truncated=False,
        )


class _NoopQueryLogWriter:
    def __init__(self) -> None:
        self.retrieval_model_calls: list[dict[str, object]] = []

    def insert_query_log(self, *_args, **_kwargs) -> None:
        return None

    def insert_denied_query_log(self, *_args, **_kwargs) -> None:
        return None

    def insert_model_call_log(self, *_args, **_kwargs) -> None:
        return None

    def insert_retrieval_model_call_log(self, *_args, **kwargs) -> None:
        self.retrieval_model_calls.append(kwargs)

    def insert_query_audit_log(self, *_args, **_kwargs) -> None:
        return None


def _rewrite_candidate(*, chunk_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        source="keyword",
        enterprise_id=ENTERPRISE_ID,
        kb_id=KB_ID,
        document_id=DOC_ID,
        document_version_id=DOC_VERSION_ID,
        chunk_id=chunk_id,
        title="采购制度",
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
        rank=1,
        score=0.9,
    )


def _session_with_one_keyword_candidate(
    *,
    context_chunks: bool = False,
    rerank_chunks: bool = False,
) -> _FakeSession:
    results = [
        _Result(one_or_none=_Row({"value_json": {"version": 3}})),
        _Result(
            one_or_none=_Row(
                {
                    "user_id": USER_ID,
                    "enterprise_id": ENTERPRISE_ID,
                    "username": "alice",
                    "status": "active",
                }
            )
        ),
        _Result(one_or_none=_Row({"org_version": 7, "permission_version": 42})),
        _Result(
            all_rows=[
                _Row(
                    {
                        "department_id": DEPARTMENT_ID,
                        "code": "sales",
                        "name": "销售部",
                        "is_primary": True,
                    }
                )
            ]
        ),
        _Result(
            all_rows=[
                _Row(
                    {
                        "role_id": "role_employee",
                        "code": "employee",
                        "name": "Employee",
                        "scope_type": "enterprise",
                        "scope_id": None,
                        "scopes": ["rag:query"],
                    }
                )
            ]
        ),
        _Result(all_rows=[_Row({"kb_id": KB_ID})]),
        _Result(
            all_rows=[
                _Row(
                    {
                        "index_version_id": INDEX_VERSION_ID,
                        "collection_name": "little_bear_p0",
                    }
                )
            ]
        ),
        _Result(
            all_rows=[
                _Row(
                    {
                        "enterprise_id": ENTERPRISE_ID,
                        "kb_id": KB_ID,
                        "document_id": DOC_ID,
                        "document_version_id": DOC_VERSION_ID,
                        "chunk_id": CHUNK_ID,
                        "title": "员工手册",
                        "owner_department_id": DEPARTMENT_ID,
                        "visibility": "department",
                        "document_lifecycle_status": "active",
                        "document_index_status": "indexed",
                        "chunk_status": "active",
                        "visibility_state": "active",
                        "index_version_id": INDEX_VERSION_ID,
                        "indexed_permission_version": 42,
                        "page_start": 1,
                        "page_end": 2,
                        "score": 0.9,
                    }
                )
            ]
        ),
        _Result(all_rows=_candidate_fact_rows(include_vector=True)),
    ]
    if rerank_chunks:
        results.append(
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": CHUNK_ID,
                            "text_preview": "员工年假需要提前申请",
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": VECTOR_CHUNK_ID,
                            "text_preview": "向量召回内容",
                        }
                    ),
                ]
            )
        )
    if context_chunks:
        results.append(
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": CHUNK_ID,
                            "document_id": DOC_ID,
                            "document_version_id": DOC_VERSION_ID,
                            "title": "员工手册",
                            "text_preview": "员工年假需要提前申请",
                            "heading_path": "制度/请假",
                            "page_start": 1,
                            "page_end": 2,
                            "source_offsets": {"item_index": 0, "chunk_ordinal": 1},
                        }
                    )
                ]
            ),
        )
    results.append(_Result())
    return _FakeSession(results)


def _candidate_fact_rows(*, include_vector: bool = False) -> list[_Row]:
    rows = [_candidate_fact_row(chunk_id=CHUNK_ID, page_start=1, page_end=2)]
    if include_vector:
        rows.append(_candidate_fact_row(chunk_id=VECTOR_CHUNK_ID, page_start=3, page_end=3))
    return rows


def _candidate_fact_row(
    *,
    chunk_id: str,
    page_start: int,
    page_end: int,
    access_blocked: bool = False,
) -> _Row:
    return _Row(
        {
            "enterprise_id": ENTERPRISE_ID,
            "kb_id": KB_ID,
            "document_id": DOC_ID,
            "document_version_id": DOC_VERSION_ID,
            "chunk_id": chunk_id,
            "title": "员工手册",
            "owner_department_id": DEPARTMENT_ID,
            "visibility": "department",
            "document_lifecycle_status": "active",
            "document_index_status": "indexed",
            "chunk_status": "active",
            "visibility_state": "active",
            "index_version_id": INDEX_VERSION_ID,
            "indexed_permission_version": 15,
            "page_start": page_start,
            "page_end": page_end,
            "access_blocked": access_blocked,
        }
    )


def _vector_candidate() -> RetrievalCandidate:
    return RetrievalCandidate(
        source="vector",
        enterprise_id=ENTERPRISE_ID,
        kb_id=KB_ID,
        document_id=DOC_ID,
        document_version_id=DOC_VERSION_ID,
        chunk_id=VECTOR_CHUNK_ID,
        title="员工手册向量片段",
        owner_department_id=DEPARTMENT_ID,
        visibility="department",
        document_lifecycle_status="active",
        document_index_status="indexed",
        chunk_status="active",
        visibility_state="active",
        index_version_id=INDEX_VERSION_ID,
        indexed_permission_version=42,
        page_start=3,
        page_end=3,
        rank=1,
        score=0.82,
    )
