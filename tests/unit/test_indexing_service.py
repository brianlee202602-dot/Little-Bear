from __future__ import annotations

import uuid

import pytest
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.service import IndexingService


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
        self.results: list[_Result] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        if self.results:
            return self.results.pop(0)
        return _Result()


class _FakeVectorIndexWriter:
    def __init__(self) -> None:
        self.draft_points: tuple[object, ...] = ()
        self.activated: list[dict[str, object]] = []

    def upsert_draft_points(self, points) -> None:
        self.draft_points = points

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        self.activated.append(
            {
                "collection_name": collection_name,
                "vector_ids": vector_ids,
                "permission_version": permission_version,
            }
        )


_ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
_KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_DOC_ID = "44444444-4444-4444-4444-444444444444"
_DOC_VERSION_ID = "55555555-5555-5555-5555-555555555555"
_INDEX_VERSION_ID = "88888888-8888-8888-8888-888888888888"
_CHUNK_ID = "99999999-9999-9999-9999-999999999999"
_DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"


def _request_json() -> dict[str, object]:
    return {"document_version_ids": [_DOC_VERSION_ID]}


def _ready_version_mapping(
    *,
    dimension: int = 768,
    chunk_count: int = 1,
) -> dict[str, object]:
    return {
        "enterprise_id": _ENTERPRISE_ID,
        "kb_id": _KB_ID,
        "document_id": _DOC_ID,
        "document_version_id": _DOC_VERSION_ID,
        "index_version_id": _INDEX_VERSION_ID,
        "collection_name": "little_bear_p0",
        "dimension": dimension,
        "chunk_count": chunk_count,
        "permission_version": 8,
    }


def _preflight_mapping(
    *,
    expected_chunk_count: int = 1,
    draft_chunk_count: int = 1,
    draft_vector_ref_count: int = 1,
) -> dict[str, object]:
    return {
        "expected_chunk_count": expected_chunk_count,
        "draft_chunk_count": draft_chunk_count,
        "draft_vector_ref_count": draft_vector_ref_count,
    }


def test_create_draft_indexes_inserts_index_version() -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "enterprise_id": _ENTERPRISE_ID,
                        "kb_id": _KB_ID,
                        "document_id": _DOC_ID,
                        "document_version_id": _DOC_VERSION_ID,
                        "created_by": "11111111-1111-1111-1111-111111111111",
                        "chunk_count": 2,
                        "permission_snapshot_hash": "perm_hash",
                    }
                )
            ]
        ),
        _Result(one_or_none=None),
        _Result(),
        _Result(),
    ]

    index_ids = IndexingService().create_draft_indexes(
        session,
        request_json=_request_json(),
    )

    assert len(index_ids) == 1
    insert_params = next(
        params
        for statement, params in session.executed
        if "INSERT INTO index_versions" in statement
    )
    assert insert_params["chunk_count"] == 2
    assert insert_params["permission_snapshot_hash"] == "perm_hash"
    assert insert_params["embedding_model"] == "p0-placeholder-embedding"


def test_write_draft_indexes_inserts_keyword_refs_and_marks_ready() -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[
                _Row(
                    {
                        "enterprise_id": _ENTERPRISE_ID,
                        "kb_id": _KB_ID,
                        "chunk_id": _CHUNK_ID,
                        "document_id": _DOC_ID,
                        "document_version_id": _DOC_VERSION_ID,
                        "index_version_id": _INDEX_VERSION_ID,
                        "title": "员工手册",
                        "collection_name": "little_bear_p0",
                        "text": "员工手册正文",
                        "owner_department_id": _DEPARTMENT_ID,
                        "visibility": "department",
                        "permission_version": 7,
                        "chunk_content_hash": "chunk_hash",
                        "index_payload_hash": "index_hash",
                        "page_start": 1,
                        "page_end": 2,
                    }
                )
            ]
        ),
        _Result(one_or_none=_Row({"keyword_id": "77777777-7777-7777-7777-777777777777"})),
        _Result(),
        _Result(),
        _Result(),
    ]
    vector_writer = _FakeVectorIndexWriter()

    index_ids = IndexingService(vector_index_writer=vector_writer).write_draft_indexes(
        session,
        request_json=_request_json(),
    )

    assert index_ids == [_INDEX_VERSION_ID]
    assert any(
        "to_tsvector('simple', :search_text)" in statement
        for statement, _ in session.executed
    )
    assert any("INSERT INTO chunk_index_refs" in statement for statement, _ in session.executed)
    assert any("SET status = 'ready'" in statement for statement, _ in session.executed)
    assert len(vector_writer.draft_points) == 1
    point = vector_writer.draft_points[0]
    uuid.UUID(point.vector_id)
    assert point.collection_name == "little_bear_p0"
    assert point.payload["visibility_state"] == "draft"
    assert point.payload["document_index_status"] == "indexing"
    assert point.payload["indexed_permission_version"] == 7
    assert point.payload["page_start"] == 1


