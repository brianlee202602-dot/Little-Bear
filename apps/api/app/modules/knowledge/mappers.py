"""普通用户知识库浏览映射和通用错误转换。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.knowledge.schemas import (
    AccessibleChunk,
    AccessibleDocument,
    AccessibleDocumentListItem,
    AccessibleDocumentVersion,
    AccessibleKnowledgeBase,
)
from app.modules.permissions.schemas import PermissionContext
from app.modules.permissions.service import knowledge_base_access_where_sql
from sqlalchemy.exc import SQLAlchemyError


def knowledge_base_visibility_sql(
    context: PermissionContext,
    params: dict[str, Any],
) -> str:
    return knowledge_base_access_where_sql(
        context,
        params,
        permission="discover",
        alias="kb",
    )


def knowledge_base_from_mapping(row: Any) -> AccessibleKnowledgeBase:
    return AccessibleKnowledgeBase(
        id=str(row["kb_id"]),
        name=str(row["name"]),
        status=str(row["status"]),
    )


def document_from_mapping(row: Any) -> AccessibleDocument:
    return AccessibleDocument(
        id=str(row["document_id"]),
        title=str(row["title"]),
        lifecycle_status=str(row["lifecycle_status"]),
        index_status=str(row["index_status"]),
        updated_at=row.get("updated_at") if isinstance(row.get("updated_at"), datetime) else None,
    )


def document_list_item_from_mapping(row: Any) -> AccessibleDocumentListItem:
    return AccessibleDocumentListItem(
        id=str(row["document_id"]),
        title=str(row["title"]),
        lifecycle_status=str(row["lifecycle_status"]),
        index_status=str(row["index_status"]),
        updated_at=row.get("updated_at") if isinstance(row.get("updated_at"), datetime) else None,
    )


def document_version_from_mapping(row: Any) -> AccessibleDocumentVersion:
    return AccessibleDocumentVersion(
        id=str(row["version_id"]),
        document_id=str(row["document_id"]),
        version_no=int(row["version_no"]),
        status=str(row["status"]),
    )


def chunk_from_mapping(row: Any) -> AccessibleChunk:
    return AccessibleChunk(
        id=str(row["chunk_id"]),
        document_id=str(row["document_id"]),
        document_version_id=str(row["document_version_id"]),
        text_preview=str(row["text_preview"]),
        page_start=optional_int(row.get("page_start")),
        page_end=optional_int(row.get("page_end")),
        status=str(row["status"]),
        ordinal=int(row["ordinal"]),
    )


def optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def json_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> KnowledgeServiceError:
    return KnowledgeServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )


# 旧测试和内部模块仍使用下划线 helper；保留别名，但真实归属为本 mapper。
_knowledge_base_visibility_sql = knowledge_base_visibility_sql
_knowledge_base_from_mapping = knowledge_base_from_mapping
_document_from_mapping = document_from_mapping
_document_list_item_from_mapping = document_list_item_from_mapping
_document_version_from_mapping = document_version_from_mapping
_chunk_from_mapping = chunk_from_mapping
_optional_str = optional_str
_optional_int = optional_int
_json_mapping = json_mapping
_database_error = database_error

