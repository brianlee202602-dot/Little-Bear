from __future__ import annotations

import pytest
from app.modules.permissions import (
    CandidateMetadata,
    PermissionService,
    PermissionServiceError,
)


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(
        self,
        *,
        one_or_none: _Row | None = None,
        all_rows: list[_Row] | None = None,
    ) -> None:
        self._one_or_none = one_or_none
        self._all_rows = all_rows or []

    def one_or_none(self) -> _Row | None:
        return self._one_or_none

    def all(self) -> list[_Row]:
        return self._all_rows


class _FakeSession:
    def __init__(self, results: list[_Result]) -> None:
        self.results = results
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        assert self.results
        return self.results.pop(0)


ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"
OTHER_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"


def test_build_context_loads_departments_roles_versions_and_filter_hash() -> None:
    session = _FakeSession(
        [
            _Result(
                one_or_none=_Row(
                    {
                        "user_id": USER_ID,
                        "enterprise_id": ENTERPRISE_ID,
                        "username": "alice",
                        "status": "active",
                    }
                )
            ),
            _Result(one_or_none=_Row({"org_version": 7, "permission_version": 42})),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "department_id": DEPARTMENT_ID,
                            "code": "sales",
                            "name": "销售部",
                            "is_primary": True,
                        }
                    )
                ]
            ),
            _Result(
                all_rows=[
                    _Row(
                        {
                            "role_id": "role_employee",
                            "code": "employee",
                            "name": "Employee",
                            "scope_type": "enterprise",
                            "scope_id": None,
                            "scopes": ["rag:query", "document:read"],
                        }
                    )
                ]
            ),
        ]
    )

    context = PermissionService().build_context(
        session,
        user_id=USER_ID,
        enterprise_id=ENTERPRISE_ID,
        request_id="req_permission",
    )

    assert context.enterprise_id == ENTERPRISE_ID
    assert context.user_id == USER_ID
    assert context.department_ids == (DEPARTMENT_ID,)
    assert context.permission_version == 42
    assert context.org_version == 7
    assert context.has_scope("rag:query") is True
    assert context.has_scope("auth:session") is True
    assert context.permission_filter_hash
    assert session.executed[0][1]["enterprise_id"] == ENTERPRISE_ID


def test_build_filter_generates_qdrant_and_sql_permission_conditions() -> None:
    context = _permission_context()

    permission_filter = PermissionService().build_filter(
        context,
        kb_ids=["55555555-5555-5555-5555-555555555555"],
        active_index_version_ids=["66666666-6666-6666-6666-666666666666"],
        required_scope="rag:query",
    )

    assert permission_filter.params["enterprise_id"] == ENTERPRISE_ID
    assert permission_filter.params["department_ids"] == [DEPARTMENT_ID]
    assert "kie.visibility_state = 'active'" in permission_filter.keyword_where_sql
    assert "d.lifecycle_status = 'active'" in permission_filter.keyword_where_sql
    assert "kie.indexed_permission_version >= :permission_version" not in (
        permission_filter.keyword_where_sql
    )
    assert "owner_department_id = ANY" in permission_filter.keyword_where_sql
    assert "ab.resource_type = 'knowledge_base'" in permission_filter.keyword_where_sql
    assert "ab.resource_type = 'folder'" in permission_filter.keyword_where_sql
    assert permission_filter.qdrant_filter["must"][0] == {
        "key": "enterprise_id",
        "match": {"value": ENTERPRISE_ID},
    }
    assert {
        "key": "index_version_id",
        "match": {"any": ["66666666-6666-6666-6666-666666666666"]},
    } in permission_filter.qdrant_filter["must"]


