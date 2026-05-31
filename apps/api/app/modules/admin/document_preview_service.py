"""Document preview administration service."""

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


class AdminDocumentPreviewService:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def get_document_preview(
        self,
        session: Session,
        *,
        enterprise_id: str,
        doc_id: str,
        page: int = 1,
        page_size: int = 20,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDocumentPreview:
        """读取管理后台文档全文预览，按 chunk 返回可定位文本。"""

        self._core_service._ensure_actor_can_manage_documents(actor_context)
        document = self._core_service.get_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        params = {
            "enterprise_id": enterprise_id,
            "doc_id": doc_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS chunk_id,
                        document_id::text AS document_id,
                        document_version_id::text AS document_version_id,
                        text_object_key,
                        text_preview,
                        heading_path,
                        source_offsets,
                        page_start,
                        page_end,
                        status,
                        ordinal
                    FROM chunks
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:doc_id AS uuid)
                      AND deleted_at IS NULL
                      AND status != 'deleted'
                    ORDER BY document_version_id, ordinal, id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM chunks
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:doc_id AS uuid)
                      AND deleted_at IS NULL
                      AND status != 'deleted'
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_PREVIEW_UNAVAILABLE",
                "document preview cannot be read",
                exc,
            ) from exc
        return AdminDocumentPreview(
            doc_id=document.id,
            title=document.title,
            chunks=tuple(self._admin_preview_chunk_from_mapping(row._mapping) for row in rows),
            total=int(total_row._mapping["total"]),
        )

    def _admin_preview_chunk_from_mapping(self, row: Any) -> AdminDocumentPreviewChunk:
        text_preview = str(row["text_preview"])
        object_key = _optional_str(row.get("text_object_key"))
        text, text_status = self._read_preview_text(
            object_key=object_key,
            text_preview=text_preview,
        )
        return AdminDocumentPreviewChunk(
            id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            document_version_id=str(row["document_version_id"]),
            text=text,
            text_preview=text_preview,
            page_start=_optional_int(row.get("page_start")),
            page_end=_optional_int(row.get("page_end")),
            status=str(row["status"]),
            ordinal=int(row["ordinal"]),
            heading_path=_optional_str(row.get("heading_path")),
            source_offsets=_json_mapping(row.get("source_offsets")),
            text_status=text_status,
        )

    def _read_preview_text(
        self,
        *,
        object_key: str | None,
        text_preview: str,
    ) -> tuple[str, str]:
        if not object_key or self._core_service.object_storage is None:
            return text_preview, "preview_only"
        try:
            content = self._core_service.object_storage.get_object(object_key=object_key)
        except (KeyError, OSError):
            return text_preview, "object_unavailable"
        return content.decode("utf-8", errors="replace"), "object"

