from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.admin.schemas import AdminPermissionPolicy
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
        display_name="权限管理员",
        status="active",
        roles=(
            AuthRole(
                id="role_1",
                code="security_admin",
                name="Security Admin",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=("permission:manage",),
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
        scopes=("permission:manage",),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id, "iat": int(datetime.now(UTC).timestamp())},
    )


def test_put_document_permissions_requires_permission_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def replace_document_permissions(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminPermissionPolicy(
            resource_type="document",
            resource_id=kwargs["doc_id"],
            visibility=kwargs["visibility"],
            permission_version=21,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.permissions.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.permissions.AuthService.authenticate_access_token",
        authenticate,
    )
    monkeypatch.setattr(
        "app.api.routes.permissions.AdminService.replace_document_permissions",
        replace_document_permissions,
    )

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/documents/doc_1/permissions",
        headers={
            "authorization": "Bearer access.jwt",
            "x-permission-confirm": "replace",
        },
        json={"visibility": "enterprise", "owner_department_id": "department_1"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "permission:manage"
    assert seen["doc_id"] == "doc_1"
    assert seen["confirmed"] is True
    assert seen["owner_department_id"] == "department_1"
    assert response.json()["data"]["permission_version"] == 21


def test_put_knowledge_base_permissions_requires_confirmation(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def replace_knowledge_base_permissions(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminPermissionPolicy(
            resource_type="knowledge_base",
            resource_id=kwargs["kb_id"],
            visibility=kwargs["visibility"],
            permission_version=22,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.permissions.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.permissions.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.permissions.AdminService.replace_knowledge_base_permissions",
        replace_knowledge_base_permissions,
    )

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/knowledge-bases/kb_1/permissions",
        headers={"authorization": "Bearer access.jwt"},
        json={"visibility": "department"},
    )

    assert response.status_code == 200
    assert seen["kb_id"] == "kb_1"
    assert seen["confirmed"] is False
    assert response.json()["data"]["resource_type"] == "knowledge_base"