def test_build_filter_fail_closed_on_stale_index_adds_permission_version_guards() -> None:
    context = _permission_context(permission_version=43)

    permission_filter = PermissionService().build_filter(
        context,
        kb_ids=["55555555-5555-5555-5555-555555555555"],
        active_index_version_ids=["66666666-6666-6666-6666-666666666666"],
        required_scope="rag:query",
        fail_closed_on_stale_index=True,
    )

    assert permission_filter.params["permission_version"] == 43
    assert {"key": "permission_version", "range": {"gte": 43}} in (
        permission_filter.qdrant_filter["must"]
    )
    assert "kie.indexed_permission_version >= :permission_version" in (
        permission_filter.keyword_where_sql
    )
    assert "cir.indexed_permission_version >= :permission_version" in (
        permission_filter.keyword_where_sql
    )
    assert "cir.indexed_permission_version >= :permission_version" in (
        permission_filter.metadata_where_sql
    )


def test_build_filter_without_departments_only_allows_enterprise_visibility() -> None:
    context = _permission_context(department_ids=())

    permission_filter = PermissionService().build_filter(context, required_scope="rag:query")

    assert "OR FALSE" in permission_filter.keyword_where_sql
    assert permission_filter.qdrant_filter["should"] == [
        {"key": "visibility", "match": {"value": "enterprise"}}
    ]


def test_build_filter_rejects_missing_scope() -> None:
    context = _permission_context(scopes=("document:read",))

    with pytest.raises(PermissionServiceError) as exc_info:
        PermissionService().build_filter(context, required_scope="rag:query")

    assert exc_info.value.error_code == "PERM_SCOPE_MISSING"


def test_list_queryable_knowledge_base_ids_uses_access_policy() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row({"kb_id": "55555555-5555-5555-5555-555555555555"}),
                    _Row({"kb_id": "66666666-6666-6666-6666-666666666666"}),
                ]
            )
        ]
    )

    kb_ids = PermissionService().list_queryable_knowledge_base_ids(
        session,
        _permission_context(),
        required_scope="rag:query",
    )

    assert kb_ids == (
        "55555555-5555-5555-5555-555555555555",
        "66666666-6666-6666-6666-666666666666",
    )
    statement, params = session.executed[0]
    assert "FROM knowledge_bases kb" in statement
    assert "knowledge_base_accesses kba" in statement
    assert "kb.status = 'active'" in statement
    assert "kb.id = ANY" not in statement
    assert params["kb_kb_access_permissions"] == ["manage", "query"]


def test_list_queryable_knowledge_base_ids_rejects_missing_scope() -> None:
    with pytest.raises(PermissionServiceError) as exc_info:
        PermissionService().list_queryable_knowledge_base_ids(
            _FakeSession([]),
            _permission_context(scopes=("document:read",)),
            required_scope="rag:query",
        )

    assert exc_info.value.error_code == "PERM_SCOPE_MISSING"


def test_gate_candidate_allows_enterprise_and_own_department() -> None:
    service = PermissionService()
    context = _permission_context()

    enterprise_result = service.gate_candidate(
        context,
        _candidate(visibility="enterprise", owner_department_id=OTHER_DEPARTMENT_ID),
    )
    department_result = service.gate_candidate(
        context,
        _candidate(visibility="department", owner_department_id=DEPARTMENT_ID),
    )

    assert enterprise_result.allowed is True
    assert department_result.allowed is True


def test_gate_candidate_rejects_other_department_and_access_block() -> None:
    service = PermissionService()
    context = _permission_context(permission_version=42)

    other_department = service.gate_candidate(
        context,
        _candidate(visibility="department", owner_department_id=OTHER_DEPARTMENT_ID),
    )
    blocked = service.gate_candidate(context, _candidate(access_blocked=True))

    assert other_department.allowed is False
    assert other_department.error_code == "PERM_DENIED"
    assert blocked.allowed is False
    assert blocked.error_code == "PERM_ACCESS_BLOCKED"


