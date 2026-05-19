from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.audit.schemas import (
    AuditLog,
    AuditLogList,
    ModelCallLog,
    ModelCallLogList,
    QueryLog,
    QueryLogList,
)
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser
from app.modules.setup.service import SetupState, SetupStatus
from fastapi.testclient import TestClient


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _create_test_app():
    return create_app(run_startup_checks=False)


def _open_business_api(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.shared.middleware.SetupService.load_state",
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
        id="user_1",
        enterprise_id="ent_1",
        username="admin",
        display_name="系统管理员",
        status="active",
        roles=(
            AuthRole(
                id="role_1",
                code="audit_admin",
                name="Audit Admin",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=("audit:read",),
            ),
        ),
        scopes=("audit:read",),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id},
    )


def _audit_log() -> AuditLog:
    return AuditLog(
        id="audit_1",
        request_id="req_1",
        trace_id="trace_1",
        event_name="config.published",
        actor_type="user",
        actor_id="user_1",
        action="publish",
        resource_type="config",
        resource_id="2",
        result="success",
        risk_level="critical",
        config_version=2,
        permission_version=None,
        index_version_hash=None,
        summary_json={"previous_active_version": 1},
        error_code=None,
        created_at=datetime.now(UTC),
    )


def _query_log() -> QueryLog:
    return QueryLog(
        id="query_log_1",
        request_id="req_query",
        trace_id="trace_query",
        user_id="user_1",
        kb_ids=("kb_1",),
        query_hash="hash_query",
        status="success",
        degraded=False,
        degrade_reason=None,
        config_version=1,
        permission_version=3,
        permission_filter_hash="hash_permission",
        index_version_hash="hash_index",
        model_route_hash="hash_model",
        latency_ms=321,
        candidate_count=5,
        citation_count=2,
        error_code=None,
        created_at=datetime.now(UTC),
    )


def _model_call_log() -> ModelCallLog:
    return ModelCallLog(
        id="model_call_1",
        request_id="req_query",
        trace_id="trace_query",
        caller="query.answer",
        model_type="llm",
        model_name="qwen2.5",
        model_version=None,
        model_route_hash="hash_model",
        status="success",
        latency_ms=654,
        token_usage_json={"prompt_tokens": 10, "completion_tokens": 20},
        degraded=False,
        config_version=1,
        prompt_hash="hash_prompt",
        input_hash="hash_input",
        output_hash="hash_output",
        error_code=None,
        created_at=datetime.now(UTC),
    )


def test_audit_log_list_route_requires_audit_read_scope(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.audit.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.audit.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.audit.AuditService.list_audit_logs",
        lambda _self, _session, **_kwargs: AuditLogList(items=[_audit_log()], total=1),
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/audit-logs?resource_type=config",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_audit"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "audit:read"
    payload = response.json()
    assert payload["request_id"] == "req_audit"
    assert payload["data"][0]["event_name"] == "config.published"
    assert payload["pagination"]["total"] == 1


def test_audit_log_get_route_returns_single_log(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.audit.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.audit.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.audit.AuditService.get_audit_log",
        lambda _self, _session, _audit_id: _audit_log(),
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/audit-logs/audit_1",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "audit_1"


def test_query_log_list_route_requires_audit_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_query_logs(_self, _session, **kwargs):
        seen.update(kwargs)
        return QueryLogList(items=[_query_log()], total=1)

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.audit.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.audit.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.audit.AuditService.list_query_logs", list_query_logs)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/query-logs?trace_id=trace_query&degraded=false",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "audit:read"
    assert seen["enterprise_id"] == "ent_1"
    assert seen["filters"]["trace_id"] == "trace_query"
    assert seen["filters"]["degraded"] is False
    assert response.json()["data"][0]["candidate_count"] == 5


def test_query_log_get_route_returns_single_log(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def get_query_log(_self, _session, **kwargs):
        seen.update(kwargs)
        return _query_log()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.audit.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.audit.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.audit.AuditService.get_query_log", get_query_log)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/query-logs/query_log_1",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["query_log_id"] == "query_log_1"
    assert response.json()["data"]["trace_id"] == "trace_query"


def test_model_call_log_list_route_requires_audit_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_model_call_logs(_self, _session, **kwargs):
        seen.update(kwargs)
        return ModelCallLogList(items=[_model_call_log()], total=1)

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.audit.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.audit.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.audit.AuditService.list_model_call_logs",
        list_model_call_logs,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/model-call-logs?trace_id=trace_query&model=qwen",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "audit:read"
    assert seen["filters"]["trace_id"] == "trace_query"
    assert seen["filters"]["model"] == "qwen"
    assert response.json()["data"][0]["model_name"] == "qwen2.5"
