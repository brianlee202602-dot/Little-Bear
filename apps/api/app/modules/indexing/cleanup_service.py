"""Pending-delete index cleanup workflow service."""

from __future__ import annotations

from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import VectorPayloadUpdate
from app.modules.indexing.utils import (
    database_error,
    document_ids_from_request,
    group_vector_ids_by_collection,
    index_version_ids_from_request,
    optional_str,
    source_error,
)
from app.modules.indexing.writers import NoopVectorIndexWriter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class IndexCleanupService:
    """Cleans logical and physical remnants of pending-delete index versions."""

    def __init__(self, core) -> None:
        self.core = core

    def cleanup_pending_delete_indexes(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> dict[str, int]:
        targets = self._load_pending_delete_index_refs(session, request_json=request_json)
        self._mark_vector_points_deleted(targets)
        index_version_ids = sorted({target["index_version_id"] for target in targets})
        if not index_version_ids:
            return {
                "index_version_count": 0,
                "vector_payload_count": 0,
                "vector_physical_delete_count": 0,
            }
        try:
            session.execute(
                text(
                    """
                    UPDATE keyword_index_entries
                    SET visibility_state = 'deleted',
                        updated_at = now()
                    WHERE index_version_id = ANY(CAST(:index_version_ids AS uuid[]))
                      AND visibility_state != 'deleted'
                    """
                ),
                {"index_version_ids": index_version_ids},
            )
            session.execute(
                text(
                    """
                    UPDATE chunk_index_refs
                    SET visibility_state = 'deleted',
                        updated_at = now()
                    WHERE index_version_id = ANY(CAST(:index_version_ids AS uuid[]))
                      AND visibility_state != 'deleted'
                    """
                ),
                {"index_version_ids": index_version_ids},
            )
            session.execute(
                text(
                    """
                    UPDATE index_versions
                    SET status = 'archived'
                    WHERE id = ANY(CAST(:index_version_ids AS uuid[]))
                      AND status = 'pending_delete'
                    """
                ),
                {"index_version_ids": index_version_ids},
            )
            physical_delete_count = self._delete_vector_points(targets)
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_CLEANUP_FAILED",
                "pending delete indexes cannot be cleaned",
                exc,
            ) from exc
        if targets:
            self.core._insert_audit_log(
                session,
                enterprise_id=targets[0]["enterprise_id"],
                event_name="index_version.cleaned",
                resource_id=targets[0]["document_id"],
                summary={
                    "index_version_ids": index_version_ids,
                    "vector_payload_count": len(targets),
                    "vector_physical_delete_count": physical_delete_count,
                },
            )
        return {
            "index_version_count": len(index_version_ids),
            "vector_payload_count": len(targets),
            "vector_physical_delete_count": physical_delete_count,
        }

    def _load_pending_delete_index_refs(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> list[dict[str, str]]:
        index_version_ids = index_version_ids_from_request(request_json)
        document_ids = document_ids_from_request(request_json)
        kb_id = optional_str(request_json, "kb_id")
        conditions = ["iv.status = 'pending_delete'"]
        params: dict[str, Any] = {}
        if index_version_ids:
            conditions.append("iv.id = ANY(CAST(:index_version_ids AS uuid[]))")
            params["index_version_ids"] = index_version_ids
        elif document_ids:
            conditions.append("iv.document_id = ANY(CAST(:document_ids AS uuid[]))")
            params["document_ids"] = document_ids
        elif kb_id:
            conditions.append("iv.kb_id = CAST(:kb_id AS uuid)")
            params["kb_id"] = kb_id
        else:
            return []
        where_sql = " AND ".join(conditions)
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        iv.enterprise_id::text AS enterprise_id,
                        iv.document_id::text AS document_id,
                        iv.id::text AS index_version_id,
                        iv.collection_name,
                        cir.vector_id
                    FROM index_versions iv
                    JOIN chunk_index_refs cir ON cir.index_version_id = iv.id
                    WHERE {where_sql}
                      AND cir.visibility_state != 'deleted'
                    ORDER BY iv.created_at ASC, cir.created_at ASC
                    """
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_CLEANUP_TARGETS_UNAVAILABLE",
                "pending delete index cleanup targets cannot be read",
                exc,
            ) from exc
        return [dict(row._mapping) for row in rows]

    def _mark_vector_points_deleted(self, targets: list[dict[str, str]]) -> None:
        if isinstance(self.core.vector_index_writer, NoopVectorIndexWriter) or not targets:
            return
        updates = tuple(
            VectorPayloadUpdate(
                collection_name=target["collection_name"],
                vector_id=target["vector_id"],
                payload={
                    "visibility_state": "deleted",
                    "document_status": "deleted",
                    "document_index_status": "blocked",
                    "chunk_status": "deleted",
                    "is_deleted": True,
                },
            )
            for target in targets
        )
        try:
            self.core.vector_index_writer.update_payloads(updates)
        except Exception as exc:
            raise IndexingServiceError(
                "INDEX_VECTOR_CLEANUP_FAILED",
                "pending delete vector payloads cannot be cleaned",
                status_code=503,
                retryable=True,
                details={
                    "point_count": len(updates),
                    "source_error": source_error(exc),
                },
            ) from exc

    def _delete_vector_points(self, targets: list[dict[str, str]]) -> int:
        if isinstance(self.core.vector_index_writer, NoopVectorIndexWriter) or not targets:
            return 0
        deleted_count = 0
        try:
            for collection_name, vector_ids in group_vector_ids_by_collection(targets).items():
                self.core.vector_index_writer.delete_points(
                    collection_name=collection_name,
                    vector_ids=tuple(vector_ids),
                )
                deleted_count += len(vector_ids)
        except Exception as exc:
            raise IndexingServiceError(
                "INDEX_VECTOR_PHYSICAL_DELETE_FAILED",
                "pending delete vector points cannot be physically deleted",
                status_code=503,
                retryable=True,
                details={
                    "point_count": len(targets),
                    "source_error": source_error(exc),
                },
            ) from exc
        return deleted_count
