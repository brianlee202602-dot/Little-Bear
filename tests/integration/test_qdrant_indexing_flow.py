from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest
from app.adapters import QdrantVectorIndexWriter, QdrantVectorRetriever
from app.modules.indexing.schemas import DraftVectorPoint
from app.modules.models import ModelGatewayEmbeddingClient
from app.modules.permissions.schemas import PermissionFilter

pytestmark = pytest.mark.skipif(
    os.getenv("LITTLE_BEAR_RUN_QDRANT_INTEGRATION") != "1",
    reason="set LITTLE_BEAR_RUN_QDRANT_INTEGRATION=1 to run Qdrant integration tests",
)

ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_ID = "44444444-4444-4444-4444-444444444444"
DOC_VERSION_ID = "55555555-5555-5555-5555-555555555555"
INDEX_VERSION_ID = "88888888-8888-8888-8888-888888888888"
DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"


def test_qdrant_index_writer_and_retriever_round_trip_with_real_services() -> None:
    qdrant_url = _env_str("LITTLE_BEAR_QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = _env_optional("LITTLE_BEAR_QDRANT_API_KEY")
    embedding_url = _env_str("LITTLE_BEAR_EMBEDDING_URL", "http://localhost:8081")
    embedding_model = _env_str("LITTLE_BEAR_EMBEDDING_MODEL", "jina-embeddings-v2-base-zh")
    embedding_provider_type = _env_str("LITTLE_BEAR_EMBEDDING_PROVIDER_TYPE", "tei")
    embedding_dimension = _env_int("LITTLE_BEAR_EMBEDDING_DIMENSION", 768)
    timeout_seconds = _env_float("LITTLE_BEAR_INTEGRATION_TIMEOUT_SECONDS", 30.0)
    collection_name = f"little_bear_it_{uuid.uuid4().hex}"

    _create_collection(
        qdrant_url,
        collection_name=collection_name,
        dimension=embedding_dimension,
        api_key=qdrant_api_key,
        timeout_seconds=timeout_seconds,
    )
    try:
        embedding_client = ModelGatewayEmbeddingClient(
            base_url=embedding_url,
            path=_embedding_path(embedding_provider_type),
            provider_type=embedding_provider_type,
            model=embedding_model,
            auth_token=_env_optional("LITTLE_BEAR_EMBEDDING_API_KEY"),
            timeout_seconds=timeout_seconds,
            expected_dimension=embedding_dimension,
            normalize=True,
        )
        writer = QdrantVectorIndexWriter(
            base_url=qdrant_url,
            api_key=qdrant_api_key,
            embedding_client=embedding_client,
            timeout_seconds=timeout_seconds,
        )
        vector_ids = (
            "11111111-1111-5111-8111-111111111111",
            "22222222-2222-5222-8222-222222222222",
        )
        writer.upsert_draft_points(
            (
                _draft_point(
                    collection_name=collection_name,
                    vector_id=vector_ids[0],
                    chunk_id="66666666-6666-6666-6666-666666666666",
                    text="员工手册规定，员工年假需要提前在系统中提交申请。",
                    page_start=1,
                ),
                _draft_point(
                    collection_name=collection_name,
                    vector_id=vector_ids[1],
                    chunk_id="77777777-7777-7777-7777-777777777777",
                    text="费用报销需要保留发票，并在当月提交给财务审核。",
                    page_start=2,
                ),
            )
        )
        _wait_for_count(
            qdrant_url,
            collection_name=collection_name,
            expected=2,
            api_key=qdrant_api_key,
            timeout_seconds=timeout_seconds,
        )

        writer.activate_points(
            collection_name=collection_name,
            vector_ids=vector_ids,
            permission_version=42,
        )
        _wait_for_count(
            qdrant_url,
            collection_name=collection_name,
            expected=2,
            api_key=qdrant_api_key,
            timeout_seconds=timeout_seconds,
            qdrant_filter=_active_filter(),
        )

        result = QdrantVectorRetriever(
            base_url=qdrant_url,
            api_key=qdrant_api_key,
            embedding_client=embedding_client,
            timeout_seconds=timeout_seconds,
        ).search(
            query_text="员工如何申请年假",
            permission_filter=_permission_filter(),
            collection_names=(collection_name,),
            top_k=2,
        )

        assert result.degraded is False
        assert result.candidates
        assert result.candidates[0].visibility_state == "active"
        assert result.candidates[0].indexed_permission_version == 42
        assert result.candidates[0].chunk_id in {
            "66666666-6666-6666-6666-666666666666",
            "77777777-7777-7777-7777-777777777777",
        }
    finally:
        _delete_collection(
            qdrant_url,
            collection_name=collection_name,
            api_key=qdrant_api_key,
            timeout_seconds=timeout_seconds,
        )


def _draft_point(
    *,
    collection_name: str,
    vector_id: str,
    chunk_id: str,
    text: str,
    page_start: int,
) -> DraftVectorPoint:
    return DraftVectorPoint(
        collection_name=collection_name,
        vector_id=vector_id,
        text=text,
        payload={
            "enterprise_id": ENTERPRISE_ID,
            "kb_id": KB_ID,
            "document_id": DOC_ID,
            "doc_id": DOC_ID,
            "document_version_id": DOC_VERSION_ID,
            "chunk_id": chunk_id,
            "index_version_id": INDEX_VERSION_ID,
            "title": "员工手册",
            "visibility_state": "draft",
            "document_status": "draft",
            "document_index_status": "indexing",
            "chunk_status": "draft",
            "owner_department_id": DEPARTMENT_ID,
            "visibility": "enterprise",
            "permission_version": 7,
            "indexed_permission_version": 7,
            "is_deleted": False,
            "page_start": page_start,
            "page_end": page_start,
            "payload_hash": f"payload_hash_{page_start}",
        },
    )


def _permission_filter() -> PermissionFilter:
    return PermissionFilter(
        enterprise_id=ENTERPRISE_ID,
        department_ids=(DEPARTMENT_ID,),
        kb_ids=(KB_ID,),
        active_index_version_ids=(INDEX_VERSION_ID,),
        permission_version=42,
        permission_filter_hash="integration_perm_hash",
        qdrant_filter=_active_filter(),
        keyword_where_sql="",
        metadata_where_sql="",
        params={},
    )


def _active_filter() -> dict[str, Any]:
    return {
        "must": [
            {"key": "enterprise_id", "match": {"value": ENTERPRISE_ID}},
            {"key": "kb_id", "match": {"value": KB_ID}},
            {"key": "index_version_id", "match": {"value": INDEX_VERSION_ID}},
            {"key": "visibility_state", "match": {"value": "active"}},
            {"key": "document_status", "match": {"value": "active"}},
            {"key": "document_index_status", "match": {"value": "indexed"}},
            {"key": "chunk_status", "match": {"value": "active"}},
            {"key": "visibility", "match": {"value": "enterprise"}},
            {"key": "is_deleted", "match": {"value": False}},
            {"key": "permission_version", "range": {"gte": 42}},
        ],
        "should": [],
        "must_not": [],
    }


def _create_collection(
    base_url: str,
    *,
    collection_name: str,
    dimension: int,
    api_key: str | None,
    timeout_seconds: float,
) -> None:
    _request_json(
        "PUT",
        _collection_url(base_url, collection_name),
        {
            "vectors": {
                "size": dimension,
                "distance": "Cosine",
            }
        },
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )


def _delete_collection(
    base_url: str,
    *,
    collection_name: str,
    api_key: str | None,
    timeout_seconds: float,
) -> None:
    try:
        _request_json(
            "DELETE",
            _collection_url(base_url, collection_name),
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
    except (HTTPError, URLError, TimeoutError, OSError):
        return


def _wait_for_count(
    base_url: str,
    *,
    collection_name: str,
    expected: int,
    api_key: str | None,
    timeout_seconds: float,
    qdrant_filter: dict[str, Any] | None = None,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_count: int | None = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            last_count = _count_points(
                base_url,
                collection_name=collection_name,
                api_key=api_key,
                timeout_seconds=min(timeout_seconds, 5.0),
                qdrant_filter=qdrant_filter,
            )
            if last_count == expected:
                return
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise AssertionError(
        f"expected {expected} qdrant points, got {last_count}; last_error={last_error}"
    )


def _count_points(
    base_url: str,
    *,
    collection_name: str,
    api_key: str | None,
    timeout_seconds: float,
    qdrant_filter: dict[str, Any] | None = None,
) -> int:
    payload: dict[str, Any] = {"exact": True}
    if qdrant_filter is not None:
        payload["filter"] = qdrant_filter
    response = _request_json(
        "POST",
        f"{_collection_url(base_url, collection_name)}/points/count",
        payload,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    result = response.get("result") if isinstance(response, dict) else None
    if not isinstance(result, dict) or not isinstance(result.get("count"), int):
        raise ValueError("qdrant count response does not include result.count")
    return result["count"]


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    api_key: str | None,
    timeout_seconds: float,
) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"accept": "application/json"}
    if payload is not None:
        headers["content-type"] = "application/json"
    if api_key:
        headers["api-key"] = api_key
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=timeout_seconds) as response:
        response_body = response.read()
    if not response_body:
        return {}
    return json.loads(response_body.decode("utf-8"))


def _collection_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}"


def _embedding_path(provider_type: str) -> str:
    return "/embed" if provider_type == "tei" else "/v1/embeddings"


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _env_str(name: str, default: str) -> str:
    return os.getenv(name) or default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default
