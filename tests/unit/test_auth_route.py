from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.main import create_app
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser, TokenPair
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


def _token_pair() -> TokenPair:
    now = datetime.now(UTC)
    return TokenPair(
        access_token="access.jwt",
        refresh_token="refresh.jwt",
        token_type="Bearer",
        expires_in=1800,
        refresh_expires_in=604800,
        access_jti="access_1",
        refresh_jti="refresh_1",
        access_expires_at=now + timedelta(minutes=30),
        refresh_expires_at=now + timedelta(days=7),
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
                code="system_admin",
                name="System Admin",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=("*",),
            ),
        ),
        scopes=("*", "auth:session"),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": "user_1"},
    )


def test_create_session_route_returns_token_pair(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.auth.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.auth.AuthService.create_session",
        lambda _self, _session, **_kwargs: _token_pair(),
    )

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/sessions",
        json={"username": "admin", "password": "ChangeMe_123456"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access.jwt"
    assert response.json()["refresh_token"] == "refresh.jwt"
    assert response.json()["token_type"] == "Bearer"


def test_create_session_route_returns_structured_auth_error(monkeypatch) -> None:
    def reject_login(_self, _session, **_kwargs):
        raise AuthServiceError("AUTH_INVALID_CREDENTIALS", "username or password is invalid")

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.auth.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.auth.AuthService.create_session", reject_login)

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/sessions",
        headers={"x-request-id": "req_auth"},
        json={"username": "admin", "password": "wrong"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["request_id"] == "req_auth"
    assert payload["error_code"] == "AUTH_INVALID_CREDENTIALS"
    assert payload["stage"] == "auth_login"


def test_token_refresh_route_uses_refresh_bearer_token(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def refresh(_self, _session, *, refresh_token, **_kwargs):
        seen["refresh_token"] = refresh_token
        return _token_pair()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.auth.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.auth.AuthService.refresh_session", refresh)

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/token-refreshes",
        headers={"authorization": "Bearer refresh.jwt"},
    )

    assert response.status_code == 200
    assert seen["refresh_token"] == "refresh.jwt"


def test_current_user_route_wraps_user_response(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.auth.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.auth.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/users/me",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_me"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req_me"
    assert payload["data"]["username"] == "admin"
    assert payload["data"]["roles"][0]["code"] == "system_admin"


def test_logout_route_returns_204(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.auth.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.auth.AuthService.revoke_current_session",
        lambda _self, _session, **_kwargs: None,
    )

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/sessions/current",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 204


def test_password_change_route_returns_204(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.auth.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.auth.AuthService.change_current_password",
        lambda _self, _session, **_kwargs: None,
    )

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/users/me/password",
        headers={"authorization": "Bearer access.jwt"},
        json={"old_password": "OldPassword_123", "new_password": "NewPassword_123"},
    )

    assert response.status_code == 204
