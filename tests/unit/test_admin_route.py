from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminDepartmentList,
    AdminKnowledgeBase,
    AdminKnowledgeBaseList,
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
        scopes=(
            "*",
            "user:read",
            "user:manage",
            "org:read",
            "org:manage",
            "role:read",
            "role:manage",
        ),
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


def _admin_department() -> AdminDepartment:
    return AdminDepartment(
        id="department_1",
        code="default",
        name="默认部门",
        status="active",
        is_primary=False,
        is_default=True,
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
                is_default=True,
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


def _knowledge_base() -> AdminKnowledgeBase:
    return AdminKnowledgeBase(
        id="kb_1",
        name="制度知识库",
        status="active",
        owner_department_id="department_1",
        default_visibility="department",
        config_scope_id=None,
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


def test_department_list_route_requires_org_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_departments(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminDepartmentList(items=[_admin_department()], total=1)

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.list_departments", list_departments)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/departments",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_departments"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "org:read"
    assert seen["enterprise_id"] == "ent_1"
    payload = response.json()
    assert payload["request_id"] == "req_departments"
    assert payload["data"][0]["code"] == "default"
    assert payload["data"][0]["is_default"] is True
    assert payload["pagination"]["total"] == 1


def test_department_create_route_requires_org_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def create_department(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminDepartment(
            id="department_2",
            code=kwargs["code"],
            name=kwargs["name"],
            status="active",
            is_default=False,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.create_department", create_department)

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/departments",
        headers={"authorization": "Bearer access.jwt"},
        json={"code": "engineering", "name": "研发部"},
    )

    assert response.status_code == 201
    assert seen["required_scope"] == "org:manage"
    assert seen["actor_user_id"] == "user_1"
    assert seen["actor_context"].user_id == "user_1"
    assert response.json()["data"]["name"] == "研发部"


def test_knowledge_base_list_route_requires_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_knowledge_bases(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminKnowledgeBaseList(items=[_knowledge_base()], total=1)

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.list_knowledge_bases",
        list_knowledge_bases,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/knowledge-bases",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_kbs"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "knowledge_base:manage"
    assert seen["enterprise_id"] == "ent_1"
    payload = response.json()
    assert payload["request_id"] == "req_kbs"
    assert payload["data"][0]["name"] == "制度知识库"
    assert payload["pagination"]["total"] == 1


def test_department_get_route_requires_org_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def get_department(_self, _session, department_id, **kwargs):
        seen["department_id"] = department_id
        seen.update(kwargs)
        return _admin_department()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.get_department", get_department)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/departments/department_1",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "org:read"
    assert seen["department_id"] == "department_1"
    assert seen["enterprise_id"] == "ent_1"


def test_department_patch_route_passes_actor_context(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def patch_department(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminDepartment(
            id=kwargs["department_id"],
            code="engineering",
            name=kwargs["name"],
            status=kwargs["status"],
            is_default=False,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.patch_department", patch_department)

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/departments/department_2",
        headers={"authorization": "Bearer access.jwt"},
        json={"name": "研发平台部", "status": "disabled"},
    )

    assert response.status_code == 200
    assert seen["actor_user_id"] == "user_1"
    assert seen["department_id"] == "department_2"
    assert seen["actor_context"].department_ids == ("department_1",)
    assert response.json()["data"]["status"] == "disabled"


def test_department_delete_route_passes_confirmation_header(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def delete_department(_self, _session, **kwargs):
        seen.update(kwargs)

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.delete_department", delete_department)

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/admin/departments/department_2",
        headers={
            "authorization": "Bearer access.jwt",
            "x-department-confirm": "delete",
        },
    )

    assert response.status_code == 204
    assert seen["confirmed"] is True
    assert seen["department_id"] == "department_2"
    assert seen["actor_context"].user_id == "user_1"


def test_user_departments_list_route_requires_org_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_user_departments(_self, _session, **kwargs):
        seen.update(kwargs)
        return [_admin_department()]

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.list_user_departments",
        list_user_departments,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/users/user_2/departments",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "org:read"
    assert seen["user_id"] == "user_2"
    assert seen["actor_context"].user_id == "user_1"
    assert response.json()["data"][0]["code"] == "default"


def test_user_departments_replace_route_passes_confirmation_header(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def replace_user_departments(_self, _session, **kwargs):
        seen.update(kwargs)
        return [
            AdminDepartment(
                id="department_2",
                code="engineering",
                name="研发部",
                status="active",
                is_primary=True,
            )
        ]

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.replace_user_departments",
        replace_user_departments,
    )

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/admin/users/user_2/departments",
        headers={
            "authorization": "Bearer access.jwt",
            "x-department-confirm": "replace-primary",
        },
        json={"department_ids": ["department_2"]},
    )

    assert response.status_code == 200
    assert seen["user_id"] == "user_2"
    assert seen["department_ids"] == ["department_2"]
    assert seen["confirmed_remove_primary"] is True
    assert seen["actor_context"].department_ids == ("department_1",)
    assert response.json()["data"][0]["is_primary"] is True


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
