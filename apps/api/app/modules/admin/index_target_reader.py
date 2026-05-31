"""Index operation target readers for admin services."""

from __future__ import annotations

from app.modules.admin.mappers import (
    _index_cleanup_target_from_mapping,
    _index_rebuild_target_from_mapping,
    _IndexCleanupTarget,
    _IndexRebuildTarget,
)
from app.modules.admin.utils import _database_error
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminIndexTargetReader:
    """读取索引重建和清理任务的目标集合。"""

    def load_rebuild_targets_for_kb(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
    ) -> list[_IndexRebuildTarget]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS document_id,
                        kb_id::text AS kb_id,
                        current_version_id::text AS document_version_id
                    FROM documents
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = CAST(:kb_id AS uuid)
                      AND lifecycle_status = 'active'
                      AND index_status IN ('indexed', 'index_failed')
                      AND current_version_id IS NOT NULL
                      AND deleted_at IS NULL
                    ORDER BY updated_at DESC, id
                    """
                ),
                {"enterprise_id": enterprise_id, "kb_id": kb_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_REBUILD_TARGETS_UNAVAILABLE",
                "index rebuild targets cannot be read",
                exc,
            ) from exc
        return [_index_rebuild_target_from_mapping(row._mapping) for row in rows]

    def load_rebuild_targets_for_documents(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_ids: list[str],
    ) -> list[_IndexRebuildTarget]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS document_id,
                        kb_id::text AS kb_id,
                        current_version_id::text AS document_version_id
                    FROM documents
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND id = ANY(CAST(:document_ids AS uuid[]))
                      AND lifecycle_status = 'active'
                      AND index_status IN ('indexed', 'index_failed')
                      AND current_version_id IS NOT NULL
                      AND deleted_at IS NULL
                    ORDER BY updated_at DESC, id
                    """
                ),
                {"enterprise_id": enterprise_id, "document_ids": document_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_REBUILD_TARGETS_UNAVAILABLE",
                "index rebuild targets cannot be read",
                exc,
            ) from exc
        return [_index_rebuild_target_from_mapping(row._mapping) for row in rows]

    def load_rebuild_targets_for_collection(
        self,
        session: Session,
        *,
        enterprise_id: str,
        collection_name: str,
    ) -> list[_IndexRebuildTarget]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS document_id,
                        d.kb_id::text AS kb_id,
                        d.current_version_id::text AS document_version_id
                    FROM documents d
                    JOIN index_versions iv
                      ON iv.enterprise_id = d.enterprise_id
                     AND iv.document_id = d.id
                     AND iv.document_version_id = d.current_version_id
                    WHERE d.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND iv.collection_name = :collection_name
                      AND iv.status = 'active'
                      AND d.lifecycle_status = 'active'
                      AND d.index_status IN ('indexed', 'index_failed')
                      AND d.current_version_id IS NOT NULL
                      AND d.deleted_at IS NULL
                    ORDER BY d.updated_at DESC, d.id
                    """
                ),
                {"enterprise_id": enterprise_id, "collection_name": collection_name},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_REBUILD_TARGETS_UNAVAILABLE",
                "index rebuild targets cannot be read",
                exc,
            ) from exc
        return [_index_rebuild_target_from_mapping(row._mapping) for row in rows]

    def load_cleanup_targets(
        self,
        session: Session,
        *,
        enterprise_id: str,
        index_version_ids: list[str],
    ) -> list[_IndexCleanupTarget]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        iv.id::text AS index_version_id,
                        iv.document_id::text AS document_id,
                        iv.kb_id::text AS kb_id,
                        iv.document_version_id::text AS document_version_id,
                        iv.collection_name,
                        iv.status
                    FROM index_versions iv
                    JOIN documents d
                      ON d.enterprise_id = iv.enterprise_id
                     AND d.id = iv.document_id
                    WHERE iv.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND iv.id = ANY(CAST(:index_version_ids AS uuid[]))
                      AND iv.status = 'pending_delete'
                      AND d.deleted_at IS NULL
                    ORDER BY iv.created_at ASC, iv.id
                    """
                ),
                {"enterprise_id": enterprise_id, "index_version_ids": index_version_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_CLEANUP_TARGETS_UNAVAILABLE",
                "index cleanup targets cannot be read",
                exc,
            ) from exc
        return [_index_cleanup_target_from_mapping(row._mapping) for row in rows]

