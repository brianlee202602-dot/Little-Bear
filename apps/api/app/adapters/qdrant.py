"""Qdrant 向量召回适配器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.modules.models import EmbeddingClient, ModelClientError
from app.modules.permissions.schemas import PermissionFilter
from app.modules.retrieval import RetrievalCandidate, VectorSearchResult

if TYPE_CHECKING:
    from app.modules.indexing.schemas import DraftVectorPoint, VectorPayloadUpdate


@dataclass(frozen=True)
class QdrantCollectionInfo:
    collection_name: str
    exists: bool
    status: str | None = None
    vector_size: int | None = None
    points_count: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class QdrantSnapshotInfo:
    name: str
    size: int | None = None
    creation_time: str | None = None
    checksum: str | None = None


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
        vector_distance: str = "Cosine",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.embedding_client = embedding_client
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.vector_distance = vector_distance

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
            vector_size = len(collection_points[0]["vector"])
            self._ensure_collection(collection_name, vector_size=vector_size)
            _send_json(
                _points_url(self.base_url, collection_name),
                {"points": collection_points},
                method="PUT",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )

    def _ensure_collection(self, collection_name: str, *, vector_size: int) -> None:
        try:
            info = _send_json(
                _collection_url(self.base_url, collection_name),
                None,
                method="GET",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )
        except QdrantClientError as exc:
            if exc.status_code != 404:
                raise
            self._create_collection(collection_name, vector_size=vector_size)
            return

        existing_size = _collection_vector_size(info)
        if existing_size is not None and existing_size != vector_size:
            raise QdrantClientError(
                "qdrant collection vector size mismatch: "
                f"collection={collection_name}, expected={vector_size}, actual={existing_size}"
            )

    def _create_collection(self, collection_name: str, *, vector_size: int) -> None:
        try:
            _send_json(
                _collection_url(self.base_url, collection_name),
                {
                    "vectors": {
                        "size": vector_size,
                        "distance": self.vector_distance,
                    }
                },
                method="PUT",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )
        except QdrantClientError as exc:
            # 多 Worker 首次导入同一 collection 时可能并发创建；409 后重读一次即可。
            if exc.status_code != 409:
                raise
            info = _send_json(
                _collection_url(self.base_url, collection_name),
                None,
                method="GET",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )
            existing_size = _collection_vector_size(info)
            if existing_size is not None and existing_size != vector_size:
                raise QdrantClientError(
                    "qdrant collection vector size mismatch: "
                    f"collection={collection_name}, expected={vector_size}, actual={existing_size}"
                ) from exc

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

    def update_payloads(self, updates: tuple[VectorPayloadUpdate, ...]) -> None:
        for update in updates:
            if not update.collection_name:
                raise QdrantClientError("qdrant collection name is empty")
            _send_json(
                _payload_url(self.base_url, update.collection_name),
                {
                    "payload": update.payload,
                    "points": [update.vector_id],
                },
                method="POST",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )

    def delete_points(self, *, collection_name: str, vector_ids: tuple[str, ...]) -> None:
        if not vector_ids:
            return
        if not collection_name:
            raise QdrantClientError("qdrant collection name is empty")
        _send_json(
            _points_delete_url(self.base_url, collection_name),
            {"points": list(dict.fromkeys(vector_ids))},
            method="POST",
            timeout_seconds=self.timeout_seconds,
            api_key=self.api_key,
        )


class QdrantOpsClient:
    """Qdrant 运维客户端。

    高风险确认、权限和审计由上层 Index Ops Service 负责，这里只封装 Qdrant
    collection 级诊断、snapshot 和 recover HTTP 调用。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def collection_info(self, collection_name: str) -> QdrantCollectionInfo:
        if not collection_name:
            raise QdrantClientError("qdrant collection name is empty")
        try:
            response = _send_json(
                _collection_url(self.base_url, collection_name),
                None,
                method="GET",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )
        except QdrantClientError as exc:
            if exc.status_code == 404:
                return QdrantCollectionInfo(collection_name=collection_name, exists=False)
            raise

        points_count = _collection_points_count(response)
        count_error: str | None = None
        try:
            count_response = _send_json(
                _points_count_url(self.base_url, collection_name),
                {"exact": True},
                method="POST",
                timeout_seconds=self.timeout_seconds,
                api_key=self.api_key,
            )
            points_count = _count_points(count_response)
        except QdrantClientError as exc:
            count_error = str(exc)
        return QdrantCollectionInfo(
            collection_name=collection_name,
            exists=True,
            status=_collection_status(response),
            vector_size=_collection_vector_size(response),
            points_count=points_count,
            error=count_error,
        )

    def list_collection_snapshots(self, collection_name: str) -> tuple[QdrantSnapshotInfo, ...]:
        if not collection_name:
            raise QdrantClientError("qdrant collection name is empty")
        response = _send_json(
            _collection_snapshots_url(self.base_url, collection_name),
            None,
            method="GET",
            timeout_seconds=self.timeout_seconds,
            api_key=self.api_key,
        )
        return tuple(_snapshot_info(item) for item in _snapshot_list(response))

    def create_collection_snapshot(self, collection_name: str) -> QdrantSnapshotInfo:
        if not collection_name:
            raise QdrantClientError("qdrant collection name is empty")
        response = _send_json(
            _collection_snapshots_url(self.base_url, collection_name),
            None,
            method="POST",
            timeout_seconds=self.timeout_seconds,
            api_key=self.api_key,
        )
        return _snapshot_info(_result_object(response))

    def recover_collection_snapshot(
        self,
        collection_name: str,
        *,
        location: str,
        priority: str | None = None,
        checksum: str | None = None,
    ) -> bool:
        if not collection_name:
            raise QdrantClientError("qdrant collection name is empty")
        if not location:
            raise QdrantClientError("qdrant snapshot location is empty")
        payload: dict[str, Any] = {"location": location}
        if priority:
            payload["priority"] = priority
        if checksum:
            payload["checksum"] = checksum
        response = _send_json(
            _collection_snapshot_recover_url(self.base_url, collection_name),
            payload,
            method="PUT",
            timeout_seconds=self.timeout_seconds,
            api_key=self.api_key,
        )
        result = response.get("result") if isinstance(response, dict) else None
        if not isinstance(result, bool):
            raise QdrantClientError("qdrant snapshot recover response is invalid")
        return result


