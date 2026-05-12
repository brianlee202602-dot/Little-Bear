"""Qdrant 向量召回适配器。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.modules.models import EmbeddingClient, ModelClientError
from app.modules.permissions.schemas import PermissionFilter
from app.modules.retrieval import RetrievalCandidate, VectorSearchResult

if TYPE_CHECKING:
    from app.modules.indexing.schemas import DraftVectorPoint


class QdrantVectorRetriever:
    """通过 Qdrant points search 执行向量召回。"""

    def __init__(
        self,
        *,
        base_url: str,
        embedding_client: EmbeddingClient,
        api_key: str | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.embedding_client = embedding_client
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        *,
        query_text: str,
        permission_filter: PermissionFilter,
        collection_names: tuple[str, ...],
        top_k: int,
    ) -> VectorSearchResult:
        if not collection_names:
            return VectorSearchResult(
                candidates=(),
                degraded=True,
                degrade_reason="vector_collection_unavailable",
            )
        try:
            vector = self.embedding_client.embed_query(query_text)
            candidates = self._search_collections(
                vector=vector,
                permission_filter=permission_filter,
                collection_names=_unique(collection_names),
                top_k=top_k,
            )
        except ModelClientError:
            return VectorSearchResult(
                candidates=(),
                degraded=True,
                degrade_reason="query_embedding_failed",
            )
        except QdrantClientError:
            return VectorSearchResult(
                candidates=(),
                degraded=True,
                degrade_reason="vector_search_failed",
            )
        return VectorSearchResult(candidates=candidates)

    def _search_collections(
        self,
        *,
        vector: list[float],
        permission_filter: PermissionFilter,
        collection_names: tuple[str, ...],
        top_k: int,
    ) -> tuple[RetrievalCandidate, ...]:
        candidates: list[RetrievalCandidate] = []
        for collection_name in collection_names:
            payload = {
                "vector": vector,
                "filter": permission_filter.qdrant_filter,
                "limit": top_k,
                "with_payload": True,
                "with_vector": False,
            }
            response = _send_json(
                _search_url(self.base_url, collection_name),
                payload,
                method="POST",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )
            points = _points(response)
            for point in points:
                candidate = _candidate_from_point(point, rank=len(candidates) + 1)
                if candidate is not None:
                    candidates.append(candidate)
        candidates.sort(key=lambda item: item.score, reverse=True)
        return tuple(
            _replace_rank(candidate, rank)
            for rank, candidate in enumerate(candidates[: max(top_k, 0)], start=1)
        )


class QdrantVectorIndexWriter:
    """写入和发布 Qdrant point 的索引侧适配器。"""

    def __init__(
        self,
        *,
        base_url: str,
        embedding_client: EmbeddingClient,
        api_key: str | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.embedding_client = embedding_client
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def upsert_draft_points(self, points: tuple[DraftVectorPoint, ...]) -> None:
        if not points:
            return
        try:
            vectors = self.embedding_client.embed_texts([point.text for point in points])
        except ModelClientError as exc:
            raise QdrantClientError("embedding provider failed while indexing") from exc
        if len(vectors) != len(points):
            raise QdrantClientError("embedding count does not match vector point count")

        grouped: dict[str, list[dict[str, Any]]] = {}
        for index, point in enumerate(points):
            if not point.collection_name:
                raise QdrantClientError("qdrant collection name is empty")
            grouped.setdefault(point.collection_name, []).append(
                {
                    "id": point.vector_id,
                    "vector": vectors[index],
                    "payload": point.payload,
                }
            )

        for collection_name, collection_points in grouped.items():
            _send_json(
                _points_url(self.base_url, collection_name),
                {"points": collection_points},
                method="PUT",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        if not vector_ids:
            return
        if not collection_name:
            raise QdrantClientError("qdrant collection name is empty")
        _send_json(
            _payload_url(self.base_url, collection_name),
            {
                "payload": {
                    "visibility_state": "active",
                    "document_status": "active",
                    "document_index_status": "indexed",
                    "chunk_status": "active",
                    "permission_version": permission_version,
                    "indexed_permission_version": permission_version,
                    "is_deleted": False,
                },
                "points": list(vector_ids),
            },
            method="POST",
            timeout_seconds=self.timeout_seconds,
            api_key=self.api_key,
        )


class QdrantClientError(Exception):
    """Qdrant 请求或响应不可用。"""


def _send_json(
    url: str,
    payload: dict[str, Any],
    *,
    method: str,
    timeout_seconds: float,
    api_key: str | None,
) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json", "accept": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            response_body = response.read()
    except HTTPError as exc:
        raise QdrantClientError(f"qdrant returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise QdrantClientError(f"qdrant request failed: {exc.__class__.__name__}") from exc
    if status < 200 or status >= 300:
        raise QdrantClientError(f"qdrant returned HTTP {status}")
    if not response_body:
        return {}
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QdrantClientError("qdrant response is not valid JSON") from exc


def _points(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        raise QdrantClientError("qdrant response must be a JSON object")
    result = response.get("result")
    if isinstance(result, dict) and isinstance(result.get("points"), list):
        return [point for point in result["points"] if isinstance(point, dict)]
    if isinstance(result, list):
        return [point for point in result if isinstance(point, dict)]
    raise QdrantClientError("qdrant response does not contain result points")


def _candidate_from_point(point: dict[str, Any], *, rank: int) -> RetrievalCandidate | None:
    payload = point.get("payload")
    if not isinstance(payload, dict):
        return None
    chunk_id = _payload_str(payload, "chunk_id")
    document_id = _payload_str(payload, "document_id") or _payload_str(payload, "doc_id")
    kb_id = _payload_str(payload, "kb_id")
    enterprise_id = _payload_str(payload, "enterprise_id")
    index_version_id = _payload_str(payload, "index_version_id")
    owner_department_id = _payload_str(payload, "owner_department_id")
    visibility = _payload_str(payload, "visibility")
    if not all(
        (
            chunk_id,
            document_id,
            kb_id,
            enterprise_id,
            index_version_id,
            owner_department_id,
            visibility,
        )
    ):
        return None
    return RetrievalCandidate(
        source="vector",
        enterprise_id=enterprise_id,
        kb_id=kb_id,
        document_id=document_id,
        document_version_id=_payload_str(payload, "document_version_id"),
        chunk_id=chunk_id,
        title=_payload_str(payload, "title") or _payload_str(payload, "document_title") or "",
        owner_department_id=owner_department_id,
        visibility=visibility,
        document_lifecycle_status=_payload_str(payload, "document_status") or "active",
        document_index_status=_payload_str(payload, "document_index_status") or "indexed",
        chunk_status=_payload_str(payload, "chunk_status") or "active",
        visibility_state=_payload_str(payload, "visibility_state") or "active",
        index_version_id=index_version_id,
        indexed_permission_version=_payload_int(payload, "indexed_permission_version")
        or _payload_int(payload, "permission_version")
        or 0,
        page_start=_payload_int(payload, "page_start"),
        page_end=_payload_int(payload, "page_end"),
        rank=rank,
        score=float(point.get("score") or 0),
    )


def _replace_rank(candidate: RetrievalCandidate, rank: int) -> RetrievalCandidate:
    return RetrievalCandidate(
        source=candidate.source,
        enterprise_id=candidate.enterprise_id,
        kb_id=candidate.kb_id,
        document_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        chunk_id=candidate.chunk_id,
        title=candidate.title,
        owner_department_id=candidate.owner_department_id,
        visibility=candidate.visibility,
        document_lifecycle_status=candidate.document_lifecycle_status,
        document_index_status=candidate.document_index_status,
        chunk_status=candidate.chunk_status,
        visibility_state=candidate.visibility_state,
        index_version_id=candidate.index_version_id,
        indexed_permission_version=candidate.indexed_permission_version,
        page_start=candidate.page_start,
        page_end=candidate.page_end,
        rank=rank,
        score=candidate.score,
    )


def _payload_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _payload_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) else None


def _search_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/points/search"


def _points_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/points"


def _payload_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/points/payload"


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)
