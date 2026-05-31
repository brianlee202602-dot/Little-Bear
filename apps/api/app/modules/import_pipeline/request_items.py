"""Import request item and request_json helpers."""

from __future__ import annotations

import json
from typing import Any

from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import DocumentImportItem


def normalize_items(*, job_type: str, items: list[DocumentImportItem]) -> list[DocumentImportItem]:
    if job_type not in {"upload", "url", "metadata_batch"}:
        raise ImportServiceError(
            "IMPORT_JOB_TYPE_INVALID",
            "document import job_type must be upload, url or metadata_batch",
            status_code=400,
            details={"job_type": job_type},
        )
    if not items:
        raise ImportServiceError(
            "IMPORT_ITEMS_REQUIRED",
            "document import requires at least one item",
            status_code=400,
        )
    normalized: list[DocumentImportItem] = []
    for index, item in enumerate(items):
        title = item.title.strip()
        if not title:
            raise ImportServiceError(
                "IMPORT_ITEM_TITLE_REQUIRED",
                "document import item title is required",
                status_code=400,
                details={"item_index": index},
            )
        if job_type == "url" and not item.url:
            raise ImportServiceError(
                "IMPORT_ITEM_URL_REQUIRED",
                "url import item requires url",
                status_code=400,
                details={"item_index": index},
            )
        if job_type == "upload" and item.object_content is None:
            raise ImportServiceError(
                "IMPORT_OBJECT_CONTENT_REQUIRED",
                "upload import item requires raw object content",
                status_code=400,
                details={"item_index": index},
            )
        normalized.append(
            DocumentImportItem(
                title=title,
                url=item.url.strip() if item.url else None,
                object_content=item.object_content,
                content_type=item.content_type,
                metadata=item.metadata,
            )
        )
    return normalized


def metadata_tags(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("tags")
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        tag = item.strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def metadata_source_uri(metadata: dict[str, Any]) -> str | None:
    filename = metadata.get("filename")
    if isinstance(filename, str) and filename:
        return f"upload://{filename}"
    source_uri = metadata.get("source_uri")
    return source_uri if isinstance(source_uri, str) and source_uri else None


def metadata_filename(metadata: dict[str, Any]) -> str | None:
    filename = metadata.get("filename")
    return filename if isinstance(filename, str) and filename else None


def metadata_text(metadata: dict[str, Any]) -> str | None:
    for key in ("content", "text", "markdown"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def request_items(request_json: dict[str, Any]) -> list[dict[str, Any]]:
    items = request_json.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def item_str(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def item_title(item: dict[str, Any]) -> str:
    title = item_str(item, "title")
    return title or "untitled document"


def item_content_type(item: dict[str, Any]) -> str | None:
    content_type = item_str(item, "content_type")
    if content_type:
        return content_type
    metadata = item_metadata(item)
    value = metadata.get("content_type")
    return value if isinstance(value, str) and value.strip() else None


def looks_like_object_key(object_key: str) -> bool:
    lowered = object_key.lower()
    return not lowered.startswith(("http://", "https://"))


def item_text_content(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    metadata_text = metadata_text_from_value(metadata)
    if metadata_text:
        return metadata_text
    title = item.get("title")
    url = item.get("url")
    parts = [value for value in (title, url) if isinstance(value, str) and value.strip()]
    return "\n".join(parts) or "empty document"


def metadata_text_from_value(value: object) -> str | None:
    return metadata_text(value if isinstance(value, dict) else {})


def document_ids_from_request(request_json: dict[str, Any], fallback: str | None) -> list[str]:
    value = request_json.get("document_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return [fallback] if fallback else []


def document_version_ids_from_request(
    request_json: dict[str, Any],
    fallback: str | None,
) -> list[str]:
    value = request_json.get("document_version_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return [fallback] if fallback else []


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}