def test_publish_ready_indexes_activates_version_document_chunks_and_refs() -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            all_rows=[_Row(_ready_version_mapping())]
        ),
        _Result(one_or_none=_Row(_preflight_mapping())),
        _Result(),
        _Result(),
        _Result(),
        _Result(),
        _Result(),
        _Result(),
        _Result(),
        _Result(),
        _Result(),
    ]

    published = IndexingService().publish_ready_indexes(session, request_json=_request_json())

    assert published == [_INDEX_VERSION_ID]
    statements = [statement for statement, _params in session.executed]
    assert any("SET status = 'archived'" in statement for statement in statements)
    assert any("SET status = 'active'" in statement for statement in statements)
    assert any("current_version_id" in statement for statement in statements)
    assert any("UPDATE chunk_index_refs" in statement for statement in statements)
    assert any("UPDATE keyword_index_entries" in statement for statement in statements)


def test_publish_ready_indexes_activates_vector_points() -> None:
    session = _FakeSession()
    vector_id = "11111111-1111-5111-8111-111111111111"
    session.results = [
        _Result(
            all_rows=[_Row(_ready_version_mapping())]
        ),
        _Result(one_or_none=_Row(_preflight_mapping())),
        _Result(all_rows=[_Row({"vector_id": vector_id})]),
    ]
    vector_writer = _FakeVectorIndexWriter()

    published = IndexingService(vector_index_writer=vector_writer).publish_ready_indexes(
        session,
        request_json=_request_json(),
    )

    assert published == [_INDEX_VERSION_ID]
    assert vector_writer.activated == [
        {
            "collection_name": "little_bear_p0",
            "vector_ids": (vector_id,),
            "permission_version": 8,
        }
    ]


def test_publish_ready_indexes_rejects_chunk_count_mismatch() -> None:
    session = _FakeSession()
    session.results = [
        _Result(all_rows=[_Row(_ready_version_mapping(chunk_count=2))]),
        _Result(
            one_or_none=_Row(
                _preflight_mapping(
                    expected_chunk_count=2,
                    draft_chunk_count=1,
                    draft_vector_ref_count=2,
                )
            )
        ),
    ]

    with pytest.raises(IndexingServiceError) as exc_info:
        IndexingService(dimension=768).publish_ready_indexes(
            session,
            request_json=_request_json(),
        )

    assert exc_info.value.error_code == "INDEX_CHUNK_COUNT_MISMATCH"
    assert exc_info.value.details["draft_chunk_count"] == 1
    assert not any("UPDATE documents" in statement for statement, _ in session.executed)


def test_publish_ready_indexes_rejects_vector_ref_count_mismatch() -> None:
    session = _FakeSession()
    session.results = [
        _Result(all_rows=[_Row(_ready_version_mapping(chunk_count=2))]),
        _Result(
            one_or_none=_Row(
                _preflight_mapping(
                    expected_chunk_count=2,
                    draft_chunk_count=2,
                    draft_vector_ref_count=1,
                )
            )
        ),
    ]

    with pytest.raises(IndexingServiceError) as exc_info:
        IndexingService(dimension=768).publish_ready_indexes(
            session,
            request_json=_request_json(),
        )

    assert exc_info.value.error_code == "INDEX_VECTOR_REFS_INCOMPLETE"
    assert exc_info.value.details["draft_vector_ref_count"] == 1
    assert not any("UPDATE chunk_index_refs" in statement for statement, _ in session.executed)


def test_publish_ready_indexes_rejects_embedding_dimension_mismatch() -> None:
    session = _FakeSession()
    session.results = [
        _Result(all_rows=[_Row(_ready_version_mapping(dimension=384))]),
        _Result(one_or_none=_Row(_preflight_mapping())),
    ]

    with pytest.raises(IndexingServiceError) as exc_info:
        IndexingService(dimension=768).publish_ready_indexes(
            session,
            request_json=_request_json(),
        )

    assert exc_info.value.error_code == "INDEX_DIMENSION_MISMATCH"
    assert exc_info.value.details["index_dimension"] == 384
    assert not any("UPDATE index_versions" in statement for statement, _ in session.executed)
