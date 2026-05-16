from __future__ import annotations

import pytest
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminDocument,
    AdminFolder,
    AdminKnowledgeBase,
    AdminRole,
    AdminRoleBinding,
    AdminUser,
)
from app.modules.admin.service import (
    AdminActorContext,
    AdminService,
    RoleBindingInput,
    _is_high_risk_role,
    _merge_scopes,
)


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(
        self,
        *,
        one: _Row | None = None,
        one_or_none: _Row | None = None,
        all_rows: list[_Row] | None = None,
    ) -> None:
        self._one = one
        self._one_or_none = one_or_none
        self._all_rows = all_rows or []

    def one(self) -> _Row:
        assert self._one is not None
        return self._one

    def one_or_none(self) -> _Row | None:
        return self._one_or_none

    def all(self) -> list[_Row]:
        return self._all_rows


_ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
_ACTOR_USER_ID = "11111111-1111-1111-1111-111111111111"


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []
        self.results: list[_Result] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        if self.results:
            return self.results.pop(0)
        return _Result()


def _role(
    *,
    role_id: str = "role_1",
    code: str = "employee",
    scope_type: str = "enterprise",
    status: str = "active",
    scopes: tuple[str, ...] = ("rag:query",),
) -> AdminRole:
    return AdminRole(
        id=role_id,
        code=code,
        name=code.replace("_", " ").title(),
        scope_type=scope_type,
        is_builtin=True,
        status=status,
        scopes=scopes,
    )


def test_merge_scopes_always_keeps_session_scopes() -> None:
    scopes = _merge_scopes((_role(scopes=("config:read",)),))

    assert "auth:session" in scopes
    assert "auth:password:update:self" in scopes
    assert "config:read" in scopes


def test_system_admin_is_high_risk_role() -> None:
    assert _is_high_risk_role(_role(code="system_admin", scopes=("*",))) is True
    assert _is_high_risk_role(_role(code="audit_admin", scopes=("audit:read",))) is True
    assert _is_high_risk_role(_role(code="custom", scopes=("role:manage",))) is True
    assert _is_high_risk_role(_role(code="employee")) is False


def test_list_users_scopes_department_reader_to_shared_departments() -> None:
    session = _FakeSession()
    session.results = [
        _Result(all_rows=[]),
        _Result(one=_Row({"total": 0})),
    ]
    actor = AdminActorContext(
        user_id="11111111-1111-1111-1111-111111111111",
        scopes=("user:read",),
        department_ids=("22222222-2222-2222-2222-222222222222",),
    )

    result = AdminService().list_users(
        session,
        enterprise_id="33333333-3333-3333-3333-333333333333",
        page=1,
        page_size=20,
        actor_context=actor,
    )

    assert result.total == 0
    sql, params = session.executed[0]
    assert "user_department_memberships actor_udm" in sql
    assert params["actor_user_id"] == actor.user_id


def test_list_departments_filters_enterprise_and_status() -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "department_id": "department_1",
                        "code": "default",
                        "name": "默认部门",
                        "status": "active",
                        "is_default": True,
                    }
                )
            ]
        ),
        _Result(one=_Row({"total": 1})),
    ]

    result = AdminService().list_departments(
        session,
        enterprise_id=_ENTERPRISE_ID,
        page=1,
        page_size=20,
        keyword="默认",
        status="active",
    )

    assert result.total == 1
    assert result.items[0].is_default is True
    sql, params = session.executed[0]
    assert "enterprise_id = CAST(:enterprise_id AS uuid)" in sql
    assert "deleted_at IS NULL" in sql
    assert "(code ILIKE :keyword OR name ILIKE :keyword)" in sql
    assert "status = :status" in sql
    assert params["enterprise_id"] == _ENTERPRISE_ID
    assert params["status"] == "active"


def test_list_knowledge_bases_filters_enterprise_and_status() -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "kb_id": "kb_1",
                        "name": "制度知识库",
                        "status": "active",
                        "owner_department_id": "department_1",
                        "default_visibility": "department",
                        "config_scope_id": None,
                        "policy_version": 1,
                    }
                )
            ]
        ),
        _Result(one=_Row({"total": 1})),
    ]

    result = AdminService().list_knowledge_bases(
        session,
        enterprise_id=_ENTERPRISE_ID,
        page=1,
        page_size=20,
        keyword="制度",
        status="active",
    )

    assert result.total == 1
    assert result.items[0].name == "制度知识库"
    sql, params = session.executed[0]
    assert "FROM knowledge_bases" in sql
    assert "enterprise_id = CAST(:enterprise_id AS uuid)" in sql
    assert "deleted_at IS NULL" in sql
    assert "name ILIKE :keyword" in sql
    assert "status = :status" in sql
    assert params["enterprise_id"] == _ENTERPRISE_ID
    assert params["status"] == "active"


