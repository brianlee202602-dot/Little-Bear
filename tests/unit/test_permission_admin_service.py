from __future__ import annotations

import pytest
from app.modules.permissions.admin_schemas import (
    PermissionAdminActorContext,
    PermissionDepartment,
    PermissionDocument,
    PermissionKnowledgeBase,
    PermissionKnowledgeBaseAccessRule,
)
from app.modules.permissions.admin_service import PermissionAdminService
from app.modules.permissions.errors import PermissionServiceError


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


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        return _Result()


_ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
_ACTOR_USER_ID = "11111111-1111-1111-1111-111111111111"
_DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"
_KB_ID = "55555555-5555-5555-5555-555555555555"
_DOC_ID = "44444444-4444-4444-4444-444444444444"


def _actor(*, scopes: tuple[str, ...]) -> PermissionAdminActorContext:
    return PermissionAdminActorContext(
        user_id=_ACTOR_USER_ID,
        scopes=scopes,
        can_manage_all_knowledge_bases=True,
    )


def _department() -> PermissionDepartment:
    return PermissionDepartment(
        id=_DEPARTMENT_ID,
        code="engineering",
        name="研发部",
        status="active",
    )


def _knowledge_base() -> PermissionKnowledgeBase:
    return PermissionKnowledgeBase(
        id=_KB_ID,
        name="制度知识库",
        status="active",
        owner_department_id=_DEPARTMENT_ID,
        kb_visibility="department_acl",
        default_document_visibility="department",
        default_document_owner_department_id=_DEPARTMENT_ID,
        access_rules=(
            PermissionKnowledgeBaseAccessRule(
                subject_type="department",
                subject_id=_DEPARTMENT_ID,
                permission="query",
            ),
        ),
        policy_version=3,
    )


def _document() -> PermissionDocument:
    return PermissionDocument(
        id=_DOC_ID,
        kb_id=_KB_ID,
        title="员工手册",
        lifecycle_status="active",
        index_status="indexed",
        owner_department_id=_DEPARTMENT_ID,
        visibility="department",
        policy_version=3,
    )


def test_replace_document_permissions_requires_permission_manage_scope() -> None:
    with pytest.raises(PermissionServiceError) as exc_info:
        PermissionAdminService().replace_document_permissions(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            actor_user_id=_ACTOR_USER_ID,
            doc_id=_DOC_ID,
            visibility="department",
            owner_department_id=None,
            confirmed=True,
            actor_context=_actor(scopes=("document:manage",)),
        )

    assert exc_info.value.error_code == "ADMIN_SCOPE_REQUIRED"
    assert exc_info.value.details["required_scope"] == "permission:manage"


def test_replace_knowledge_base_permissions_writes_snapshot_and_audit(monkeypatch) -> None:
    service = PermissionAdminService()
    session = _FakeSession()
    current = _knowledge_base()
    monkeypatch.setattr(service, "_load_knowledge_base", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(service, "_resolve_department", lambda *_args, **_kwargs: _department())
    monkeypatch.setattr(service.resource_writer, "bump_permission_version", lambda *_args: 19)
    monkeypatch.setattr(
        service.resource_writer,
        "replace_resource_policy",
        lambda *_args, **_kwargs: "99999999-9999-9999-9999-999999999999",
    )
    monkeypatch.setattr(
        service.resource_writer,
        "insert_permission_snapshot",
        lambda *_args, **_kwargs: {"snapshot_id": "snapshot_1", "payload_hash": "hash_1"},
    )
    monkeypatch.setattr(
        service.refresh_job_writer,
        "enqueue_permission_refresh_job",
        lambda *_args, **_kwargs: "job_1",
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
        kb_visibility="enterprise",
        default_document_visibility="department",
        default_document_owner_department_id=_DEPARTMENT_ID,
        access_rules=[],
        confirmed=True,
        actor_context=_actor(scopes=("permission:manage",)),
    )

    assert policy.resource_type == "knowledge_base"
    assert policy.permission_version == 19
    assert any("UPDATE knowledge_bases" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "knowledge_base.permission_replaced"


def test_replace_document_permissions_writes_snapshot_and_refresh_job(monkeypatch) -> None:
    service = PermissionAdminService()
    session = _FakeSession()
    monkeypatch.setattr(service, "_load_document", lambda *_args, **_kwargs: _document())
    monkeypatch.setattr(
        service,
        "_load_knowledge_base",
        lambda *_args, **_kwargs: _knowledge_base(),
    )
    monkeypatch.setattr(service, "_resolve_department", lambda *_args, **_kwargs: _department())
    monkeypatch.setattr(service.resource_writer, "bump_permission_version", lambda *_args: 23)
    monkeypatch.setattr(
        service.resource_writer,
        "replace_resource_policy",
        lambda *_args, **_kwargs: "99999999-9999-9999-9999-999999999999",
    )
    monkeypatch.setattr(
        service.resource_writer,
        "insert_permission_snapshot",
        lambda *_args, **_kwargs: {"snapshot_id": "snapshot_2", "payload_hash": "hash_2"},
    )
    monkeypatch.setattr(
        service.refresh_job_writer,
        "enqueue_permission_refresh_job",
        lambda *_args, **_kwargs: "job_2",
    )
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    policy = service.replace_document_permissions(
        session,
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_ACTOR_USER_ID,
        doc_id=_DOC_ID,
        visibility="enterprise",
        owner_department_id=_DEPARTMENT_ID,
        confirmed=True,
        actor_context=_actor(scopes=("permission:manage",)),
    )

    assert policy.resource_type == "document"
    assert policy.visibility == "enterprise"
    assert policy.permission_version == 23
    assert any("UPDATE documents" in statement for statement, _params in session.executed)
    assert audits[0]["event_name"] == "document.visibility_expanded"
