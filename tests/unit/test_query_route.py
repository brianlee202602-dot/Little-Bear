from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser
from app.modules.context.schemas import ContextChunk, QueryContext
from app.modules.permissions.schemas import PermissionContext
from app.modules.query.conversations import (
    QueryConversationDetail,
    QueryConversationList,
    QueryConversationSummary,
    QueryConversationWriteContext,
    QueryMessage,
)
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import QueryCitation, QueryResult
from app.modules.query.service import QueryStreamPlan
from app.modules.setup.service import SetupState, SetupStatus
from fastapi.testclient import TestClient

AUTH_TARGET = "app.api.dependencies.auth.AuthService.authenticate_access_token"


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeQueryService:
    def __init__(self, handler) -> None:
        self.handler = handler

    def create_query(self, session, **kwargs):
        return self.handler(self, session, **kwargs)


class _FakeAnswerRunner:
    def __init__(self) -> None:
        self.result: AnswerGenerationResult | None = None

    def stream_tokens(self):
        yield "员工年假"
        yield "需要提前申请。"
        self.result = AnswerGenerationResult(
            answer="员工年假需要提前申请。[source:chunk_1]",
            degraded=False,
            degrade_reason=None,
        )


class _FakeStreamingAnswerService:
    def stream(self, *, query_context):
        assert query_context is not None
        return _FakeAnswerRunner()


class _FakeStreamingQueryService:
    def __init__(self, captured: dict[str, object]) -> None:
        self.answer_service = _FakeStreamingAnswerService()
        self.captured = captured

    def create_query_stream_plan(self, _session, **kwargs):
        self.captured.update(kwargs)
        return QueryStreamPlan(
            request_id=kwargs["request_id"],
            trace_id=kwargs["trace_id"],
            mode=kwargs["mode"],
            started_at=1.0,
            normalized_query=kwargs["query_text"],
            normalized_kb_ids=tuple(kwargs["kb_ids"]),
            config_version=1,
            context=PermissionContext(
                enterprise_id=kwargs["enterprise_id"],
                user_id=kwargs["user_id"],
                username="alice",
                status="active",
                department_ids=(),
                departments=(),
                roles=(),
                scopes=("rag:query",),
                permission_version=1,
                org_version=1,
                permission_filter_hash="permission_hash",
                request_id=kwargs["request_id"],
            ),
            query_context=_query_context(),
            allowed_candidates=(),
            citations=(
                QueryCitation(
                    source_id="chunk_1",
                    doc_id="44444444-4444-4444-4444-444444444444",
                    document_version_id="55555555-5555-5555-5555-555555555555",
                    title="员工手册",
                    page_start=1,
                    page_end=2,
                    score=0.9,
                ),
            ),
            confidence="low",
            pre_degrade_reasons=(),
            audit_events=(),
            rerank_model_call=None,
            model_route_hash=None,
            candidate_count=1,
            permission_filter_hash="permission_hash",
            permission_version=1,
            index_version_hash="index_hash",
        )

    def finalize_query_stream(self, _session, *, plan, answer_result):
        self.captured["final_answer"] = answer_result.answer
        return QueryResult(
            request_id=plan.request_id,
            answer="员工年假需要提前申请。",
            citations=plan.citations,
            confidence=plan.confidence,
            degraded=answer_result.degraded,
            degrade_reason=answer_result.degrade_reason,
            trace_id=plan.trace_id,
            context=plan.query_context,
        )


