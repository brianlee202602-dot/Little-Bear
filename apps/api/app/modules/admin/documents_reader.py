"""Document administration read service."""

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


class AdminDocumentsReader:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_documents(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
        lifecycle_status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDocumentList:
        """读取知识库内文档元数据列表。"""

        self._core_service._ensure_actor_can_manage_documents(actor_context)
        knowledge_base = self._core_service.get_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "d.enterprise_id = CAST(:enterprise_id AS uuid)",
            "d.kb_id = CAST(:kb_id AS uuid)",
            "d.deleted_at IS NULL",
            "d.lifecycle_status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "kb_id": knowledge_base.id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if lifecycle_status:
            if lifecycle_status not in {"draft", "active", "archived", "deleted"}:
                raise AdminServiceError(
                    "ADMIN_DOCUMENT_STATUS_INVALID",
                    "document lifecycle status is invalid",
                    status_code=400,
                    details={"lifecycle_status": lifecycle_status},
                )
            conditions.append("d.lifecycle_status = :lifecycle_status")
            params["lifecycle_status"] = lifecycle_status
        where_sql = " AND ".join(conditions)
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        d.id::text AS doc_id,
                        d.kb_id::text AS kb_id,
                        d.folder_id::text AS folder_id,
                        f.name AS folder_name,
                        d.title,
                        d.lifecycle_status,
                        d.index_status,
                        d.owner_department_id::text AS owner_department_id,
                        od.name AS owner_department_name,
                        d.visibility,
                        d.current_version_id::text AS current_version_id,
                        dv.version_no AS current_version_no,
                        d.tags,
                        d.permission_snapshot_id::text AS permission_snapshot_id,
                        d.content_hash,
                        COALESCE(ps.policy_version, 1) AS policy_version
                    FROM documents d
                    LEFT JOIN folders f ON f.id = d.folder_id
                    LEFT JOIN departments od ON od.id = d.owner_department_id
                    LEFT JOIN permission_snapshots ps ON ps.id = d.permission_snapshot_id
                    LEFT JOIN document_versions dv ON dv.id = d.current_version_id
                    WHERE {where_sql}
                    ORDER BY d.updated_at DESC, d.title
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    f"""
                    SELECT count(*) AS total
                    FROM documents d
                    WHERE {where_sql}
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENTS_UNAVAILABLE",
                "documents cannot be read",
                exc,
            ) from exc
        return AdminDocumentList(
            items=[_document_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_document(
        self,
        session: Session,
        doc_id: str,
        *,
        enterprise_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDocument:
        self._core_service._ensure_actor_can_manage_documents(actor_context)
        document = self._core_service._load_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
        )
        self._core_service.get_knowledge_base(
            session,
            document.kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        return document

