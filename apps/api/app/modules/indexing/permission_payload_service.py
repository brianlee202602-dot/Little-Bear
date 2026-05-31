"""Index permission payload refresh workflow service."""

from __future__ import annotations

from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.utils import (
    PermissionRefreshTarget,
    database_error,
    optional_int,
    optional_str,
    permission_refresh_payload_hash,
    required_int,
    required_str,
    source_error,
    vector_payload_update,
)
from app.modules.indexing.writers import NoopVectorIndexWriter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class PermissionPayloadRefreshService:
    """Refreshes permission payloads for active keyword/vector index entries."""

    def __init__(self, core) -> None:
        self.core = core

    def refresh_permission_payloads(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> dict[str, int]:
        enterprise_id = required_str(request_json, "enterprise_id")
        resource_type = required_str(request_json, "resource_type")
        permission_version = required_int(request_json, "permission_version")
        if resource_type not in {"document", "knowledge_base"}:
            raise IndexingServiceError(
                "INDEX_PERMISSION_REFRESH_RESOURCE_INVALID",
                "permission refresh resource type is invalid",
                status_code=409,
                details={"resource_type": resource_type},
            )
        document_id = optional_str(request_json, "document_id")
        kb_id = optional_str(request_json, "kb_id")
        if resource_type == "document" and not document_id:
            raise IndexingServiceError(
                "INDEX_PERMISSION_REFRESH_DOCUMENT_REQUIRED",
                "permission refresh request does not include document_id",
                status_code=409,
            )
        if resource_type == "knowledge_base" and not kb_id:
            raise IndexingServiceError(
                "INDEX_PERMISSION_REFRESH_KB_REQUIRED",
                "permission refresh request does not include kb_id",
                status_code=409,
            )

        targets = self._load_permission_refresh_targets(
            session,
            enterprise_id=enterprise_id,
            resource_type=resource_type,
            resource_id=document_id if resource_type == "document" else kb_id,
            permission_version=permission_version,
        )
        self._update_index_permission_payloads(session, targets=targets)
        self._release_permission_tightened_blocks(
            session,
            enterprise_id=enterprise_id,
            resource_type=resource_type,
            resource_id=document_id if resource_type == "document" else kb_id,
        )
        self._update_vector_permission_payloads(targets)
        self.core._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            event_name="index_permission_payload.refreshed",
            resource_id=document_id or kb_id or "unknown",
            summary={
                "resource_type": resource_type,
                "resource_id": document_id or kb_id,
                "permission_version": permission_version,
                "chunk_count": len(targets),
                "vector_payload_count": len(targets),
            },
        )
        return {"chunk_count": len(targets), "vector_payload_count": len(targets)}

    def _load_permission_refresh_targets(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str | None,
        permission_version: int,
    ) -> list[PermissionRefreshTarget]:
        if resource_id is None:
            return []
        resource_predicate = (
            "d.id = CAST(:resource_id AS uuid)"
            if resource_type == "document"
            else "d.kb_id = CAST(:resource_id AS uuid)"
        )
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        d.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        iv.id::text AS index_version_id,
                        iv.collection_name,
                        cir.vector_id,
                        cir.keyword_id::text AS keyword_id,
                        c.id::text AS chunk_id,
                        d.title,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        GREATEST(ps.permission_version, :permission_version)::integer
                            AS indexed_permission_version,
                        iv.payload_hash AS index_payload_hash,
                        d.lifecycle_status AS document_status,
                        d.index_status AS document_index_status,
                        c.status AS chunk_status,
                        c.page_start,
                        c.page_end
                    FROM documents d
                    JOIN permission_snapshots ps ON ps.id = d.permission_snapshot_id
                    JOIN index_versions iv
                      ON iv.document_id = d.id
                     AND iv.status = 'active'
                    JOIN chunks c
                      ON c.document_id = d.id
                     AND c.document_version_id = iv.document_version_id
                     AND c.status = 'active'
                    JOIN chunk_index_refs cir
                      ON cir.chunk_id = c.id
                     AND cir.index_version_id = iv.id
                     AND cir.visibility_state IN ('active', 'blocked')
                    WHERE d.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND {resource_predicate}
                      AND d.deleted_at IS NULL
                      AND d.lifecycle_status != 'deleted'
                    ORDER BY d.id, c.ordinal
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "resource_id": resource_id,
                    "permission_version": permission_version,
                },
            ).all()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_PERMISSION_REFRESH_TARGETS_UNAVAILABLE",
                "permission refresh targets cannot be read",
                exc,
            ) from exc
        return [
            PermissionRefreshTarget(
                enterprise_id=row._mapping["enterprise_id"],
                kb_id=row._mapping["kb_id"],
                document_id=row._mapping["document_id"],
                document_version_id=row._mapping["document_version_id"],
                index_version_id=row._mapping["index_version_id"],
                collection_name=row._mapping["collection_name"],
                vector_id=row._mapping["vector_id"],
                keyword_id=row._mapping["keyword_id"],
                chunk_id=row._mapping["chunk_id"],
                title=row._mapping["title"],
                owner_department_id=row._mapping["owner_department_id"],
                visibility=row._mapping["visibility"],
                indexed_permission_version=int(row._mapping["indexed_permission_version"]),
                index_payload_hash=row._mapping["index_payload_hash"],
                document_status=row._mapping["document_status"],
                document_index_status=row._mapping["document_index_status"],
                chunk_status=row._mapping["chunk_status"],
                page_start=optional_int(row._mapping["page_start"]),
                page_end=optional_int(row._mapping["page_end"]),
            )
            for row in rows
        ]

    def _update_vector_permission_payloads(
        self,
        targets: list[PermissionRefreshTarget],
    ) -> None:
        if isinstance(self.core.vector_index_writer, NoopVectorIndexWriter):
            return
        updates = tuple(vector_payload_update(target) for target in targets)
        if not updates:
            return
        try:
            self.core.vector_index_writer.update_payloads(updates)
        except Exception as exc:
            raise IndexingServiceError(
                "INDEX_PERMISSION_VECTOR_REFRESH_FAILED",
                "vector permission payload cannot be refreshed",
                status_code=503,
                retryable=True,
                details={
                    "point_count": len(updates),
                    "source_error": source_error(exc),
                },
            ) from exc

    def _update_index_permission_payloads(
        self,
        session: Session,
        *,
        targets: list[PermissionRefreshTarget],
    ) -> None:
        document_ids = sorted({target.document_id for target in targets})
        if document_ids:
            session.execute(
                text(
                    """
                    UPDATE chunks c
                    SET permission_snapshot_id = d.permission_snapshot_id,
                        updated_at = now()
                    FROM documents d
                    WHERE c.document_id = d.id
                      AND d.id = ANY(CAST(:document_ids AS uuid[]))
                      AND c.status = 'active'
                    """
                ),
                {"document_ids": document_ids},
            )
        for target in targets:
            payload_hash = permission_refresh_payload_hash(target)
            if target.keyword_id:
                session.execute(
                    text(
                        """
                        UPDATE keyword_index_entries
                        SET owner_department_id = CAST(:owner_department_id AS uuid),
                            visibility = :visibility,
                            visibility_state = 'active',
                            indexed_permission_version = :indexed_permission_version,
                            payload_hash = :payload_hash,
                            updated_at = now()
                        WHERE id = CAST(:keyword_id AS uuid)
                        """
                    ),
                    {
                        "keyword_id": target.keyword_id,
                        "owner_department_id": target.owner_department_id,
                        "visibility": target.visibility,
                        "indexed_permission_version": target.indexed_permission_version,
                        "payload_hash": payload_hash,
                    },
                )
            session.execute(
                text(
                    """
                    UPDATE chunk_index_refs
                    SET visibility_state = 'active',
                        indexed_permission_version = :indexed_permission_version,
                        payload_hash = :payload_hash,
                        updated_at = now()
                    WHERE vector_id = :vector_id
                    """
                ),
                {
                    "vector_id": target.vector_id,
                    "indexed_permission_version": target.indexed_permission_version,
                    "payload_hash": payload_hash,
                },
            )

    def _release_permission_tightened_blocks(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str | None,
    ) -> None:
        if resource_id is None:
            return
        session.execute(
            text(
                """
                UPDATE access_blocks
                SET status = 'released',
                    released_at = now()
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND resource_type = :resource_type
                  AND resource_id = CAST(:resource_id AS uuid)
                  AND reason = 'permission_tightened'
                  AND status = 'active'
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
