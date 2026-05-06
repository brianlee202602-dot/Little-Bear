from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.runtime import AuthRuntimeConfig, AuthRuntimeConfigProvider
from app.modules.auth.schemas import AuthRole, AuthUser
from app.modules.auth.service import AuthService

AUTH_RUNTIME = AuthRuntimeConfig(
    config_version=1,
    auth_config={
        "password_min_length": 12,
        "password_require_uppercase": True,
        "password_require_lowercase": True,
        "password_require_digit": True,
        "password_require_symbol": False,
        "login_failure_limit": 5,
        "lock_minutes": 15,
        "access_token_ttl_minutes": 30,
        "refresh_token_ttl_minutes": 10080,
        "jwt_issuer": "little-bear-rag",
        "jwt_audience": "little-bear-internal",
        "jwt_signing_key_ref": "secret://rag/auth/jwt-signing-key",
    },
    jwt_issuer="little-bear-rag",
    jwt_audience="little-bear-internal",
    jwt_signing_key_ref="secret://rag/auth/jwt-signing-key",
    jwt_signing_secret="jwt-secret",
)


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        return None


class _Snapshot:
    def __init__(self, version: int = 1) -> None:
        self.version = version

    def section(self, name: str) -> dict[str, object]:
        assert name == "auth"
        return dict(AUTH_RUNTIME.auth_config)


class _ConfigService:
    def __init__(self) -> None:
        self.calls = 0
        self.version = 1

    def get_active_config(self):
        self.calls += 1
        return _Snapshot(version=self.version)


class _SecretStore:
    def __init__(self) -> None:
        self.calls = 0

    def get_secret_value(self, _session, *, secret_ref: str) -> str:
        self.calls += 1
        assert secret_ref == "secret://rag/auth/jwt-signing-key"
        return "jwt-secret"


def _token_row(*, expires_at: datetime | None = None) -> dict[str, object]:
    return {
        "jti": "access_1",
        "enterprise_id": "ent_1",
        "subject_user_id": "user_1",
        "token_type": "access",
        "status": "active",
        "scopes": ["*"],
        "expires_at": expires_at or datetime.now(UTC) + timedelta(minutes=5),
        "metadata_json": {"session_id": "sess_1"},
    }


def _user(scopes: tuple[str, ...]) -> AuthUser:
    return AuthUser(
        id="user_1",
        enterprise_id="ent_1",
        username="admin",
        display_name="Admin",
        status="active",
        roles=(
            AuthRole(
                id="role_1",
                code="custom",
                name="Custom",
                scope_type="enterprise",
                is_builtin=False,
                status="active",
                scopes=scopes,
            ),
        ),
        scopes=scopes,
    )


def test_access_scope_requires_current_database_scope(monkeypatch) -> None:
    service = AuthService()
    monkeypatch.setattr(service, "_load_auth_runtime", lambda _session: AUTH_RUNTIME)
    monkeypatch.setattr(
        service,
        "_decode_token",
        lambda *_args, **_kwargs: {
            "jti": "access_1",
            "sub": "user_1",
            "enterprise_id": "ent_1",
            "scopes": ["*"],
        },
    )
    monkeypatch.setattr(service, "_load_token_row", lambda *_args, **_kwargs: _token_row())
    monkeypatch.setattr(service, "_load_user_context", lambda *_args: _user(("auth:session",)))

    with pytest.raises(AuthServiceError) as exc_info:
        service.authenticate_access_token(
            _FakeSession(),
            access_token="access.jwt",
            required_scope="config:manage",
        )

    assert exc_info.value.error_code == "AUTH_SCOPE_FORBIDDEN"
    assert exc_info.value.details["token_scope_allowed"] is True
    assert exc_info.value.details["current_scope_allowed"] is False


def test_access_scope_requires_token_scope_too(monkeypatch) -> None:
    service = AuthService()
    monkeypatch.setattr(service, "_load_auth_runtime", lambda _session: AUTH_RUNTIME)
    monkeypatch.setattr(
        service,
        "_decode_token",
        lambda *_args, **_kwargs: {
            "jti": "access_1",
            "sub": "user_1",
            "enterprise_id": "ent_1",
            "scopes": ["auth:session"],
        },
    )
    monkeypatch.setattr(service, "_load_token_row", lambda *_args, **_kwargs: _token_row())
    monkeypatch.setattr(service, "_load_user_context", lambda *_args: _user(("*",)))

    with pytest.raises(AuthServiceError) as exc_info:
        service.authenticate_access_token(
            _FakeSession(),
            access_token="access.jwt",
            required_scope="config:manage",
        )

    assert exc_info.value.error_code == "AUTH_SCOPE_FORBIDDEN"
    assert exc_info.value.details["token_scope_allowed"] is False
    assert exc_info.value.details["current_scope_allowed"] is True


def test_logout_revoke_is_bound_to_subject_and_enterprise(monkeypatch) -> None:
    service = AuthService()
    session = _FakeSession()
    monkeypatch.setattr(service, "_load_auth_runtime", lambda _session: AUTH_RUNTIME)
    monkeypatch.setattr(
        service,
        "_decode_token",
        lambda *_args, **_kwargs: {
            "jti": "access_1",
            "sub": "user_1",
            "enterprise_id": "ent_1",
            "sid": "sess_1",
        },
    )
    monkeypatch.setattr(service, "_load_token_row", lambda *_args, **_kwargs: _token_row())

    service.revoke_current_session(session, access_token="access.jwt")

    sql, params = session.executed[-1]
    assert "subject_user_id = :subject_user_id" in sql
    assert "enterprise_id = :enterprise_id" in sql
    assert params["subject_user_id"] == "user_1"
    assert params["enterprise_id"] == "ent_1"
    assert params["session_id"] == "sess_1"


def test_expired_token_row_is_marked_expired() -> None:
    service = AuthService()
    session = _FakeSession()
    row = _token_row(expires_at=datetime.now(UTC) - timedelta(seconds=1))

    with pytest.raises(AuthServiceError) as exc_info:
        service._assert_token_row_active(session, row, token_type="access")

    assert exc_info.value.error_code == "AUTH_TOKEN_EXPIRED"
    sql, params = session.executed[-1]
    assert "SET status = 'expired'" in sql
    assert params["jti"] == "access_1"


def test_auth_runtime_config_provider_reuses_secret_until_version_changes() -> None:
    config_service = _ConfigService()
    secret_store = _SecretStore()
    provider = AuthRuntimeConfigProvider()
    session = _FakeSession()

    first = provider.get(session, config_service=config_service, secret_store=secret_store)
    second = provider.get(session, config_service=config_service, secret_store=secret_store)
    config_service.version = 2
    third = provider.get(session, config_service=config_service, secret_store=secret_store)

    assert first.jwt_signing_secret == "jwt-secret"
    assert second is first
    assert third.config_version == 2
    assert secret_store.calls == 2