class _FakeConversationService:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured
        self.summary = QueryConversationSummary(
            id="22222222-2222-2222-2222-222222222222",
            title="员工手册",
            status="active",
            kb_ids=("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",),
            last_message_at=None,
            created_at=None,
            updated_at=None,
        )

    def list_conversations(self, _session, **kwargs):
        self.captured["conversation_list_kwargs"] = kwargs
        return QueryConversationList(items=(self.summary,), total=1)

    def create_conversation(self, _session, **kwargs):
        self.captured["conversation_create_kwargs"] = kwargs
        return self.summary

    def get_conversation(self, _session, **kwargs):
        self.captured["conversation_get_kwargs"] = kwargs
        return QueryConversationDetail(
            conversation=self.summary,
            messages=(
                QueryMessage(
                    id="77777777-7777-7777-7777-777777777777",
                    conversation_id=self.summary.id,
                    role="user",
                    content="员工手册",
                    status="done",
                    citations=(),
                    confidence=None,
                    degraded=False,
                    degrade_reason=None,
                    request_id="req_query",
                    trace_id="trace_query",
                    created_at=None,
                    updated_at=None,
                ),
            ),
            message_page=kwargs.get("page", 1),
            message_page_size=kwargs.get("page_size", 50),
            message_total=1,
        )

    def delete_conversation(self, _session, **kwargs):
        self.captured["conversation_delete_kwargs"] = kwargs

    def prepare_query_messages(self, _session, **kwargs):
        self.captured["conversation_prepare_kwargs"] = kwargs
        return QueryConversationWriteContext(
            conversation_id=self.summary.id,
            user_message_id="88888888-8888-8888-8888-888888888888",
            assistant_message_id="99999999-9999-9999-9999-999999999999",
        )

    def complete_assistant_message(self, _session, **kwargs):
        self.captured["conversation_complete_kwargs"] = kwargs

    def fail_assistant_message(self, _session, **kwargs):
        self.captured["conversation_fail_kwargs"] = kwargs


def _create_test_app():
    return create_app(run_startup_checks=False)


def _open_business_api(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.middleware.setup_guard.SetupService.load_state",
        lambda _self: SetupState(
            initialized=True,
            setup_status=SetupStatus.INITIALIZED,
            active_config_version=1,
            active_config_available=True,
            service_bootstrap_ready=True,
        ),
    )


def _auth_context() -> AuthContext:
    user = AuthUser(
        id="11111111-1111-1111-1111-111111111111",
        enterprise_id="33333333-3333-3333-3333-333333333333",
        username="alice",
        display_name="Alice",
        status="active",
        roles=(
            AuthRole(
                id="role_1",
                code="employee",
                name="Employee",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=("rag:query",),
            ),
        ),
        scopes=("rag:query",),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id, "iat": int(datetime.now(UTC).timestamp())},
    )


def _patch_conversation_service(monkeypatch, captured: dict[str, object]) -> None:
    service = _FakeConversationService(captured)
    monkeypatch.setattr(
        "app.api.routes.query_conversations.QueryConversationService",
        lambda: service,
    )
    monkeypatch.setattr("app.api.routes.query_execute.QueryConversationService", lambda: service)
    monkeypatch.setattr("app.api.routes.query_stream.QueryConversationService", lambda: service)


