from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.audit.schemas import AuditLog, AuditLogList
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
