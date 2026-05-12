from __future__ import annotations

import json

from app.adapters import QdrantVectorIndexWriter, QdrantVectorRetriever
from app.modules.indexing.schemas import DraftVectorPoint
from app.modules.permissions.schemas import PermissionFilter

ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_ID = "44444444-4444-4444-4444-444444444444"
DOC_VERSION_ID = "55555555-5555-5555-5555-555555555555"
CHUNK_ID = "66666666-6666-6666-6666-666666666666"
INDEX_VERSION_ID = "88888888-8888-8888-8888-888888888888"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"


class _EmbeddingClient:
    def embed_query(self, query_text: str) -> list[float]:
        assert query_text == "员工手册"
        return [0.1, 0.2]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _text in texts]


class _Response:
    def __init__(self, payload: object | None = None) -> None:
        self.payload = payload

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        payload = self.payload or {
            "result": [
                {
                    "score": 0.88,
                    "payload": {
                        "enterprise_id": ENTERPRISE_ID,
                        "kb_id": KB_ID,
                        "document_id": DOC_ID,
                        "document_version_id": DOC_VERSION_ID,
                        "chunk_id": CHUNK_ID,
                        "title": "员工手册",
                        "owner_department_id": DEPARTMENT_ID,
                        "visibility": "department",
                        "document_status": "active",
                        "document_index_status": "indexed",
                        "chunk_status": "active",
                        "visibility_state": "active",
                        "index_version_id": INDEX_VERSION_ID,
                        "permission_version": 42,
                        "page_start": 1,
                        "page_end": 2,
                    },
                }
            ]
        }
        return json.dumps(payload).encode("utf-8")


def test_qdrant_vector_retriever_searches_with_permission_filter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr("app.adapters.qdrant.urlopen", _urlopen)

    result = QdrantVectorRetriever(
        base_url="http://qdrant:6333",
        api_key="qdrant-key",
        embedding_client=_EmbeddingClient(),
        timeout_seconds=2.0,
    ).search(
        query_text="员工手册",
        permission_filter=_permission_filter(),
        collection_names=("little_bear_p0",),
        top_k=5,
    )

    assert result.degraded is False
    assert result.candidates[0].source == "vector"
    assert result.candidates[0].chunk_id == CHUNK_ID
    assert captured["url"] == "http://qdrant:6333/collections/little_bear_p0/points/search"
    assert captured["timeout"] == 2.0
    assert captured["body"]["vector"] == [0.1, 0.2]
    assert captured["body"]["filter"]["must"][0]["key"] == "enterprise_id"


def test_qdrant_vector_index_writer_upserts_draft_points(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response({"result": {"status": "acknowledged"}})

    monkeypatch.setattr("app.adapters.qdrant.urlopen", _urlopen)

    QdrantVectorIndexWriter(
        base_url="http://qdrant:6333",
        api_key="qdrant-key",
        embedding_client=_EmbeddingClient(),
        timeout_seconds=2.0,
    ).upsert_draft_points(
        (
            DraftVectorPoint(
                collection_name="little_bear_p0",
                vector_id="11111111-1111-5111-8111-111111111111",
                text="员工手册正文",
                payload={"chunk_id": CHUNK_ID, "visibility_state": "draft"},
            ),
        )
    )

    assert captured["method"] == "PUT"
    assert captured["url"] == "http://qdrant:6333/collections/little_bear_p0/points"
    assert captured["timeout"] == 2.0
    assert captured["body"]["points"][0]["id"] == "11111111-1111-5111-8111-111111111111"
    assert captured["body"]["points"][0]["vector"] == [0.1, 0.2]
    assert captured["body"]["points"][0]["payload"]["visibility_state"] == "draft"


def test_qdrant_vector_index_writer_activates_points(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response({"result": {"status": "acknowledged"}})

    monkeypatch.setattr("app.adapters.qdrant.urlopen", _urlopen)

    QdrantVectorIndexWriter(
        base_url="http://qdrant:6333",
        api_key="qdrant-key",
        embedding_client=_EmbeddingClient(),
        timeout_seconds=2.0,
    ).activate_points(
        collection_name="little_bear_p0",
        vector_ids=("11111111-1111-5111-8111-111111111111",),
        permission_version=42,
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "http://qdrant:6333/collections/little_bear_p0/points/payload"
    assert captured["timeout"] == 2.0
    assert captured["body"]["points"] == ["11111111-1111-5111-8111-111111111111"]
    assert captured["body"]["payload"]["visibility_state"] == "active"
    assert captured["body"]["payload"]["indexed_permission_version"] == 42


def _permission_filter() -> PermissionFilter:
    return PermissionFilter(
        enterprise_id=ENTERPRISE_ID,
        department_ids=(DEPARTMENT_ID,),
        kb_ids=(KB_ID,),
        active_index_version_ids=(INDEX_VERSION_ID,),
        permission_version=42,
        permission_filter_hash="perm_hash",
        qdrant_filter={
            "must": [{"key": "enterprise_id", "match": {"value": ENTERPRISE_ID}}],
            "should": [],
            "must_not": [],
        },
        keyword_where_sql="",
        metadata_where_sql="",
        params={},
    )
