"""Document version administration read service."""

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


class AdminDocumentVersionsReader:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_document_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        doc_id: str,
        page: int,
        page_size: int,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDocumentVersionList:
        """读取文档内容版本列表。"""

        self._core_service._ensure_actor_can_manage_documents(actor_context)
        self._core_service.get_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS version_id,
                        document_id::text AS document_id,
                        version_no,
                        status
                    FROM document_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:doc_id AS uuid)
                    ORDER BY version_no DESC, created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "doc_id": doc_id,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM document_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:doc_id AS uuid)
                    """
                ),
                {"enterprise_id": enterprise_id, "doc_id": doc_id},
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_VERSIONS_UNAVAILABLE",
                "document versions cannot be read",
                exc,
            ) from exc
        return AdminDocumentVersionList(
            items=[_document_version_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_document_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        doc_id: str,
        page: int,
        page_size: int,
        actor_context: AdminActorContext | None = None,
    ) -> AdminIndexVersionList:
        """读取文档索引版本列表，用于管理端诊断和重建前确认。"""

        self._core_service._ensure_actor_can_index_documents(actor_context)
        document = self._core_service._load_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
        )
        knowledge_base = self._core_service._load_knowledge_base(
            session,
            document.kb_id,
            enterprise_id=enterprise_id,
        )
        self._core_service._ensure_actor_can_access_knowledge_base(
            actor_context,
            knowledge_base,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS index_version_id,
                        document_id::text AS document_id,
                        document_version_id::text AS document_version_id,
                        embedding_model,
                        model_version,
                        dimension,
                        collection_name,
                        status,
                        chunk_count,
                        created_at,
                        activated_at
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:doc_id AS uuid)
                    ORDER BY
                        CASE status
                            WHEN 'active' THEN 0
                            WHEN 'ready' THEN 1
                            WHEN 'draft' THEN 2
                            WHEN 'pending_delete' THEN 3
                            WHEN 'failed' THEN 4
                            ELSE 5
                        END,
                        created_at DESC,
                        id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "doc_id": doc_id,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:doc_id AS uuid)
                    """
                ),
                {"enterprise_id": enterprise_id, "doc_id": doc_id},
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_VERSIONS_UNAVAILABLE",
                "document index versions cannot be read",
                exc,
            ) from exc
        return AdminIndexVersionList(
            items=[_admin_index_version_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

