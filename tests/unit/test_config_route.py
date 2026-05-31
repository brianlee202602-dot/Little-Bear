from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser
from app.modules.config.schemas import (
    ConfigItem,
    ConfigItemList,
    ConfigValidationResult,
    ConfigVersion,
    ConfigVersionList,
)
from app.modules.setup.service import SetupState, SetupStatus
from fastapi.testclient import TestClient

AUTH_TARGET = "app.api.dependencies.auth.AuthService.authenticate_access_token"


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


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


def _patch_config_session_scope(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.config_items.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.config_versions.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.config_validations.session_scope", lambda: _FakeSession())


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


def _config_manager_without_system_admin_role() -> AuthContext:
    user = AuthUser(
        id="22222222-2222-2222-2222-222222222222",
        enterprise_id="ent_1",
        username="config_manager",
        display_name="配置管理员",
        status="active",
        roles=(
            AuthRole(
                id="role_2",
                code="config_manager",
                name="Config Manager",
                scope_type="enterprise",
                is_builtin=False,
                status="active",
                scopes=("config:manage",),
            ),
        ),
        scopes=("config:read", "config:manage"),
    )
    return AuthContext(
        user=user,
        token_jti="access_2",
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
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(AUTH_TARGET, authenticate)
    monkeypatch.setattr(
        "app.api.routes.config_items.ConfigService.list_config_items",
        lambda _self, _session, *, page, page_size: ConfigItemList(
            items=[
                ConfigItem(
                    key="auth",
                    value_json={"access_token_ttl_minutes": 30},
                    scope_type="global",
                    status="active",
                    version=1,
                )
            ],
            total=1,
        ),
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
    assert "value_json" not in payload["data"][0]
    assert payload["pagination"] == {"page": 1, "page_size": 50, "total": 1}


def test_config_write_route_requires_system_admin_role(monkeypatch) -> None:
    called = False

    def validate_config_payload(_self, _session, **_kwargs):
        nonlocal called
        called = True
        return ConfigValidationResult(valid=True)

    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _config_manager_without_system_admin_role(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_validations.ConfigService.validate_config_payload",
        validate_config_payload,
    )

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/config-validations",
        headers={"authorization": "Bearer access.jwt"},
        json={"config": {"schema_version": 1}},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH_SYSTEM_ADMIN_REQUIRED"
    assert called is False


def test_high_risk_config_put_requires_confirmation(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
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
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_validations.ConfigService.validate_config_payload",
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


def test_config_version_list_route_returns_paginated_summary_without_config(monkeypatch) -> None:
    seen: dict[str, int] = {}

    def list_versions(_self, _session, *, page, page_size):
        seen["page"] = page
        seen["page_size"] = page_size
        return ConfigVersionList(
            items=[
                ConfigVersion(
                    version=3,
                    status="draft",
                    risk_level="medium",
                    created_by="11111111-1111-1111-1111-111111111111",
                    config={"auth": {"jwt_issuer": "must-not-leak"}},
                    created_at=datetime(2026, 5, 22, tzinfo=UTC),
                    updated_at=datetime(2026, 5, 22, tzinfo=UTC),
                )
            ],
            total=7,
        )

    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.ConfigService.list_config_versions",
        list_versions,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/config-versions?page=2&page_size=5",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen == {"page": 2, "page_size": 5}
    payload = response.json()
    assert payload["pagination"] == {"page": 2, "page_size": 5, "total": 7}
    assert payload["data"][0]["version"] == 3
    assert "config" not in payload["data"][0]


def test_config_version_create_route_requires_confirmation(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/config-versions",
        headers={"authorization": "Bearer access.jwt"},
        json={"config": {"schema_version": 1}},
    )

    assert response.status_code == 428
    assert response.json()["error_code"] == "CONFIG_CONFIRMATION_REQUIRED"


def test_config_version_create_route_saves_full_config(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def create_version(_self, _session, *, config, actor_user_id):
        seen["config"] = config
        seen["actor_user_id"] = actor_user_id
        return ConfigVersion(
            version=2,
            status="draft",
            risk_level="medium",
            created_by=actor_user_id,
            config=config,
            created_at=datetime(2026, 5, 22, tzinfo=UTC),
            updated_at=datetime(2026, 5, 22, tzinfo=UTC),
        )

    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.ConfigService.create_config_version",
        create_version,
    )

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/config-versions",
        headers={
            "authorization": "Bearer access.jwt",
            "x-config-confirm": "save-draft",
        },
        json={"config": {"schema_version": 1, "auth": {"jwt_issuer": "little-bear-rag"}}},
    )

    assert response.status_code == 200
    assert response.json()["data"]["version"] == 2
    assert response.json()["data"]["config"]["auth"]["jwt_issuer"] == "little-bear-rag"
    assert seen["actor_user_id"] == "11111111-1111-1111-1111-111111111111"


def test_config_version_update_route_updates_existing_version(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def update_version(_self, _session, *, version, config, actor_user_id):
        seen["version"] = version
        seen["config"] = config
        seen["actor_user_id"] = actor_user_id
        return ConfigVersion(
            version=version,
            status="draft",
            risk_level="medium",
            created_by=actor_user_id,
            config=config,
        )

    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.ConfigService.update_config_version",
        update_version,
    )

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/admin/config-versions/2",
        headers={
            "authorization": "Bearer access.jwt",
            "x-config-confirm": "save-draft",
        },
        json={"config": {"schema_version": 1, "auth": {"jwt_issuer": "little-bear-rag"}}},
    )

    assert response.status_code == 200
    assert response.json()["data"]["version"] == 2
    assert seen == {
        "version": 2,
        "config": {"schema_version": 1, "auth": {"jwt_issuer": "little-bear-rag"}},
        "actor_user_id": "11111111-1111-1111-1111-111111111111",
    }


def test_config_publish_route_requires_confirmation(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
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
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.ConfigService.publish_config_version",
        lambda _self, _session, **_kwargs: ConfigVersion(
            version=2,
            status="active",
            risk_level="high",
            created_by="11111111-1111-1111-1111-111111111111",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER.invalidate",
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


def test_config_patch_route_archives_version(monkeypatch) -> None:
    seen: dict[str, int | str | None] = {}

    def archive(_self, _session, *, version, actor_user_id):
        seen["version"] = version
        seen["actor_user_id"] = actor_user_id
        return ConfigVersion(
            version=version,
            status="archived",
            risk_level="medium",
            created_by=actor_user_id,
        )

    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.ConfigService.archive_config_version",
        archive,
    )

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/config-versions/2",
        headers={
            "authorization": "Bearer access.jwt",
            "x-config-confirm": "archive",
        },
        json={"status": "archived"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "archived"
    assert seen == {
        "version": 2,
        "actor_user_id": "11111111-1111-1111-1111-111111111111",
    }


def test_config_delete_draft_route_requires_confirmation(monkeypatch) -> None:
    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/admin/config-versions/2",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 428
    assert response.json()["error_code"] == "CONFIG_CONFIRMATION_REQUIRED"


def test_config_delete_draft_route_archives_version(monkeypatch) -> None:
    seen: dict[str, int | str | None] = {}

    def archive(_self, _session, *, version, actor_user_id):
        seen["version"] = version
        seen["actor_user_id"] = actor_user_id
        return None

    _open_business_api(monkeypatch)
    _patch_config_session_scope(monkeypatch)
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.config_versions.ConfigService.archive_config_version",
        archive,
    )

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/admin/config-versions/2",
        headers={
            "authorization": "Bearer access.jwt",
            "x-config-confirm": "archive",
        },
    )

    assert response.status_code == 204
    assert seen == {
        "version": 2,
        "actor_user_id": "11111111-1111-1111-1111-111111111111",
    }