def test_gate_candidate_rejects_stale_index_version() -> None:
    result = PermissionService().gate_candidate(
        _permission_context(),
        _candidate(index_version_id="66666666-6666-6666-6666-666666666666"),
        active_index_version_ids=("99999999-9999-9999-9999-999999999999",),
    )

    assert result.allowed is False
    assert result.error_code == "PERM_VERSION_STALE"


@pytest.mark.parametrize(
    ("candidate_kwargs", "detail_key"),
    [
        ({"document_lifecycle_status": "deleted"}, "document_lifecycle_status"),
        ({"document_index_status": "draft"}, "document_index_status"),
        ({"chunk_status": "deleted"}, "chunk_status"),
        ({"visibility_state": "pending_delete"}, "visibility_state"),
    ],
)
def test_gate_candidate_rejects_deleted_blocked_or_non_active_states(
    candidate_kwargs: dict[str, str],
    detail_key: str,
) -> None:
    result = PermissionService().gate_candidate(
        _permission_context(),
        _candidate(**candidate_kwargs),
    )

    assert result.allowed is False
    assert result.error_code == "PERM_ACCESS_BLOCKED"
    assert detail_key in result.details


def test_validate_visibility_policy_rejects_unsupported_acl_and_invalid_visibility() -> None:
    service = PermissionService()

    with pytest.raises(PermissionServiceError) as unsupported:
        service.validate_visibility_policy(
            {
                "visibility": "department",
                "owner_department_id": DEPARTMENT_ID,
                "user_ids": [USER_ID],
            }
        )
    with pytest.raises(PermissionServiceError) as invalid:
        service.validate_visibility_policy({"visibility": "private"})

    assert unsupported.value.error_code == "UNSUPPORTED_PERMISSION_POLICY"
    assert invalid.value.error_code == "PERM_VISIBILITY_INVALID"


def test_build_permission_snapshot_payload_returns_stable_hash() -> None:
    payload = PermissionService().build_permission_snapshot_payload(
        owner_department_id=DEPARTMENT_ID,
        visibility="department",
        permission_version=42,
        policy_version=3,
    )

    assert payload["payload"] == {
        "owner_department_id": DEPARTMENT_ID,
        "visibility": "department",
        "permission_version": 42,
        "policy_version": 3,
    }
    assert payload["payload_hash"]


def _permission_context(
    *,
    department_ids: tuple[str, ...] = (DEPARTMENT_ID,),
    scopes: tuple[str, ...] = ("rag:query", "document:read"),
    permission_version: int = 42,
):
    from app.modules.permissions.schemas import PermissionContext

    return PermissionContext(
        enterprise_id=ENTERPRISE_ID,
        user_id=USER_ID,
        username="alice",
        status="active",
        department_ids=department_ids,
        departments=(),
        roles=(),
        scopes=scopes,
        permission_version=permission_version,
        org_version=7,
        permission_filter_hash="perm_hash",
        request_id="req_test",
    )


def _candidate(
    *,
    visibility: str = "department",
    owner_department_id: str = DEPARTMENT_ID,
    document_lifecycle_status: str = "active",
    document_index_status: str = "indexed",
    chunk_status: str = "active",
    visibility_state: str = "active",
    index_version_id: str = "66666666-6666-6666-6666-666666666666",
    indexed_permission_version: int = 42,
    access_blocked: bool = False,
) -> CandidateMetadata:
    return CandidateMetadata(
        enterprise_id=ENTERPRISE_ID,
        kb_id="55555555-5555-5555-5555-555555555555",
        document_id="77777777-7777-7777-7777-777777777777",
        chunk_id="88888888-8888-8888-8888-888888888888",
        owner_department_id=owner_department_id,
        visibility=visibility,
        document_lifecycle_status=document_lifecycle_status,
        document_index_status=document_index_status,
        chunk_status=chunk_status,
        visibility_state=visibility_state,
        index_version_id=index_version_id,
        indexed_permission_version=indexed_permission_version,
        access_blocked=access_blocked,
    )
