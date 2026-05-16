from __future__ import annotations

from dataclasses import replace

import pytest
from app.modules.answer import AnswerService
from app.modules.models import ChatCompletionResult, ChatMessage, ModelClientError
from app.modules.query.errors import QueryServiceError
from app.modules.query.service import QueryService
from app.modules.retrieval import (
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


ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"
KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_ID = "44444444-4444-4444-4444-444444444444"
DOC_VERSION_ID = "55555555-5555-5555-5555-555555555555"
CHUNK_ID = "66666666-6666-6666-6666-666666666666"
VECTOR_CHUNK_ID = "77777777-7777-7777-7777-777777777777"
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
    assert result.citations[0].source_id == CHUNK_ID
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
    log_params = session.executed[-1][1]
    assert log_params["status"] == "success"
    assert log_params["candidate_count"] == 2
    assert log_params["citation_count"] == 2
    assert log_params["config_version"] == 3


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
        VECTOR_CHUNK_ID,
        CHUNK_ID,
    ]
    assert reranker.calls[0]["texts"] == ("员工年假需要提前申请", "向量召回内容")
    model_log_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO model_call_logs" in statement
    )
    assert model_log_params["caller"] == "query.rerank"
    assert model_log_params["model_type"] == "rerank"
    assert model_log_params["status"] == "success"
    assert model_log_params["input_hash"] == "rerank-input"
    assert session.executed[-1][1]["model_route_hash"] == "rerank-route"


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
    assert session.executed[-1][1]["degraded"] is True
    assert session.executed[-1][1]["degrade_reason"] == "RERANK_PROVIDER_UNAVAILABLE"


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
    assert session.executed[-1][1]["degraded"] is True


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
    assert result.degraded is True
    assert result.degrade_reason == "llm_context_empty"
    assert session.executed[-1][1]["candidate_count"] == 0


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
    assert result.answer == "员工年假需要提前申请。[source:66666666-6666-6666-6666-666666666666]"
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
    assert session.executed[-1][1]["model_route_hash"] == model_log_params["model_route_hash"]


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

    assert result.answer == ""
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
    assert session.executed[-1][1]["degraded"] is True
    assert session.executed[-1][1]["degrade_reason"] == "citation_unauthorized"


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

    assert result.answer == ""
    assert result.degraded is True
    assert result.degrade_reason == "vector_retriever_unavailable;LLM_PROVIDER_UNAVAILABLE"
    assert result.citations[0].source_id == CHUNK_ID


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
