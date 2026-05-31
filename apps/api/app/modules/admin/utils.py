"""General-purpose admin service helpers."""

from __future__ import annotations

import json
from typing import Any

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import AdminFolder
from sqlalchemy.exc import SQLAlchemyError


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _unique_strings(values: list[str]) -> list[str]:
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


def _json_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _normalize_folder_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise AdminServiceError(
            "ADMIN_FOLDER_INVALID",
            "folder name is required",
            status_code=400,
        )
    return normalized


def _normalize_tags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        if len(item) > 64:
            raise AdminServiceError(
                "ADMIN_DOCUMENT_TAG_INVALID",
                "document tag is too long",
                status_code=400,
                details={"tag": item},
            )
        seen.add(item)
        normalized.append(item)
    if len(normalized) > 50:
        raise AdminServiceError(
            "ADMIN_DOCUMENT_TAG_INVALID",
            "document tags exceed limit",
            status_code=400,
            details={"max_tags": 50},
        )
    return normalized


def _build_folder_path(parent: AdminFolder | None, folder_id: str) -> str:
    parent_path = parent.path.rstrip("/") if parent else ""
    return f"{parent_path}/{folder_id}"


def _folder_path_contains(path: str, folder_id: str) -> bool:
    return f"/{folder_id}/" in f"{path.rstrip('/')}/"


def _normalize_id_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _mask_username(username: str) -> str:
    if len(username) <= 2:
        return "***"
    return f"{username[0]}***{username[-1]}"


def _database_error(error_code: str, message: str, exc: SQLAlchemyError) -> AdminServiceError:
    return AdminServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