def test_list_knowledge_bases_scopes_resource_limited_actor() -> None:
    session = _FakeSession()
    session.results = [
        _Result(all_rows=[]),
        _Result(one=_Row({"total": 0})),
    ]
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("knowledge_base:manage",),
        department_ids=("22222222-2222-2222-2222-222222222222",),
        knowledge_base_ids=("55555555-5555-5555-5555-555555555555",),
        can_manage_all_knowledge_bases=False,
    )

    result = AdminService().list_knowledge_bases(
        session,
        enterprise_id=_ENTERPRISE_ID,
        page=1,
        page_size=20,
        actor_context=actor,
    )

    assert result.total == 0
    sql, params = session.executed[0]
    assert "owner_department_id = ANY" in sql
    assert "id = ANY" in sql
    assert params["actor_department_ids"] == ["22222222-2222-2222-2222-222222222222"]
    assert params["actor_kb_ids"] == ["55555555-5555-5555-5555-555555555555"]


def test_create_knowledge_base_requires_confirmation_for_enterprise_visibility() -> None:
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("knowledge_base:manage",),
        can_manage_all_knowledge_bases=True,
    )

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService().create_knowledge_base(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            name="制度知识库",
            owner_department_id="22222222-2222-2222-2222-222222222222",
            default_visibility="enterprise",
            confirmed_enterprise_visibility=False,
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_CONFIRMATION_REQUIRED"
    assert exc_info.value.status_code == 428


def test_create_knowledge_base_writes_policy_snapshot_and_audit(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "department_id": "22222222-2222-2222-2222-222222222222",
                        "code": "engineering",
                        "name": "研发部",
                        "status": "active",
                        "is_default": False,
                    }
                )
            ]
        ),
        _Result(),
        _Result(one=_Row({"permission_version": 7})),
        _Result(),
        _Result(),
        _Result(),
    ]
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("knowledge_base:manage",),
        can_manage_all_knowledge_bases=True,
    )

    knowledge_base = service.create_knowledge_base(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        name=" 制度知识库 ",
        owner_department_id="22222222-2222-2222-2222-222222222222",
        default_visibility="department",
        confirmed_enterprise_visibility=False,
        actor_context=actor,
    )

    assert knowledge_base.name == "制度知识库"
    assert knowledge_base.policy_version == 1
    statements = [statement for statement, _params in session.executed]
    assert any("INSERT INTO knowledge_bases" in statement for statement in statements)
    assert any("INSERT INTO resource_policies" in statement for statement in statements)
    assert any("INSERT INTO permission_snapshots" in statement for statement in statements)
    assert any("knowledge_base.created" in str(params) for _statement, params in session.executed)
    snapshot_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO permission_snapshots" in statement
    )
    assert snapshot_params["permission_version"] == 7
    assert snapshot_params["visibility"] == "department"


def test_patch_knowledge_base_requires_confirmation_when_visibility_expands(monkeypatch) -> None:
    service = AdminService()
    current = AdminKnowledgeBase(
        id="kb_1",
        name="制度知识库",
        status="active",
        owner_department_id="department_1",
        default_visibility="department",
        policy_version=2,
    )
    monkeypatch.setattr(service, "get_knowledge_base", lambda *_args, **_kwargs: current)

    with pytest.raises(AdminServiceError) as exc_info:
        service.patch_knowledge_base(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            kb_id="kb_1",
            default_visibility="enterprise",
            confirmed_visibility_expand=False,
            actor_context=AdminActorContext(
                user_id=_ACTOR_USER_ID,
                scopes=("knowledge_base:manage",),
                can_manage_all_knowledge_bases=True,
            ),
        )

    assert exc_info.value.error_code == "ADMIN_CONFIRMATION_REQUIRED"
    assert exc_info.value.details["previous_visibility"] == "department"


