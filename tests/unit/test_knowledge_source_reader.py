from __future__ import annotations

import pytest
from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.knowledge.source_reader import KnowledgeSourceReader
from app.modules.permissions.schemas import PermissionContext, PermissionFilter
from app.modules.storage.service import InMemoryObjectStorage

ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"
KB_ID = "55555555-5555-5555-5555-555555555555"
DOCUMENT_ID = "77777777-7777-7777-7777-777777777777"
SOURCE_ID = "88888888-8888-8888-8888-888888888888"
INDEX_VERSION_ID = "66666666-6666-6666-6666-666666666666"


def test_source_reader_resolves_object_storage_from_factory() -> None:
    storage = InMemoryObjectStorage({"chunks/doc_1/chunk_1.txt": "完整来源正文".encode()})
    factory_sessions: list[object] = []

    def object_storage_factory(session):
        factory_sessions.append(session)
        return storage

    reader = KnowledgeSourceReader(object_storage_factory=object_storage_factory)
    session = object()

    source = reader.source_from_mapping(
        session,
        {
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "document_version_id": "version_1",
            "title": "员工手册",
            "text_object_key": "chunks/doc_1/chunk_1.txt",
            "text_preview": "来源预览",
            "page_start": 1,
            "page_end": 2,
            "ordinal": 3,
            "heading_path": "制度 / 请假",
            "source_offsets": {"start": 0, "end": 4},
        },
    )

    assert factory_sessions == [session]
    assert source.text == "完整来源正文"
    assert source.text_preview == "来源预览"
    assert source.text_status == "object"


def test_get_document_source_fails_closed_when_no_active_index_versions() -> None:
    storage_sessions: list[object] = []
    repository = _FakeKnowledgeRepository(active_index_version_ids=())
    reader = KnowledgeSourceReader(
        access_guard=_FakeKnowledgeAccessGuard(),
        repository=repository,
        object_storage_factory=lambda session: storage_sessions.append(session) or None,
    )

    with pytest.raises(KnowledgeServiceError) as exc_info:
        reader.get_document_source(
            object(),
            user_id=USER_ID,
            enterprise_id=ENTERPRISE_ID,
            document_id=DOCUMENT_ID,
            source_id=SOURCE_ID,
            request_id="req_source",
        )

    assert exc_info.value.error_code == "KNOWLEDGE_SOURCE_NOT_FOUND"
    assert repository.source_row_calls == []
    assert storage_sessions == []


def test_get_document_source_rechecks_permission_filter_before_object_storage_read() -> None:
    storage_sessions: list[object] = []
    permission_service = _FakePermissionService()
    repository = _FakeKnowledgeRepository(source_row=None)
    reader = KnowledgeSourceReader(
        access_guard=_FakeKnowledgeAccessGuard(permission_service=permission_service),
        repository=repository,
        object_storage_factory=lambda session: storage_sessions.append(session) or None,
    )

    with pytest.raises(KnowledgeServiceError) as exc_info:
        reader.get_document_source(
            object(),
            user_id=USER_ID,
            enterprise_id=ENTERPRISE_ID,
            document_id=DOCUMENT_ID,
            source_id=SOURCE_ID,
            request_id="req_source",
        )

    assert exc_info.value.error_code == "KNOWLEDGE_SOURCE_NOT_FOUND"
    assert permission_service.calls == [
        {
            "kb_ids": (KB_ID,),
            "active_index_version_ids": (INDEX_VERSION_ID,),
            "required_scope": "document:read",
        }
    ]
    assert repository.source_row_calls[0]["document_id"] == DOCUMENT_ID
    assert repository.source_row_calls[0]["source_id"] == SOURCE_ID
    assert repository.source_row_calls[0]["permission_filter"].active_index_version_ids == (
        INDEX_VERSION_ID,
    )
    assert storage_sessions == []


class _FakePermissionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_filter(
        self,
        _context: PermissionContext,
        *,
        kb_ids: tuple[str, ...],
        active_index_version_ids: tuple[str, ...],
        required_scope: str,
    ) -> PermissionFilter:
        self.calls.append(
            {
                "kb_ids": kb_ids,
                "active_index_version_ids": active_index_version_ids,
                "required_scope": required_scope,
            }
        )
        return PermissionFilter(
            enterprise_id=ENTERPRISE_ID,
            department_ids=(DEPARTMENT_ID,),
            kb_ids=kb_ids,
            active_index_version_ids=active_index_version_ids,
            permission_version=42,
            permission_filter_hash="perm_hash",
            qdrant_filter={},
            keyword_where_sql="TRUE",
            metadata_where_sql="TRUE",
            params={},
        )


class _FakeKnowledgeAccessGuard:
    def __init__(self, *, permission_service: _FakePermissionService | None = None) -> None:
        self.permission_service = permission_service or _FakePermissionService()
        self.queryable_kb_ids: list[str] = []

    def permission_context(
        self,
        _session: object,
        *,
        user_id: str,
        enterprise_id: str,
        request_id: str | None,
        required_scope: str,
    ) -> PermissionContext:
        assert user_id == USER_ID
        assert enterprise_id == ENTERPRISE_ID
        assert request_id == "req_source"
        assert required_scope == "document:read"
        return PermissionContext(
            enterprise_id=ENTERPRISE_ID,
            user_id=USER_ID,
            username="alice",
            status="active",
            department_ids=(DEPARTMENT_ID,),
            departments=(),
            roles=(),
            scopes=("document:read", "rag:query"),
            permission_version=42,
            org_version=7,
            permission_filter_hash="perm_hash",
            request_id=request_id,
        )

    def ensure_queryable_knowledge_base(
        self,
        _session: object,
        _context: PermissionContext,
        *,
        kb_id: str,
    ) -> None:
        self.queryable_kb_ids.append(kb_id)


class _FakeKnowledgeRepository:
    def __init__(
        self,
        *,
        active_index_version_ids: tuple[str, ...] = (INDEX_VERSION_ID,),
        source_row: object | None = None,
    ) -> None:
        self.active_index_version_ids = active_index_version_ids
        self.source_row = source_row
        self.source_row_calls: list[dict[str, object]] = []

    def load_document_kb_id(
        self,
        _session: object,
        *,
        enterprise_id: str,
        document_id: str,
    ) -> str:
        assert enterprise_id == ENTERPRISE_ID
        assert document_id == DOCUMENT_ID
        return KB_ID

    def load_active_index_versions(
        self,
        _session: object,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        assert enterprise_id == ENTERPRISE_ID
        assert kb_ids == (KB_ID,)
        return self.active_index_version_ids

    def get_document_source_row(
        self,
        _session: object,
        *,
        permission_filter: PermissionFilter,
        document_id: str,
        source_id: str,
    ) -> object | None:
        self.source_row_calls.append(
            {
                "permission_filter": permission_filter,
                "document_id": document_id,
                "source_id": source_id,
            }
        )
        return self.source_row
