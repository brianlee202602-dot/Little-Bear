"""索引模块内部纯工具函数。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import DraftIndexChunk, DraftVectorPoint, VectorPayloadUpdate
from app.shared.json_utils import stable_json_hash
from sqlalchemy.exc import SQLAlchemyError

VECTOR_ID_NAMESPACE = uuid.UUID("93b57e36-2c2a-4f74-9f56-e9cdb2a9c3c2")


@dataclass(frozen=True)
class PermissionRefreshTarget:
    enterprise_id: str
    kb_id: str
    document_id: str
    document_version_id: str
    index_version_id: str
    collection_name: str
    vector_id: str
    keyword_id: str | None
    chunk_id: str
    title: str
    owner_department_id: str
    visibility: str
    indexed_permission_version: int
    index_payload_hash: str
    document_status: str
    document_index_status: str
    chunk_status: str
    page_start: int | None
    page_end: int | None


def document_version_ids_from_request(request_json: dict[str, Any]) -> list[str]:
    value = request_json.get("document_version_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def document_ids_from_request(request_json: dict[str, Any]) -> list[str]:
    value = request_json.get("document_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    value = request_json.get("document_id")
    return [value] if isinstance(value, str) and value else []


def index_version_ids_from_request(request_json: dict[str, Any]) -> list[str]:
    value = request_json.get("index_version_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    value = request_json.get("index_version_id")
    return [value] if isinstance(value, str) and value else []


def is_rebuild_request(request_json: dict[str, Any]) -> bool:
    return request_json.get("job_type") == "index_rebuild" or request_json.get("rebuild") is True


def vector_id(chunk: DraftIndexChunk) -> str:
    return str(
        uuid.uuid5(
            VECTOR_ID_NAMESPACE,
            f"{chunk.chunk_id}:{chunk.index_version_id}:{chunk.chunk_content_hash}",
        )
    )


def draft_vector_point(chunk: DraftIndexChunk) -> DraftVectorPoint:
    payload_hash = chunk_index_payload_hash(chunk)
    return DraftVectorPoint(
        collection_name=chunk.collection_name,
        vector_id=vector_id(chunk),
        text=chunk.text,
        payload={
            "enterprise_id": chunk.enterprise_id,
            "kb_id": chunk.kb_id,
            "document_id": chunk.document_id,
            "doc_id": chunk.document_id,
            "document_version_id": chunk.document_version_id,
            "chunk_id": chunk.chunk_id,
            "index_version_id": chunk.index_version_id,
            "title": chunk.title,
            "visibility_state": "draft",
            "document_status": "draft",
            "document_index_status": "indexing",
            "chunk_status": "draft",
            "owner_department_id": chunk.owner_department_id,
            "visibility": chunk.visibility,
            "permission_version": chunk.indexed_permission_version,
            "indexed_permission_version": chunk.indexed_permission_version,
            "is_deleted": False,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "payload_hash": payload_hash,
        },
    )


def vector_payload_update(target: PermissionRefreshTarget) -> VectorPayloadUpdate:
    payload_hash = permission_refresh_payload_hash(target)
    return VectorPayloadUpdate(
        collection_name=target.collection_name,
        vector_id=target.vector_id,
        payload={
            "enterprise_id": target.enterprise_id,
            "kb_id": target.kb_id,
            "document_id": target.document_id,
            "doc_id": target.document_id,
            "document_version_id": target.document_version_id,
            "chunk_id": target.chunk_id,
            "index_version_id": target.index_version_id,
            "title": target.title,
            "visibility_state": "active",
            "document_status": target.document_status,
            "document_index_status": target.document_index_status,
            "chunk_status": target.chunk_status,
            "owner_department_id": target.owner_department_id,
            "visibility": target.visibility,
            "permission_version": target.indexed_permission_version,
            "indexed_permission_version": target.indexed_permission_version,
            "is_deleted": False,
            "page_start": target.page_start,
            "page_end": target.page_end,
            "payload_hash": payload_hash,
        },
    )


def chunk_index_payload_hash(chunk: DraftIndexChunk) -> str:
    return stable_json_hash(
        {
            "chunk_id": chunk.chunk_id,
            "index_version_id": chunk.index_version_id,
            "owner_department_id": chunk.owner_department_id,
            "visibility": chunk.visibility,
            "indexed_permission_version": chunk.indexed_permission_version,
            "index_payload_hash": chunk.index_payload_hash,
        }
    )


def permission_refresh_payload_hash(target: PermissionRefreshTarget) -> str:
    return stable_json_hash(
        {
            "chunk_id": target.chunk_id,
            "index_version_id": target.index_version_id,
            "owner_department_id": target.owner_department_id,
            "visibility": target.visibility,
            "indexed_permission_version": target.indexed_permission_version,
            "index_payload_hash": target.index_payload_hash,
        }
    )


def group_vector_ids_by_collection(targets: list[dict[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for target in targets:
        collection_name = target["collection_name"]
        current_vector_id = target["vector_id"]
        key = (collection_name, current_vector_id)
        if key in seen:
            continue
        seen.add(key)
        grouped.setdefault(collection_name, []).append(current_vector_id)
    return grouped


def required_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise IndexingServiceError(
        "INDEX_PERMISSION_REFRESH_REQUEST_INVALID",
        "permission refresh request is missing required field",
        status_code=409,
        details={"field": key},
    )


def optional_str(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def required_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, int):
        return value
    raise IndexingServiceError(
        "INDEX_PERMISSION_REFRESH_REQUEST_INVALID",
        "permission refresh request is missing required integer field",
        status_code=409,
        details={"field": key},
    )


def optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def database_error(error_code: str, message: str, exc: SQLAlchemyError) -> IndexingServiceError:
    original = getattr(exc, "orig", None) or exc.__cause__
    return IndexingServiceError(
        error_code,
        message,
        status_code=500,
        retryable=True,
        details={
            "database_error": {
                "type": exc.__class__.__name__,
                "driver": original.__class__.__name__ if original is not None else None,
            }
        },
    )


def source_error(exc: Exception) -> dict[str, str | None]:
    cause = exc.__cause__
    root_cause = exc
    while root_cause.__cause__ is not None:
        root_cause = root_cause.__cause__
    return {
        "type": exc.__class__.__name__,
        "message": str(exc) or None,
        "cause_type": cause.__class__.__name__ if cause is not None else None,
        "cause_message": str(cause) if cause is not None and str(cause) else None,
        "root_cause_type": root_cause.__class__.__name__,
        "root_cause_message": str(root_cause) or None,
    }
