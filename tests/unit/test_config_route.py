from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser
from app.modules.config.schemas import ConfigItem, ConfigValidationResult, ConfigVersion
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
        id="11111111-1111-1111-1111-111111111111",
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
        scopes=("*", "config:read", "config:manage"),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id, "iat": int(datetime.now(UTC).timestamp())},
    )


def test_config_list_route_requires_config_read_scope(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.config.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.config.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.config.ConfigService.list_config_items",
        lambda _self, _session: [
            ConfigItem(
                key="auth",
                value_json={"access_token_ttl_minutes": 30},
                scope_type="global",
                status="active",
                version=1,
            )
        ],
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/configs",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_cfg"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "config:read"
    payload = response.json()
    assert payload["request_id"] == "req_cfg"
    assert payload["data"][0]["key"] == "auth"


def test_high_risk_config_put_requires_confirmation(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.config.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.config.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/admin/configs/auth",
        headers={"authorization": "Bearer access.jwt"},
        json={"value_json": {"access_token_ttl_minutes": 45}},
    )

    assert response.status_code == 428
    assert response.json()["error_code"] == "CONFIG_CONFIRMATION_REQUIRED"


def test_config_validation_route_returns_validation_result(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.config.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.config.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config.ConfigService.validate_config_payload",
        lambda _self, _session, **_kwargs: ConfigValidationResult(valid=True),
    )

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/config-validations",
        headers={"authorization": "Bearer access.jwt"},
        json={"config": {"schema_version": 1}},
    )

    assert response.status_code == 200
    assert response.json()["data"]["valid"] is True


def test_config_publish_route_requires_confirmation(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.config.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.config.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/config-versions/2",
        headers={"authorization": "Bearer access.jwt"},
        json={"status": "active"},
    )

    assert response.status_code == 428
    assert response.json()["error_code"] == "CONFIG_CONFIRMATION_REQUIRED"


def test_config_publish_route_invalidates_auth_runtime(monkeypatch) -> None:
    invalidated: dict[str, bool] = {}

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.config.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.config.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config.ConfigService.publish_config_version",
        lambda _self, _session, **_kwargs: ConfigVersion(
            version=2,
            status="active",
            risk_level="high",
            created_by="11111111-1111-1111-1111-111111111111",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.config.GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER.invalidate",
        lambda: invalidated.update({"value": True}),
    )

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/config-versions/2",
        headers={
            "authorization": "Bearer access.jwt",
            "x-config-confirm": "publish",
        },
        json={"status": "active"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"
    assert invalidated["value"] is True
