from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminChunk,
    AdminDepartment,
    AdminDepartmentList,
    AdminDocument,
    AdminDocumentList,
    AdminDocumentVersion,
    AdminFolder,
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


def _folder() -> AdminFolder:
    return AdminFolder(
        id="folder_1",
        kb_id="kb_1",
        parent_id=None,
        name="制度",
        status="active",
        path="/folder_1",
    )


def _document() -> AdminDocument:
    return AdminDocument(
        id="doc_1",
        kb_id="kb_1",
        folder_id="folder_1",
        title="员工手册",
        lifecycle_status="active",
        index_status="indexed",
        owner_department_id="department_1",
        visibility="department",
        current_version_id="version_1",
        tags=("制度",),
        permission_snapshot_id="snapshot_1",
        content_hash="hash_1",
        policy_version=1,
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
    assert seen["actor_context"].user_id == "user_1"
    payload = response.json()
    assert payload["request_id"] == "req_kbs"
    assert payload["data"][0]["name"] == "制度知识库"
    assert payload["pagination"]["total"] == 1


def test_knowledge_base_create_route_passes_confirmation_header(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def create_knowledge_base(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminKnowledgeBase(
            id="kb_2",
            name=kwargs["name"],
            status="active",
            owner_department_id=kwargs["owner_department_id"],
            default_visibility=kwargs["default_visibility"],
            config_scope_id=kwargs["config_scope_id"],
            policy_version=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.create_knowledge_base",
        create_knowledge_base,
    )

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/knowledge-bases",
        headers={
            "authorization": "Bearer access.jwt",
            "x-knowledge-base-confirm": "enterprise-visible",
        },
        json={
            "name": "制度知识库",
            "owner_department_id": "department_1",
            "default_visibility": "enterprise",
            "config_scope_id": "kb-default",
        },
    )

    assert response.status_code == 201
    assert seen["confirmed_enterprise_visibility"] is True
    assert seen["actor_context"].user_id == "user_1"
    assert seen["actor_context"].can_manage_all_knowledge_bases is True
    assert response.json()["data"]["policy_version"] == 1


def test_knowledge_base_get_route_requires_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def get_knowledge_base(_self, _session, kb_id, **kwargs):
        seen["kb_id"] = kb_id
        seen.update(kwargs)
        return _knowledge_base()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.get_knowledge_base",
        get_knowledge_base,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/knowledge-bases/kb_1",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "knowledge_base:manage"
    assert seen["kb_id"] == "kb_1"
    assert seen["enterprise_id"] == "ent_1"


def test_knowledge_base_patch_route_passes_visibility_confirmation(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def patch_knowledge_base(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminKnowledgeBase(
            id=kwargs["kb_id"],
            name=kwargs["name"],
            status=kwargs["status"],
            owner_department_id="department_1",
            default_visibility=kwargs["default_visibility"],
            config_scope_id=None,
            policy_version=2,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.patch_knowledge_base",
        patch_knowledge_base,
    )

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/knowledge-bases/kb_1",
        headers={
            "authorization": "Bearer access.jwt",
            "x-knowledge-base-confirm": "visibility-expand",
        },
        json={
            "name": "制度知识库",
            "status": "active",
            "default_visibility": "enterprise",
        },
    )

    assert response.status_code == 200
    assert seen["confirmed_visibility_expand"] is True
    assert seen["kb_id"] == "kb_1"
    assert response.json()["data"]["policy_version"] == 2


def test_knowledge_base_delete_route_returns_accepted_job(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def delete_knowledge_base(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminAcceptedResult(accepted=True, job_id="job_1")

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.delete_knowledge_base",
        delete_knowledge_base,
    )

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/admin/knowledge-bases/kb_1",
        headers={
            "authorization": "Bearer access.jwt",
            "x-knowledge-base-confirm": "delete",
        },
    )

    assert response.status_code == 202
    assert seen["confirmed"] is True
    assert seen["kb_id"] == "kb_1"
    assert response.json()["data"] == {"accepted": True, "job_id": "job_1"}


def test_folder_list_route_requires_folder_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_folders(_self, _session, **kwargs):
        seen.update(kwargs)
        return type("FolderList", (), {"items": [_folder()], "total": 1})()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.list_folders", list_folders)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/knowledge-bases/kb_1/folders",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "folder:manage"
    assert seen["kb_id"] == "kb_1"
    assert seen["actor_context"].user_id == "user_1"
    assert response.json()["data"][0]["name"] == "制度"


def test_folder_create_route_passes_parent_id(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def create_folder(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminFolder(
            id="folder_2",
            kb_id=kwargs["kb_id"],
            parent_id=kwargs["parent_id"],
            name=kwargs["name"],
            status="active",
            path="/folder_1/folder_2",
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.create_folder", create_folder)

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/admin/knowledge-bases/kb_1/folders",
        headers={"authorization": "Bearer access.jwt"},
        json={"name": "流程", "parent_id": "folder_1"},
    )

    assert response.status_code == 201
    assert seen["kb_id"] == "kb_1"
    assert seen["parent_id"] == "folder_1"
    assert response.json()["data"]["parent_id"] == "folder_1"


def test_folder_get_route_requires_folder_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def get_folder(_self, _session, folder_id, **kwargs):
        seen["folder_id"] = folder_id
        seen.update(kwargs)
        return _folder()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.get_folder", get_folder)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/folders/folder_1",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "folder:manage"
    assert seen["folder_id"] == "folder_1"


def test_folder_patch_route_passes_status(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def patch_folder(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminFolder(
            id=kwargs["folder_id"],
            kb_id="kb_1",
            parent_id=kwargs["parent_id"],
            name=kwargs["name"],
            status=kwargs["status"],
            path="/folder_2",
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.patch_folder", patch_folder)

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/folders/folder_1",
        headers={"authorization": "Bearer access.jwt"},
        json={"name": "流程", "parent_id": "folder_2", "status": "archived"},
    )

    assert response.status_code == 200
    assert seen["folder_id"] == "folder_1"
    assert seen["status"] == "archived"
    assert response.json()["data"]["status"] == "archived"


def test_folder_delete_route_returns_accepted_job(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def delete_folder(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminAcceptedResult(accepted=True, job_id="job_folder_1")

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.delete_folder", delete_folder)

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/admin/folders/folder_1",
        headers={"authorization": "Bearer access.jwt", "x-folder-confirm": "delete"},
    )

    assert response.status_code == 202
    assert seen["confirmed"] is True
    assert seen["folder_id"] == "folder_1"
    assert response.json()["data"] == {"accepted": True, "job_id": "job_folder_1"}


def test_document_list_route_requires_document_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_documents(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminDocumentList(items=[_document()], total=1)

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.list_documents", list_documents)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/knowledge-bases/kb_1/documents?status=active",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_documents"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "document:manage"
    assert seen["kb_id"] == "kb_1"
    assert seen["lifecycle_status"] == "active"
    assert seen["actor_context"].user_id == "user_1"
    payload = response.json()
    assert payload["request_id"] == "req_documents"
    assert payload["data"][0]["title"] == "员工手册"
    assert payload["pagination"]["total"] == 1


def test_document_get_route_requires_document_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def get_document(_self, _session, doc_id, **kwargs):
        seen["doc_id"] = doc_id
        seen.update(kwargs)
        return _document()

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr("app.api.routes.admin.AdminService.get_document", get_document)

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/documents/doc_1",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "document:manage"
    assert seen["doc_id"] == "doc_1"
    assert seen["enterprise_id"] == "ent_1"
    assert response.json()["data"]["current_version_id"] == "version_1"


def test_document_versions_route_requires_document_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_document_versions(_self, _session, **kwargs):
        seen.update(kwargs)
        return (
            AdminDocumentVersion(
                id="version_1",
                document_id=kwargs["doc_id"],
                version_no=1,
                status="active",
            ),
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.list_document_versions",
        list_document_versions,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/documents/doc_1/versions",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "document:manage"
    assert seen["doc_id"] == "doc_1"
    assert response.json()["data"][0]["version_no"] == 1


def test_document_chunks_route_requires_document_manage_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_document_chunks(_self, _session, **kwargs):
        seen.update(kwargs)
        return (
            AdminChunk(
                id="chunk_1",
                document_id=kwargs["doc_id"],
                document_version_id="version_1",
                text_preview="制度正文",
                page_start=1,
                page_end=1,
                status="active",
            ),
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr("app.api.routes.admin.AuthService.authenticate_access_token", authenticate)
    monkeypatch.setattr(
        "app.api.routes.admin.AdminService.list_document_chunks",
        list_document_chunks,
    )

    client = TestClient(_create_test_app())
    response = client.get(
        "/internal/v1/admin/documents/doc_1/chunks",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "document:manage"
    assert seen["doc_id"] == "doc_1"
    assert response.json()["data"][0]["text_preview"] == "制度正文"


def test_document_patch_route_passes_visibility_confirmation(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def patch_document(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminDocument(
            id=kwargs["doc_id"],
            kb_id="kb_1",
            folder_id=kwargs["folder_id"],
            title=kwargs["title"],
            lifecycle_status=kwargs["lifecycle_status"],
            index_status="indexed",
            owner_department_id=kwargs["owner_department_id"],
            visibility=kwargs["visibility"],
            current_version_id="version_1",
            tags=tuple(kwargs["tags"]),
            permission_snapshot_id="snapshot_2",
            policy_version=2,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.patch_document", patch_document)

    client = TestClient(_create_test_app())
    response = client.patch(
        "/internal/v1/admin/documents/doc_1",
        headers={
            "authorization": "Bearer access.jwt",
            "x-document-confirm": "visibility-expand",
        },
        json={
            "title": "员工手册 V2",
            "folder_id": None,
            "tags": ["制度", "HR"],
            "owner_department_id": "department_1",
            "visibility": "enterprise",
            "lifecycle_status": "active",
        },
    )

    assert response.status_code == 200
    assert seen["confirmed_visibility_expand"] is True
    assert seen["folder_id_provided"] is True
    assert seen["tags_provided"] is True
    assert seen["folder_id"] is None
    assert response.json()["data"]["visibility"] == "enterprise"


def test_document_delete_route_returns_accepted_job(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def delete_document(_self, _session, **kwargs):
        seen.update(kwargs)
        return AdminAcceptedResult(accepted=True, job_id="job_doc_1")

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.admin.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.admin.AuthService.authenticate_access_token",
        lambda _self, _session, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr("app.api.routes.admin.AdminService.delete_document", delete_document)

    client = TestClient(_create_test_app())
    response = client.delete(
        "/internal/v1/admin/documents/doc_1",
        headers={"authorization": "Bearer access.jwt", "x-document-confirm": "delete"},
    )

    assert response.status_code == 202
    assert seen["confirmed"] is True
    assert seen["doc_id"] == "doc_1"
    assert response.json()["data"] == {"accepted": True, "job_id": "job_doc_1"}


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
