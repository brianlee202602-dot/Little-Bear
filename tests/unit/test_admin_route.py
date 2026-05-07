from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminRole,
    AdminRoleBinding,
    AdminUser,
    AdminUserList,
)
from app.modules.auth.schemas import AuthContext, AuthDepartment, AuthRole, AuthUser
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
                code="system_admin",
                name="System Admin",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=("*",),
            ),
        ),
        departments=(
            AuthDepartment(
                id="department_1",
                code="default",
                name="默认部门",
                status="active",
                is_primary=True,
            ),
        ),
        scopes=("*", "user:read", "user:manage", "role:read", "role:manage"),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id, "iat": int(datetime.now(UTC).timestamp())},
    )


def _admin_role() -> AdminRole:
    return AdminRole(
        id="role_1",
        code="system_admin",
        name="System Admin",
        scope_type="enterprise",
        is_builtin=True,
        status="active",
        scopes=("*",),
    )


def _admin_user() -> AdminUser:
    return AdminUser(
        id="user_2",
        username="alice",
        name="Alice",
        status="active",
        enterprise_id="ent_1",
        departments=(
            AdminDepartment(
                id="department_1",
                code="default",
                name="默认部门",
                status="active",
                is_primary=True,
            ),
        ),
        roles=(_admin_role(),),
        scopes=("*", "auth:session"),
    )


def _binding() -> AdminRoleBinding:
    return AdminRoleBinding(
        id="binding_1",
        role_id="role_1",
        subject_type="user",
        subject_id="user_2",
        scope_type="enterprise",
        scope_id=None,
        role_code="system_admin",
        role_name="System Admin",
    )


def test_admin_user_list_route_requires_user_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    def list_users(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminUserList(items=[_admin_user()], total=1)

    monkeypatch.setattr("app.api.routes.admin.AdminService.list_users", list_users)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/users",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_users"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "user:read"
    assert seen["actor_context"].user_id == "user_1"
    assert seen["actor_context"].department_ids == ("department_1",)
    payload = response.json()
    assert payload["request_id"] == "req_users"
    assert payload["data"][0]["username"] == "alice"
    assert payload["pagination"]["total"] == 1


def test_admin_user_create_passes_high_risk_confirmation(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def create_user(_self, _session, **kwargs):
        seen.update(kwargs)
        return _admin_user()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.create_user", create_user)

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/users",
        headers={
            "authorization": "Bearer access.jwt",
            "x-user-confirm": "create-admin",
        },
        json={
            "username": "alice",
            "name": "Alice",
            "initial_password": "ChangeMe_123456",
            "department_ids": [],
            "role_ids": ["role_1"],
        },
    )

    assert response.status_code == 201
    assert seen["confirmed_high_risk"] is True
    assert seen["actor_user_id"] == "user_1"
    assert seen["actor_context"].user_id == "user_1"
    assert seen["actor_context"].department_ids == ("department_1",)


def test_role_list_route_requires_role_read_scope(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.list_roles",
        lambda _self, _session, **_kwargs: [_admin_role()],
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/roles",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "role:read"
    assert response.json()["data"][0]["code"] == "system_admin"


def test_role_binding_replace_passes_confirmation_header(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def replace_bindings(_self, _session, **kwargs):
        seen.update(kwargs)
        return [_binding()]

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.replace_role_bindings", replace_bindings)

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/admin/users/user_2/role-bindings",
        headers={
            "authorization": "Bearer access.jwt",
            "x-role-binding-confirm": "replace",
        },
        json={"bindings": [{"role_id": "role_1", "scope_type": "enterprise"}]},
    )

    assert response.status_code == 200
    assert seen["confirmed"] is True
    assert seen["bindings"][0].role_id == "role_1"
    assert seen["actor_context"].user_id == "user_1"
    assert seen["actor_context"].department_ids == ("department_1",)


def test_role_binding_create_returns_structured_admin_error(monkeypatch) -> None:
    def create_binding(_self, _session, **_kwargs):
        raise AdminServiceError(
            "ADMIN_CONFIRMATION_REQUIRED",
            "granting high-risk role requires confirmation",
            status_code=428,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.create_role_bindings", create_binding)

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/users/user_2/role-bindings",
        headers={"authorization": "Bearer access.jwt"},
        json={"bindings": [{"role_id": "role_1", "scope_type": "enterprise"}]},
    )

    assert response.status_code == 428
    assert response.json()["error_code"] == "ADMIN_CONFIRMATION_REQUIRED"
    assert response.json()["stage"] == "admin_role_binding_create"