def test_patch_knowledge_base_visibility_writes_new_policy_and_snapshot(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = AdminKnowledgeBase(
        id="kb_1",
        name="制度知识库",
        status="active",
        owner_department_id="22222222-2222-2222-2222-222222222222",
        default_visibility="department",
        policy_version=2,
    )
    after = AdminKnowledgeBase(
        id="kb_1",
        name="制度知识库",
        status="active",
        owner_department_id="22222222-2222-2222-2222-222222222222",
        default_visibility="enterprise",
        policy_version=3,
    )
    monkeypatch.setattr(service, "get_knowledge_base", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_load_knowledge_base", lambda *_args, **_kwargs: after)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 9)
    monkeypatch.setattr(
        service,
        "_replace_resource_policy",
        lambda *_args, **_kwargs: "55555555-5555-5555-5555-555555555555",
    )
    monkeypatch.setattr(
        service,
        "_insert_permission_snapshot",
        lambda *_args, **_kwargs: {"snapshot_id": "snapshot_1", "payload_hash": "hash_1"},
    )
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.patch_knowledge_base(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        kb_id="kb_1",
        default_visibility="enterprise",
        confirmed_visibility_expand=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("knowledge_base:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.default_visibility == "enterprise"
    update_params = next(
        params for statement, params in session.executed if "UPDATE knowledge_bases" in statement
    )
    assert update_params["policy_version"] == 3
    assert audits[0]["event_name"] == "knowledge_base.updated"
    assert audits[0]["summary"]["permission_snapshot_id"] == "snapshot_1"


def test_delete_knowledge_base_blocks_access_and_enqueues_cleanup(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = AdminKnowledgeBase(
        id="kb_1",
        name="制度知识库",
        status="active",
        owner_department_id="department_1",
        default_visibility="department",
        policy_version=1,
    )
    monkeypatch.setattr(service, "get_knowledge_base", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_insert_access_block", lambda *_args, **_kwargs: "block_1")
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 11)
    monkeypatch.setattr(service, "_enqueue_index_delete_job", lambda *_args, **_kwargs: "job_1")
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.delete_knowledge_base(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        kb_id="kb_1",
        confirmed=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("knowledge_base:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.accepted is True
    assert result.job_id == "job_1"
    assert any("UPDATE knowledge_bases" in statement for statement, _params in session.executed)
    assert any("UPDATE resource_policies" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "knowledge_base.deleted"
    assert audits[0]["summary"]["access_block_id"] == "block_1"


def test_list_folders_requires_folder_manage_scope(monkeypatch) -> None:
    service = AdminService()
    monkeypatch.setattr(
        service,
        "get_knowledge_base",
        lambda *_args, **_kwargs: AdminKnowledgeBase(
            id="kb_1",
            name="制度知识库",
            status="active",
            owner_department_id="department_1",
            default_visibility="department",
        ),
    )
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("knowledge_base:manage",),
        can_manage_all_knowledge_bases=True,
    )

    with pytest.raises(AdminServiceError) as exc_info:
        service.list_folders(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            kb_id="kb_1",
            page=1,
            page_size=20,
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scope"] == "folder:manage"


def test_list_folders_filters_by_knowledge_base(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "folder_id": "folder_1",
                        "kb_id": "kb_1",
                        "parent_id": None,
                        "name": "制度",
                        "path": "/folder_1",
                        "status": "active",
                    }
                )
            ]
        ),
        _Result(one=_Row({"total": 1})),
    ]
    monkeypatch.setattr(
        service,
        "get_knowledge_base",
        lambda *_args, **_kwargs: AdminKnowledgeBase(
            id="kb_1",
            name="制度知识库",
            status="active",
            owner_department_id="department_1",
            default_visibility="department",
        ),
    )

    result = service.list_folders(
        session,
        enterprise_id=_ENTERPRISE_ID,
        kb_id="kb_1",
        page=1,
        page_size=20,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("folder:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.total == 1
    assert result.items[0].name == "制度"
    sql, params = session.executed[0]
    assert "FROM folders" in sql
    assert "kb_id = CAST(:kb_id AS uuid)" in sql
    assert params["kb_id"] == "kb_1"


def test_create_folder_writes_audit(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    monkeypatch.setattr(
        service,
        "get_knowledge_base",
        lambda *_args, **_kwargs: AdminKnowledgeBase(
            id="kb_1",
            name="制度知识库",
            status="active",
            owner_department_id="department_1",
            default_visibility="department",
        ),
    )
    monkeypatch.setattr(service, "_resolve_parent_folder", lambda *_args, **_kwargs: None)
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    folder = service.create_folder(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        kb_id="kb_1",
        name=" 制度 ",
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("folder:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert folder.name == "制度"
    assert any("INSERT INTO folders" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "folder.created"
    assert audits[0]["summary"]["kb_id"] == "kb_1"


def test_patch_folder_rejects_moving_into_descendant(monkeypatch) -> None:
    service = AdminService()
    current = AdminFolder(
        id="folder_parent",
        kb_id="kb_1",
        parent_id=None,
        name="父文件夹",
        status="active",
        path="/folder_parent",
    )
    child = AdminFolder(
        id="folder_child",
        kb_id="kb_1",
        parent_id="folder_parent",
        name="子文件夹",
        status="active",
        path="/folder_parent/folder_child",
    )
    monkeypatch.setattr(service, "get_folder", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_resolve_parent_folder", lambda *_args, **_kwargs: child)

    with pytest.raises(AdminServiceError) as exc_info:
        service.patch_folder(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            folder_id="folder_parent",
            parent_id="folder_child",
            actor_context=AdminActorContext(
                user_id=_ACTOR_USER_ID,
                scopes=("folder:manage",),
                can_manage_all_knowledge_bases=True,
            ),
            parent_id_provided=True,
        )

    assert exc_info.value.error_code == "ADMIN_FOLDER_PARENT_INVALID"


def test_delete_folder_blocks_access_and_enqueues_cleanup(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = AdminFolder(
        id="folder_1",
        kb_id="kb_1",
        parent_id=None,
        name="制度",
        status="active",
        path="/folder_1",
    )
    monkeypatch.setattr(service, "get_folder", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_count_folder_documents", lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(service, "_insert_access_block", lambda *_args, **_kwargs: "block_1")
    monkeypatch.setattr(service, "_enqueue_index_delete_job", lambda *_args, **_kwargs: "job_1")
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.delete_folder(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        folder_id="folder_1",
        confirmed=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("folder:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.accepted is True
    assert result.job_id == "job_1"
    assert any("UPDATE folders" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "folder.deleted"
    assert audits[0]["summary"]["document_impact_count"] == 3


def _document(
    *,
    visibility: str = "department",
    owner_department_id: str = "22222222-2222-2222-2222-222222222222",
    lifecycle_status: str = "active",
    policy_version: int = 1,
) -> AdminDocument:
    return AdminDocument(
        id="44444444-4444-4444-4444-444444444444",
        kb_id="55555555-5555-5555-5555-555555555555",
        folder_id="66666666-6666-6666-6666-666666666666",
        title="员工手册",
        lifecycle_status=lifecycle_status,
        index_status="indexed",
        owner_department_id=owner_department_id,
        visibility=visibility,
        current_version_id="77777777-7777-7777-7777-777777777777",
        tags=("制度",),
        permission_snapshot_id="88888888-8888-8888-8888-888888888888",
        content_hash="hash_1",
        policy_version=policy_version,
    )


def test_list_documents_requires_document_manage_scope(monkeypatch) -> None:
    service = AdminService()
    monkeypatch.setattr(
        service,
        "get_knowledge_base",
        lambda *_args, **_kwargs: AdminKnowledgeBase(
            id="kb_1",
            name="制度知识库",
            status="active",
            owner_department_id="department_1",
            default_visibility="department",
        ),
    )
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("document:read",),
        can_manage_all_knowledge_bases=True,
    )

    with pytest.raises(AdminServiceError) as exc_info:
        service.list_documents(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            kb_id="kb_1",
            page=1,
            page_size=20,
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scope"] == "document:manage"


def test_list_documents_filters_by_knowledge_base_and_status(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "doc_id": "doc_1",
                        "kb_id": "kb_1",
                        "folder_id": "folder_1",
                        "title": "员工手册",
                        "lifecycle_status": "active",
                        "index_status": "indexed",
                        "owner_department_id": "department_1",
                        "visibility": "department",
                        "current_version_id": "version_1",
                        "tags": ["制度"],
                        "permission_snapshot_id": "snapshot_1",
                        "content_hash": "hash_1",
                        "policy_version": 1,
                    }
                )
            ]
        ),
        _Result(one=_Row({"total": 1})),
    ]
    monkeypatch.setattr(
        service,
        "get_knowledge_base",
        lambda *_args, **_kwargs: AdminKnowledgeBase(
            id="kb_1",
            name="制度知识库",
            status="active",
            owner_department_id="department_1",
            default_visibility="department",
        ),
    )

    result = service.list_documents(
        session,
        enterprise_id=_ENTERPRISE_ID,
        kb_id="kb_1",
        page=1,
        page_size=20,
        lifecycle_status="active",
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("document:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.total == 1
    assert result.items[0].title == "员工手册"
    sql, params = session.executed[0]
    assert "FROM documents d" in sql
    assert "d.kb_id = CAST(:kb_id AS uuid)" in sql
    assert "d.lifecycle_status = :lifecycle_status" in sql
    assert params["kb_id"] == "kb_1"


def test_list_document_versions_requires_document_manage_scope() -> None:
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("document:read",),
        can_manage_all_knowledge_bases=True,
    )

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService().list_document_versions(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            doc_id="44444444-4444-4444-4444-444444444444",
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scope"] == "document:manage"


def test_list_document_versions_filters_by_document(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "version_id": "77777777-7777-7777-7777-777777777777",
                        "document_id": "44444444-4444-4444-4444-444444444444",
                        "version_no": 2,
                        "status": "active",
                    }
                )
            ]
        )
    ]
    monkeypatch.setattr(service, "get_document", lambda *_args, **_kwargs: _document())

    versions = service.list_document_versions(
        session,
        enterprise_id=_ENTERPRISE_ID,
        doc_id="44444444-4444-4444-4444-444444444444",
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("document:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert versions[0].version_no == 2
    sql, params = session.executed[0]
    assert "FROM document_versions" in sql
    assert params["doc_id"] == "44444444-4444-4444-4444-444444444444"


def test_list_document_chunks_filters_by_document(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "chunk_id": "chunk_1",
                        "document_id": "44444444-4444-4444-4444-444444444444",
                        "document_version_id": "77777777-7777-7777-7777-777777777777",
                        "text_preview": "制度正文",
                        "page_start": 1,
                        "page_end": 2,
                        "status": "active",
                    }
                )
            ]
        )
    ]
    monkeypatch.setattr(service, "get_document", lambda *_args, **_kwargs: _document())

    chunks = service.list_document_chunks(
        session,
        enterprise_id=_ENTERPRISE_ID,
        doc_id="44444444-4444-4444-4444-444444444444",
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("document:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert chunks[0].text_preview == "制度正文"
    sql, params = session.executed[0]
    assert "FROM chunks" in sql
    assert params["doc_id"] == "44444444-4444-4444-4444-444444444444"


def test_replace_document_permissions_requires_permission_manage_scope() -> None:
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("document:manage",),
        can_manage_all_knowledge_bases=True,
    )

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService().replace_document_permissions(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            doc_id="44444444-4444-4444-4444-444444444444",
            visibility="department",
            owner_department_id=None,
            confirmed=True,
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scope"] == "permission:manage"


def test_replace_document_permissions_delegates_to_document_patch(monkeypatch) -> None:
    service = AdminService()
    seen: dict[str, object] = {}

    def patch_document(_session, **kwargs):
        seen.update(kwargs)
        return _document(visibility="enterprise", policy_version=4)

    monkeypatch.setattr(service, "patch_document", patch_document)
    monkeypatch.setattr(service, "_load_resource_permission_version", lambda *_args, **_kwargs: 18)

    policy = service.replace_document_permissions(
        _FakeSession(),
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        doc_id="44444444-4444-4444-4444-444444444444",
        visibility="enterprise",
        owner_department_id="22222222-2222-2222-2222-222222222222",
        confirmed=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("permission:manage",),
            can_manage_all_knowledge_bases=False,
        ),
    )

    assert policy.resource_type == "document"
    assert policy.visibility == "enterprise"
    assert policy.permission_version == 18
    assert seen["confirmed_visibility_expand"] is True
    assert "document:manage" in seen["actor_context"].scopes


def test_replace_knowledge_base_permissions_writes_snapshot_and_audit(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = AdminKnowledgeBase(
        id="55555555-5555-5555-5555-555555555555",
        name="制度知识库",
        status="active",
        owner_department_id="22222222-2222-2222-2222-222222222222",
        default_visibility="department",
        policy_version=3,
    )
    monkeypatch.setattr(service, "_load_knowledge_base", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 19)
    monkeypatch.setattr(
        service,
        "_replace_resource_policy",
        lambda *_args, **_kwargs: "99999999-9999-9999-9999-999999999999",
    )
    monkeypatch.setattr(
        service,
        "_insert_permission_snapshot",
        lambda *_args, **_kwargs: {"snapshot_id": "snapshot_1", "payload_hash": "hash_1"},
    )
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    policy = service.replace_knowledge_base_permissions(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        kb_id=current.id,
        visibility="enterprise",
        owner_department_id=None,
        confirmed=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("permission:manage",),
            can_manage_all_knowledge_bases=False,
        ),
    )

    assert policy.resource_type == "knowledge_base"
    assert policy.permission_version == 19
    assert any("UPDATE knowledge_bases" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "knowledge_base.permission_replaced"


def test_patch_document_requires_confirmation_when_visibility_expands(monkeypatch) -> None:
    service = AdminService()
    current = _document(visibility="department", policy_version=3)
    monkeypatch.setattr(service, "get_document", lambda *_args, **_kwargs: current)

    with pytest.raises(AdminServiceError) as exc_info:
        service.patch_document(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            doc_id=current.id,
            visibility="enterprise",
            confirmed_visibility_expand=False,
            actor_context=AdminActorContext(
                user_id=_ACTOR_USER_ID,
                scopes=("document:manage",),
                can_manage_all_knowledge_bases=True,
            ),
        )

    assert exc_info.value.error_code == "ADMIN_CONFIRMATION_REQUIRED"
    assert exc_info.value.details["previous_visibility"] == "department"


def test_patch_document_permission_change_writes_snapshot_and_refresh_job(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = _document(visibility="department", policy_version=3)
    after = _document(visibility="enterprise", policy_version=4)
    monkeypatch.setattr(service, "get_document", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_load_document", lambda *_args, **_kwargs: after)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 12)
    monkeypatch.setattr(
        service,
        "_replace_resource_policy",
        lambda *_args, **_kwargs: "99999999-9999-9999-9999-999999999999",
    )
    monkeypatch.setattr(
        service,
        "_insert_permission_snapshot",
        lambda *_args, **_kwargs: {
            "snapshot_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "payload_hash": "hash_2",
        },
    )
    monkeypatch.setattr(
        service,
        "_enqueue_permission_refresh_job",
        lambda *_args, **_kwargs: "job_1",
    )
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.patch_document(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        doc_id=current.id,
        title=" 员工手册 V2 ",
        folder_id=None,
        folder_id_provided=True,
        tags=["制度", "制度", "HR"],
        tags_provided=True,
        visibility="enterprise",
        confirmed_visibility_expand=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("document:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.visibility == "enterprise"
    update_params = next(
        params for statement, params in session.executed if "UPDATE documents" in statement
    )
    assert update_params["title"] == "员工手册 V2"
    assert update_params["folder_id"] is None
    assert update_params["tags"] == ["制度", "HR"]
    assert update_params["permission_snapshot_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert audits[0]["event_name"] == "document.visibility_expanded"
    assert audits[0]["summary"]["refresh_job_id"] == "job_1"


def test_patch_document_tightening_inserts_access_block(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = _document(visibility="enterprise", policy_version=2)
    after = _document(visibility="department", policy_version=3)
    monkeypatch.setattr(service, "get_document", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_load_document", lambda *_args, **_kwargs: after)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 13)
    monkeypatch.setattr(
        service,
        "_replace_resource_policy",
        lambda *_args, **_kwargs: "99999999-9999-9999-9999-999999999999",
    )
    monkeypatch.setattr(
        service,
        "_insert_permission_snapshot",
        lambda *_args, **_kwargs: {
            "snapshot_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "payload_hash": "hash_2",
        },
    )
    blocks: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_access_block",
        lambda _session, **kwargs: blocks.append(kwargs) or "block_1",
    )
    monkeypatch.setattr(
        service,
        "_enqueue_permission_refresh_job",
        lambda *_args, **_kwargs: "job_1",
    )
    monkeypatch.setattr(service, "_insert_audit_log", lambda *_args, **_kwargs: None)

    service.patch_document(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        doc_id=current.id,
        visibility="department",
        confirmed_visibility_expand=False,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("document:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert blocks[0]["resource_type"] == "document"
    assert blocks[0]["reason"] == "permission_tightened"
    assert blocks[0]["block_level"] == "query"


def test_delete_document_blocks_access_and_enqueues_cleanup(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = _document()
    monkeypatch.setattr(service, "get_document", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_insert_access_block", lambda *_args, **_kwargs: "block_1")
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 14)
    monkeypatch.setattr(service, "_enqueue_index_delete_job", lambda *_args, **_kwargs: "job_1")
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.delete_document(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        doc_id=current.id,
        confirmed=True,
        actor_context=AdminActorContext(
            user_id=_ACTOR_USER_ID,
            scopes=("document:manage",),
            can_manage_all_knowledge_bases=True,
        ),
    )

    assert result.accepted is True
    assert result.job_id == "job_1"
    assert any("UPDATE documents" in statement for statement, _params in session.executed)
    assert any("UPDATE resource_policies" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "document.deleted"
    assert audits[0]["summary"]["access_block_id"] == "block_1"


def test_create_department_requires_org_manage_scope() -> None:
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("org:read",),
        department_ids=(),
    )

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService().create_department(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            code="engineering",
            name="研发部",
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scope"] == "org:manage"


def test_create_department_bumps_versions_and_audits() -> None:
    session = _FakeSession()
    session.results = [
        _Result(one=_Row({"org_version": 4})),
        _Result(),
        _Result(one=_Row({"permission_version": 7})),
    ]
    actor = AdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=("org:manage",),
        department_ids=(),
    )

    department = AdminService().create_department(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        code="engineering",
        name="研发部",
        actor_context=actor,
    )

    assert department.code == "engineering"
    assert department.is_default is False
    sql_statements = [statement for statement, _params in session.executed]
    assert any("SET org_version = org_version + 1" in statement for statement in sql_statements)
    assert any("INSERT INTO departments" in statement for statement in sql_statements)
    assert any(
        "SET permission_version = permission_version + 1" in statement
        for statement in sql_statements
    )
    assert any("department.created" in str(params) for _statement, params in session.executed)
    insert_params = next(
        params for statement, params in session.executed if "INSERT INTO departments" in statement
    )
    assert insert_params["org_version"] == 4
    assert insert_params["code"] == "engineering"


def test_patch_department_bumps_versions_and_audits(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    current = AdminDepartment(
        id="department_2",
        code="engineering",
        name="研发部",
        status="active",
        is_default=False,
        org_version=3,
    )
    after = AdminDepartment(
        id="department_2",
        code="engineering",
        name="研发平台部",
        status="active",
        is_default=False,
        org_version=4,
    )
    reads = iter([current, after])
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(service, "get_department", lambda *_args, **_kwargs: next(reads))
    monkeypatch.setattr(service, "_bump_org_version", lambda *_args: 4)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 8)
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.patch_department(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        department_id="department_2",
        name="研发平台部",
        actor_context=AdminActorContext(user_id=_ACTOR_USER_ID, scopes=("org:manage",)),
    )

    assert result.name == "研发平台部"
    assert any("UPDATE departments" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "department.updated"
    assert audits[0]["summary"]["changed_fields"] == ["name"]
    assert audits[0]["summary"]["permission_version"] == 8


def test_delete_department_rejects_active_members(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    session.results = [_Result(one=_Row({"active_members": 1}))]
    monkeypatch.setattr(
        service,
        "get_department",
        lambda *_args, **_kwargs: AdminDepartment(
            id="department_2",
            code="engineering",
            name="研发部",
            status="active",
            is_default=False,
        ),
    )

    with pytest.raises(AdminServiceError) as exc_info:
        service.delete_department(
            session,
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            department_id="department_2",
            confirmed=True,
            actor_context=AdminActorContext(user_id=_ACTOR_USER_ID, scopes=("org:manage",)),
        )

    assert exc_info.value.error_code == "ADMIN_DEPARTMENT_HAS_ACTIVE_MEMBERS"


def test_replace_user_departments_requires_at_least_one_department() -> None:
    actor = AdminActorContext(user_id=_ACTOR_USER_ID, scopes=("*",))

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService().replace_user_departments(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            user_id="44444444-4444-4444-4444-444444444444",
            department_ids=[],
            confirmed_remove_primary=False,
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_USER_DEPARTMENTS_INVALID"


def test_replace_user_departments_requires_confirmation_when_primary_changes(monkeypatch) -> None:
    service = AdminService()
    before = [
        AdminDepartment(
            id="department_old",
            code="sales",
            name="销售部",
            status="active",
            is_primary=True,
        )
    ]
    next_departments = [
        AdminDepartment(
            id="department_new",
            code="engineering",
            name="研发部",
            status="active",
        )
    ]
    monkeypatch.setattr(service, "_load_user_row", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_load_user_departments", lambda *_args, **_kwargs: tuple(before))
    monkeypatch.setattr(service, "_resolve_departments", lambda *_args, **_kwargs: next_departments)

    with pytest.raises(AdminServiceError) as exc_info:
        service.replace_user_departments(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            user_id="44444444-4444-4444-4444-444444444444",
            department_ids=["department_new"],
            confirmed_remove_primary=False,
            actor_context=AdminActorContext(user_id=_ACTOR_USER_ID, scopes=("*",)),
        )

    assert exc_info.value.error_code == "ADMIN_CONFIRMATION_REQUIRED"
    assert exc_info.value.status_code == 428


def test_replace_user_departments_bumps_versions_and_audits(monkeypatch) -> None:
    service = AdminService()
    session = _FakeSession()
    before = [
        AdminDepartment(
            id="department_old",
            code="sales",
            name="销售部",
            status="active",
            is_primary=True,
        )
    ]
    next_departments = [
        AdminDepartment(
            id="department_new",
            code="engineering",
            name="研发部",
            status="active",
        )
    ]
    after = [
        AdminDepartment(
            id="department_new",
            code="engineering",
            name="研发部",
            status="active",
            is_primary=True,
        )
    ]
    reads = iter([tuple(before), tuple(after)])
    inserted: list[tuple[str, bool]] = []
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(service, "_load_user_row", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_load_user_departments", lambda *_args, **_kwargs: next(reads))
    monkeypatch.setattr(service, "_resolve_departments", lambda *_args, **_kwargs: next_departments)
    monkeypatch.setattr(service, "_bump_org_version", lambda *_args: 5)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 9)
    monkeypatch.setattr(
        service,
        "_insert_department_membership",
        lambda _session, **kwargs: inserted.append(
            (kwargs["department_id"], kwargs["is_primary"])
        ),
    )
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    result = service.replace_user_departments(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        user_id="44444444-4444-4444-4444-444444444444",
        department_ids=["department_new"],
        confirmed_remove_primary=True,
        actor_context=AdminActorContext(user_id=_ACTOR_USER_ID, scopes=("*",)),
    )

    assert result == after
    assert inserted == [("department_new", True)]
    assert any(
        "UPDATE user_department_memberships" in statement
        for statement, _params in session.executed
    )
    assert audits[0]["event_name"] == "membership.replaced"
    assert audits[0]["summary"]["org_version"] == 5
    assert audits[0]["summary"]["permission_version"] == 9


def test_create_role_binding_requires_confirmation_for_high_risk_role(monkeypatch) -> None:
    service = AdminService()
    monkeypatch.setattr(service, "_load_user_row", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        service,
        "_load_role",
        lambda *_args, **_kwargs: _role(code="system_admin", scopes=("*",)),
    )

    with pytest.raises(AdminServiceError) as exc_info:
        service.create_role_bindings(
            _FakeSession(),
            enterprise_id="ent_1",
            actor_user_id="actor_1",
            user_id="user_1",
            bindings=[RoleBindingInput(role_id="role_admin", scope_type="enterprise")],
            confirmed_high_risk=False,
        )

    assert exc_info.value.error_code == "ADMIN_CONFIRMATION_REQUIRED"
    assert exc_info.value.status_code == 428


def test_role_binding_write_requires_user_manage_and_role_manage_scope() -> None:
    actor = AdminActorContext(
        user_id="user_1",
        scopes=("role:manage",),
        department_ids=(),
    )

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService().create_role_bindings(
            _FakeSession(),
            enterprise_id="ent_1",
            actor_user_id="actor_1",
            user_id="user_2",
            bindings=[RoleBindingInput(role_id="role_employee", scope_type="enterprise")],
            confirmed_high_risk=False,
            actor_context=actor,
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scopes"] == ["user:manage"]


def test_insert_role_binding_rejects_scope_mismatch_before_database_write() -> None:
    session = _FakeSession()
    service = AdminService()

    with pytest.raises(AdminServiceError) as exc_info:
        service._insert_role_binding(
            session,
            enterprise_id="ent_1",
            user_id="user_1",
            role=_role(scope_type="department"),
            scope_type="enterprise",
            scope_id=None,
            actor_user_id="actor_1",
        )

    assert exc_info.value.error_code == "ADMIN_ROLE_SCOPE_MISMATCH"
    assert session.executed == []


def test_insert_role_binding_rejects_inactive_role_before_database_write() -> None:
    session = _FakeSession()
    service = AdminService()

    with pytest.raises(AdminServiceError) as exc_info:
        service._insert_role_binding(
            session,
            enterprise_id="ent_1",
            user_id="user_1",
            role=_role(code="employee", status="disabled", scopes=("rag:query",)),
            scope_type="enterprise",
            scope_id=None,
            actor_user_id="actor_1",
        )

    assert exc_info.value.error_code == "ADMIN_ROLE_INACTIVE"
    assert session.executed == []


def test_disabled_user_bumps_permission_version_and_audits(monkeypatch) -> None:
    service = AdminService()
    audits: list[dict[str, object]] = []
    bumps: list[str] = []
    current = AdminUser(
        id="user_2",
        username="alice",
        name="Alice",
        status="active",
        enterprise_id="ent_1",
        roles=(_role(),),
    )
    monkeypatch.setattr(service, "get_user", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_revoke_user_tokens", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: bumps.append("x") or 7)
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    service.patch_user(
        _FakeSession(),
        enterprise_id="ent_1",
        actor_user_id="actor_1",
        user_id="user_2",
        status="disabled",
    )

    assert bumps == ["x"]
    assert audits[0]["event_name"] == "user.disabled"
    assert audits[0]["summary"]["permission_version"] == 7


def test_last_system_admin_cannot_be_removed_even_with_confirmation() -> None:
    session = _FakeSession()
    session.results = [
        _Result(one=_Row({"admin_count": 1})),
        _Result(one_or_none=_Row({"exists": 1})),
    ]

    with pytest.raises(AdminServiceError) as exc_info:
        AdminService()._ensure_not_last_system_admin(
            session,
            enterprise_id="ent_1",
            user_id="user_1",
            confirmed=True,
        )

    assert exc_info.value.error_code == "ADMIN_LAST_SYSTEM_ADMIN"


def test_replace_role_bindings_writes_one_replace_audit(monkeypatch) -> None:
    service = AdminService()
    audits: list[dict[str, object]] = []
    inserted: list[RoleBindingInput] = []
    bump_calls: list[str] = []
    before = [
        AdminRoleBinding(
            id="binding_old",
            role_id="role_employee",
            subject_type="user",
            subject_id="user_1",
            scope_type="enterprise",
            scope_id=None,
            role_code="employee",
            role_name="Employee",
        )
    ]
    after = [
        AdminRoleBinding(
            id="binding_new",
            role_id="role_audit",
            subject_type="user",
            subject_id="user_1",
            scope_type="enterprise",
            scope_id=None,
            role_code="audit_admin",
            role_name="Audit Admin",
        )
    ]
    binding_reads = iter([before, after])

    monkeypatch.setattr(service, "_load_user_row", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        service,
        "_load_role_bindings",
        lambda *_args, **_kwargs: next(binding_reads),
    )
    monkeypatch.setattr(service, "_load_role", lambda *_args, **_kwargs: _role(code="audit_admin"))

    def insert_binding(_session, **kwargs):
        inserted.append(
            RoleBindingInput(
                role_id=kwargs["role"].id,
                scope_type=kwargs["scope_type"],
                scope_id=kwargs["scope_id"],
            )
        )
        return after[0]

    monkeypatch.setattr(service, "_insert_role_binding", insert_binding)
    monkeypatch.setattr(
        service,
        "_bump_permission_version",
        lambda *_args: bump_calls.append("x") or 3,
    )
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )
    monkeypatch.setattr(
        service,
        "create_role_bindings",
        lambda *_args, **_kwargs: pytest.fail("replace must not emit create audit"),
    )

    result = service.replace_role_bindings(
        _FakeSession(),
        enterprise_id="ent_1",
        actor_user_id="actor_1",
        user_id="user_1",
        bindings=[RoleBindingInput(role_id="role_audit", scope_type="enterprise")],
        confirmed=True,
    )

    assert result == after
    assert len(inserted) == 1
    assert bump_calls == ["x"]
    assert [audit["event_name"] for audit in audits] == ["role_binding.replaced"]
