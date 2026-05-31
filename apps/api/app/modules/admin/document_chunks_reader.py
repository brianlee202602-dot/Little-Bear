"""Document chunk administration read service."""

# ruff: noqa: F401

from __future__ import annotations

from typing import Any

from app.modules.admin.access_control import AdminActorContext
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.events import (
    _changed_update_fields,
    _document_update_event,
)
from app.modules.admin.mappers import (
    _admin_chunk_from_mapping,
    _admin_index_version_from_mapping,
    _document_from_mapping,
    _document_version_from_mapping,
)
from app.modules.admin.policies import (
    _document_permission_tightens,
    _validate_visibility,
    _visibility_expands,
)
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminChunkList,
    AdminDocument,
    AdminDocumentList,
    AdminDocumentPreview,
    AdminDocumentPreviewChunk,
    AdminDocumentVersionList,
    AdminIndexVersionList,
)
from app.modules.admin.utils import (
    _database_error,
    _json_mapping,
    _normalize_tags,
    _optional_int,
    _optional_str,
)
from app.modules.permissions.errors import PermissionServiceError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminDocumentChunksReader:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_document_chunks(
        self,
        session: Session,
        *,
        enterprise_id: str,
        doc_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminChunkList:
        """读取文档 chunk 预览列表。"""

        self._core_service._ensure_actor_can_manage_documents(actor_context)
        self._core_service.get_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "doc_id": doc_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        filters = [
            "enterprise_id = CAST(:enterprise_id AS uuid)",
            "document_id = CAST(:doc_id AS uuid)",
            "deleted_at IS NULL",
            "status != 'deleted'",
        ]
        if keyword:
            filters.append("text_preview ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            filters.append("status = :status")
            params["status"] = status
        where_sql = " AND ".join(filters)
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS chunk_id,
                        document_id::text AS document_id,
                        document_version_id::text AS document_version_id,
                        text_preview,
                        page_start,
                        page_end,
                        status,
                        ordinal
                    FROM chunks
                    WHERE {where_sql}
                    ORDER BY document_version_id, ordinal, id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    f"""
                    SELECT count(*) AS total
                    FROM chunks
                    WHERE {where_sql}
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_CHUNKS_UNAVAILABLE",
                "document chunks cannot be read",
                exc,
            ) from exc
        return AdminChunkList(
            items=[_admin_chunk_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