class QdrantClientError(Exception):
    """Qdrant 请求或响应不可用。"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _send_json(
    url: str,
    payload: dict[str, Any] | None,
    *,
    method: str,
    timeout_seconds: float,
    api_key: str | None,
) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json", "accept": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            response_body = response.read()
    except HTTPError as exc:
        response_body = exc.read()
        raise QdrantClientError(
            _http_error_message(exc.code, response_body),
            status_code=exc.code,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise QdrantClientError(f"qdrant request failed: {exc.__class__.__name__}") from exc
    if status < 200 or status >= 300:
        raise QdrantClientError(_http_error_message(status, response_body), status_code=status)
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


def _points_count_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/points/count"


def _points_delete_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/points/delete"


def _payload_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/points/payload"


def _collection_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}"


def _collection_snapshots_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/snapshots"


def _collection_snapshot_recover_url(base_url: str, collection_name: str) -> str:
    encoded_collection = quote(collection_name, safe="")
    return f"{base_url.rstrip('/')}/collections/{encoded_collection}/snapshots/recover"


def _collection_vector_size(response: Any) -> int | None:
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    config = result.get("config")
    if not isinstance(config, dict):
        return None
    params = config.get("params")
    if not isinstance(params, dict):
        return None
    vectors = params.get("vectors")
    if isinstance(vectors, dict):
        size = vectors.get("size")
        if isinstance(size, int):
            return size
        default_vector = vectors.get("default")
        if isinstance(default_vector, dict) and isinstance(default_vector.get("size"), int):
            return int(default_vector["size"])
    return None


def _collection_status(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    return status if isinstance(status, str) else None


def _collection_points_count(response: Any) -> int | None:
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    value = result.get("points_count")
    if isinstance(value, int):
        return value
    value = result.get("vectors_count")
    return value if isinstance(value, int) else None


def _count_points(response: Any) -> int | None:
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    count = result.get("count")
    return count if isinstance(count, int) else None


def _snapshot_list(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        raise QdrantClientError("qdrant response must be a JSON object")
    result = response.get("result")
    if not isinstance(result, list):
        raise QdrantClientError("qdrant response does not contain snapshot list")
    return [item for item in result if isinstance(item, dict)]


def _result_object(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise QdrantClientError("qdrant response must be a JSON object")
    result = response.get("result")
    if not isinstance(result, dict):
        raise QdrantClientError("qdrant response does not contain result object")
    return result


def _snapshot_info(item: dict[str, Any]) -> QdrantSnapshotInfo:
    name = item.get("name")
    if not isinstance(name, str) or not name:
        raise QdrantClientError("qdrant snapshot response does not contain name")
    size = item.get("size")
    creation_time = item.get("creation_time")
    checksum = item.get("checksum")
    return QdrantSnapshotInfo(
        name=name,
        size=int(size) if isinstance(size, (int, float)) else None,
        creation_time=creation_time if isinstance(creation_time, str) else None,
        checksum=checksum if isinstance(checksum, str) else None,
    )


def _http_error_message(status: int, response_body: bytes | None) -> str:
    if not response_body:
        return f"qdrant returned HTTP {status}"
    try:
        body_text = response_body.decode("utf-8", errors="replace").strip()
    except Exception:
        body_text = ""
    if not body_text:
        return f"qdrant returned HTTP {status}"
    return f"qdrant returned HTTP {status}: {body_text[:500]}"


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)