def _patch_query_session_scope(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.query_conversations.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.query_execute.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.query_stream.session_scope", lambda: _FakeSession())


def test_create_query_route_returns_query_response(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    _patch_query_session_scope(monkeypatch)
    captured: dict[str, object] = {}

    def _authenticate(*_args, **kwargs):
        captured.update(kwargs)
        return _auth_context()

    def _create_query(_self, _session, **kwargs):
        captured.update(kwargs)
        return QueryResult(
            request_id=kwargs["request_id"],
            answer="",
            citations=(
                QueryCitation(
                    source_id="66666666-6666-6666-6666-666666666666",
                    doc_id="44444444-4444-4444-4444-444444444444",
                    document_version_id="55555555-5555-5555-5555-555555555555",
                    title="员工手册",
                    page_start=1,
                    page_end=2,
                    score=0.9,
                ),
            ),
            confidence="low",
            degraded=True,
            degrade_reason="llm_runtime_config_unavailable",
            trace_id=kwargs["trace_id"],
        )

    monkeypatch.setattr(
        AUTH_TARGET,
        _authenticate,
    )
    _patch_conversation_service(monkeypatch, captured)
    monkeypatch.setattr(
        "app.api.routes.query_execute.build_query_service",
        lambda _session: _FakeQueryService(_create_query),
    )

    response = TestClient(app).post(
        "/internal/v1/queries",
        headers={"Authorization": "Bearer token", "x-request-id": "req_query"},
        json={
            "kb_ids": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
            "query": "员工手册",
            "history": [
                {"role": "user", "content": "上一轮问题"},
                {"role": "assistant", "content": "上一轮回答"},
            ],
            "mode": "answer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["debug_id"].startswith("dbg_")
    assert "request_id" not in body
    assert "trace_id" not in body
    assert body["conversation_id"] == "22222222-2222-2222-2222-222222222222"
    assert body["message_id"] == "99999999-9999-9999-9999-999999999999"
    assert body["citations"][0]["title"] == "员工手册"
    assert body["degraded"] is True
    assert captured["required_scope"] == "rag:query"
    assert captured["query_text"] == "员工手册"
    assert captured["conversation_prepare_kwargs"]["query_text"] == "员工手册"
    assert captured["conversation_complete_kwargs"]["message_id"] == (
        "99999999-9999-9999-9999-999999999999"
    )


def test_create_query_stream_route_returns_sse_events(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    _patch_query_session_scope(monkeypatch)
    captured: dict[str, object] = {}

    def _authenticate(*_args, **kwargs):
        captured.update(kwargs)
        return _auth_context()

    def _create_query(_self, _session, **kwargs):
        captured.update(kwargs)
        return QueryResult(
            request_id=kwargs["request_id"],
            answer="员工年假需要提前申请。",
            citations=(
                QueryCitation(
                    source_id="66666666-6666-6666-6666-666666666666",
                    doc_id="44444444-4444-4444-4444-444444444444",
                    document_version_id="55555555-5555-5555-5555-555555555555",
                    title="员工手册",
                    page_start=1,
                    page_end=2,
                    score=0.9,
                ),
            ),
            confidence="low",
            degraded=False,
            degrade_reason=None,
            trace_id=kwargs["trace_id"],
        )

    monkeypatch.setattr(
        AUTH_TARGET,
        _authenticate,
    )
    _patch_conversation_service(monkeypatch, captured)
    monkeypatch.setattr(
        "app.api.routes.query_stream.build_query_service",
        lambda _session: _FakeQueryService(_create_query),
    )

    response = TestClient(app).post(
        "/internal/v1/query-streams",
        headers={"Authorization": "Bearer token", "x-request-id": "req_stream"},
        json={
            "kb_ids": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
            "query": "员工手册",
            "mode": "answer",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: metadata" in response.text
    assert 'data: {"delta":"员工年假需要提前申请。"}' in response.text
    assert "event: citation" in response.text
    assert "event: done" in response.text
    assert '"debug_id":"dbg_' in response.text
    assert '"request_id"' not in response.text
    assert '"trace_id"' not in response.text
    assert '"conversation_id":"22222222-2222-2222-2222-222222222222"' in response.text
    assert '"message_id":"99999999-9999-9999-9999-999999999999"' in response.text
    assert "员工手册" in response.text
    assert captured["required_scope"] == "rag:query"


def test_create_query_stream_route_uses_provider_token_stream(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    _patch_query_session_scope(monkeypatch)
    captured: dict[str, object] = {}

    def _authenticate(*_args, **kwargs):
        captured.update(kwargs)
        return _auth_context()

    monkeypatch.setattr(
        AUTH_TARGET,
        _authenticate,
    )
    _patch_conversation_service(monkeypatch, captured)
    monkeypatch.setattr(
        "app.api.routes.query_stream.build_query_service",
        lambda _session: _FakeStreamingQueryService(captured),
    )

    response = TestClient(app).post(
        "/internal/v1/query-streams",
        headers={"Authorization": "Bearer token", "x-request-id": "req_stream"},
        json={
            "kb_ids": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
            "query": "员工手册",
            "mode": "answer",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"streaming":true' in response.text
    assert 'data: {"delta":"员工年假"}' in response.text
    assert 'data: {"delta":"需要提前申请。"}' in response.text
    assert "[source:chunk_1]" not in response.text
    assert "event: citation" in response.text
    assert "event: done" in response.text
    assert '"debug_id":"dbg_' in response.text
    assert '"request_id"' not in response.text
    assert '"trace_id"' not in response.text
    assert captured["required_scope"] == "rag:query"
    assert captured["final_answer"] == "员工年假需要提前申请。[source:chunk_1]"
    assert captured["query_text"] == "员工手册"
    assert captured["conversation_complete_kwargs"]["answer"] == "员工年假需要提前申请。"


def test_create_query_route_returns_service_error(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    _patch_query_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda *_args, **_kwargs: _auth_context(),
    )
    captured: dict[str, object] = {}
    _patch_conversation_service(monkeypatch, captured)

    def _raise_error(*_args, **_kwargs):
        raise QueryServiceError("QUERY_FILTER_UNSUPPORTED", "unsupported", status_code=400)

    monkeypatch.setattr(
        "app.api.routes.query_execute.build_query_service",
        lambda _session: _FakeQueryService(_raise_error),
    )

    response = TestClient(app).post(
        "/internal/v1/queries",
        headers={"Authorization": "Bearer token"},
        json={
            "kb_ids": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
            "query": "员工手册",
            "filters": {"custom_acl": "x"},
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "QUERY_FILTER_UNSUPPORTED"
    assert captured["conversation_fail_kwargs"]["degrade_reason"] == "QUERY_FILTER_UNSUPPORTED"


def test_query_conversation_routes_use_current_user_scope(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    _patch_query_session_scope(monkeypatch)
    captured: dict[str, object] = {}
    _patch_conversation_service(monkeypatch, captured)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda *_args, **kwargs: (captured.update(kwargs) or _auth_context()),
    )

    client = TestClient(app)
    list_response = client.get(
        "/internal/v1/query-conversations",
        headers={"Authorization": "Bearer token", "x-request-id": "req_list"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["title"] == "员工手册"
    assert captured["conversation_list_kwargs"]["user_id"] == (
        "11111111-1111-1111-1111-111111111111"
    )

    detail_response = client.get(
        "/internal/v1/query-conversations/22222222-2222-2222-2222-222222222222",
        headers={"Authorization": "Bearer token", "x-request-id": "req_get"},
    )
    assert detail_response.status_code == 200
    message = detail_response.json()["messages"][0]
    assert message["content"] == "员工手册"
    assert message["debug_id"].startswith("dbg_")
    assert "request_id" not in message
    assert "trace_id" not in message
    assert detail_response.json()["messages_pagination"] == {
        "page": 1,
        "page_size": 50,
        "total": 1,
    }
    assert captured["conversation_get_kwargs"]["page"] == 1
    assert captured["conversation_get_kwargs"]["page_size"] == 50

    paged_detail_response = client.get(
        "/internal/v1/query-conversations/22222222-2222-2222-2222-222222222222"
        "?page=2&page_size=10",
        headers={"Authorization": "Bearer token", "x-request-id": "req_get_page"},
    )
    assert paged_detail_response.status_code == 200
    assert paged_detail_response.json()["messages_pagination"] == {
        "page": 2,
        "page_size": 10,
        "total": 1,
    }
    assert captured["conversation_get_kwargs"]["page"] == 2
    assert captured["conversation_get_kwargs"]["page_size"] == 10

    delete_response = client.delete(
        "/internal/v1/query-conversations/22222222-2222-2222-2222-222222222222",
        headers={"Authorization": "Bearer token", "x-request-id": "req_delete"},
    )
    assert delete_response.status_code == 204
    assert captured["conversation_delete_kwargs"]["conversation_id"] == (
        "22222222-2222-2222-2222-222222222222"
    )


def _query_context() -> QueryContext:
    return QueryContext(
        query_text="员工手册",
        chunks=(
            ContextChunk(
                chunk_id="chunk_1",
                document_id="44444444-4444-4444-4444-444444444444",
                document_version_id="55555555-5555-5555-5555-555555555555",
                title="员工手册",
                content="员工年假需要提前申请。",
                heading_path="制度/请假",
                page_start=1,
                page_end=2,
                score=0.9,
                rank=1,
            ),
        ),
        estimated_tokens=10,
        truncated=False,
    )
