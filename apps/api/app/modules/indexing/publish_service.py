"""Ready index publish workflow service."""

from __future__ import annotations

from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import ReadyIndexVersion
from app.modules.indexing.utils import (
    database_error,
    document_version_ids_from_request,
    source_error,
)
from app.modules.indexing.writers import NoopVectorIndexWriter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class IndexPublishService:
    """Publishes ready index versions and switches active document/index state."""

    def __init__(self, core) -> None:
        self.core = core

    def publish_ready_indexes(self, session: Session, *, request_json: dict[str, Any]) -> list[str]:
        versions = self._load_ready_index_versions(session, request_json=request_json)
        if not versions:
            raise IndexingServiceError(
                "INDEX_READY_VERSION_REQUIRED",
                "no ready index version can be published",
                status_code=409,
            )

        published: list[str] = []
        for version in versions:
            self._validate_publish_preflight(session, version=version)
            self._activate_vector_points(session, version=version)
            self._archive_previous_active(session, version=version)
            self._activate_index_version(session, version=version)
            self._activate_document_version(session, version=version)
            self._activate_document(session, version=version)
            self._activate_chunks(session, version=version)
            self._activate_index_refs(session, version=version)
            self._activate_keyword_entries(session, version=version)
            self.core._insert_audit_log(
                session,
                enterprise_id=version.enterprise_id,
                event_name="index_version.activated",
                resource_id=version.document_id,
                summary={
                    "index_version_id": version.index_version_id,
                    "document_version_id": version.document_version_id,
                },
            )
            published.append(version.index_version_id)
        return published

    def _load_ready_index_versions(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> list[ReadyIndexVersion]:
        document_version_ids = document_version_ids_from_request(request_json)
        if not document_version_ids:
            raise IndexingServiceError(
                "INDEX_DOCUMENT_VERSIONS_REQUIRED",
                "indexing request does not include document version ids",
                status_code=409,
            )
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        iv.enterprise_id::text AS enterprise_id,
                        iv.kb_id::text AS kb_id,
                        iv.document_id::text AS document_id,
                        iv.document_version_id::text AS document_version_id,
                        iv.id::text AS index_version_id,
                        iv.collection_name,
                        iv.dimension,
                        iv.chunk_count,
                        ps.permission_version
                    FROM index_versions iv
                    JOIN documents d ON d.id = iv.document_id
                    JOIN permission_snapshots ps ON ps.id = d.permission_snapshot_id
                    WHERE iv.document_version_id = ANY(CAST(:document_version_ids AS uuid[]))
                      AND iv.status = 'ready'
                      AND iv.chunk_count > 0
                      AND iv.permission_snapshot_hash = ps.payload_hash
                    ORDER BY iv.created_at ASC
                    """
                ),
                {"document_version_ids": document_version_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_READY_VERSIONS_UNAVAILABLE",
                "ready index versions cannot be read",
                exc,
            ) from exc
        return [
            ReadyIndexVersion(
                enterprise_id=row._mapping["enterprise_id"],
                kb_id=row._mapping["kb_id"],
                document_id=row._mapping["document_id"],
                document_version_id=row._mapping["document_version_id"],
                index_version_id=row._mapping["index_version_id"],
                collection_name=row._mapping["collection_name"],
                dimension=int(row._mapping["dimension"]),
                chunk_count=int(row._mapping["chunk_count"]),
                permission_version=int(row._mapping["permission_version"]),
            )
            for row in rows
        ]

    def _validate_publish_preflight(self, session: Session, *, version: ReadyIndexVersion) -> None:
        row = self._load_publish_preflight(session, version=version)
        expected_chunk_count = int(row["expected_chunk_count"])
        draft_chunk_count = int(row["draft_chunk_count"])
        draft_vector_ref_count = int(row["draft_vector_ref_count"])

        if expected_chunk_count != version.chunk_count:
            raise IndexingServiceError(
                "INDEX_CHUNK_COUNT_MISMATCH",
                "ready index chunk count changed before publish",
                status_code=409,
                details={
                    "index_version_id": version.index_version_id,
                    "loaded_chunk_count": version.chunk_count,
                    "current_chunk_count": expected_chunk_count,
                },
            )
        if draft_chunk_count != expected_chunk_count:
            raise IndexingServiceError(
                "INDEX_CHUNK_COUNT_MISMATCH",
                "draft chunk count does not match ready index chunk count",
                status_code=409,
                details={
                    "index_version_id": version.index_version_id,
                    "expected_chunk_count": expected_chunk_count,
                    "draft_chunk_count": draft_chunk_count,
                },
            )
        if draft_vector_ref_count != expected_chunk_count:
            raise IndexingServiceError(
                "INDEX_VECTOR_REFS_INCOMPLETE",
                "draft vector ref count does not match ready index chunk count",
                status_code=409,
                details={
                    "index_version_id": version.index_version_id,
                    "expected_chunk_count": expected_chunk_count,
                    "draft_vector_ref_count": draft_vector_ref_count,
                },
            )
        if self.core.dimension > 0 and version.dimension != self.core.dimension:
            raise IndexingServiceError(
                "INDEX_DIMENSION_MISMATCH",
                "ready index embedding dimension does not match active config",
                status_code=409,
                details={
                    "index_version_id": version.index_version_id,
                    "index_dimension": version.dimension,
                    "active_config_dimension": self.core.dimension,
                },
            )
        self._validate_permission_payload(session, version=version)

    def _load_publish_preflight(
        self,
        session: Session,
        *,
        version: ReadyIndexVersion,
    ) -> dict[str, int]:
        try:
            chunk_statuses = ["draft", "active"]
            row = session.execute(
                text(
                    """
                    SELECT
                        iv.chunk_count::integer AS expected_chunk_count,
                        (
                            SELECT count(*)::integer
                            FROM chunks c
                            WHERE c.document_version_id = iv.document_version_id
                              AND c.status = ANY(CAST(:chunk_statuses AS text[]))
                        ) AS draft_chunk_count,
                        (
                            SELECT count(*)::integer
                            FROM chunk_index_refs cir
                            WHERE cir.index_version_id = iv.id
                              AND cir.visibility_state = 'draft'
                        ) AS draft_vector_ref_count
                    FROM index_versions iv
                    WHERE iv.id = CAST(:index_version_id AS uuid)
                      AND iv.status = 'ready'
                    """
                ),
                {"index_version_id": version.index_version_id, "chunk_statuses": chunk_statuses},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_PUBLISH_PREFLIGHT_UNAVAILABLE",
                "publish preflight facts cannot be read",
                exc,
            ) from exc
        if row is None:
            raise IndexingServiceError(
                "INDEX_READY_VERSION_REQUIRED",
                "ready index version disappeared before publish",
                status_code=409,
                details={"index_version_id": version.index_version_id},
            )
        return {
            "expected_chunk_count": int(row._mapping["expected_chunk_count"]),
            "draft_chunk_count": int(row._mapping["draft_chunk_count"]),
            "draft_vector_ref_count": int(row._mapping["draft_vector_ref_count"]),
        }

    def _validate_permission_payload(self, session: Session, *, version: ReadyIndexVersion) -> None:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        count(*)::integer AS payload_count,
                        count(*) FILTER (
                            WHERE owner_department_id IS NOT NULL
                              AND visibility IN ('department', 'enterprise')
                        )::integer AS valid_payload_count
                    FROM keyword_index_entries
                    WHERE index_version_id = CAST(:index_version_id AS uuid)
                      AND visibility_state = 'draft'
                    """
                ),
                {"index_version_id": version.index_version_id},
            ).one()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_PERMISSION_PAYLOAD_UNAVAILABLE",
                "keyword index permission payload cannot be read",
                exc,
            ) from exc
        payload_count = int(row._mapping["payload_count"])
        valid_payload_count = int(row._mapping["valid_payload_count"])
        if payload_count != version.chunk_count or valid_payload_count != payload_count:
            raise IndexingServiceError(
                "INDEX_PERMISSION_PAYLOAD_INVALID",
                "draft keyword payload is missing permission fields",
                status_code=409,
                details={
                    "index_version_id": version.index_version_id,
                    "payload_count": payload_count,
                    "valid_payload_count": valid_payload_count,
                    "expected_chunk_count": version.chunk_count,
                },
            )

    def _activate_vector_points(self, session: Session, *, version: ReadyIndexVersion) -> None:
        if isinstance(self.core.vector_index_writer, NoopVectorIndexWriter):
            return
        vector_ids = self._load_draft_vector_ids(session, index_version_id=version.index_version_id)
        if not vector_ids:
            raise IndexingServiceError(
                "INDEX_VECTOR_REFS_REQUIRED",
                "ready index version does not have draft vector refs",
                status_code=409,
                details={"index_version_id": version.index_version_id},
            )
        try:
            self.core.vector_index_writer.activate_points(
                collection_name=version.collection_name,
                vector_ids=vector_ids,
                permission_version=version.permission_version,
            )
        except Exception as exc:
            raise IndexingServiceError(
                "INDEX_VECTOR_PUBLISH_FAILED",
                "vector points cannot be activated",
                status_code=503,
                retryable=True,
                details={
                    "index_version_id": version.index_version_id,
                    "collection_name": version.collection_name,
                    "point_count": len(vector_ids),
                    "source_error": source_error(exc),
                },
            ) from exc

    def _load_draft_vector_ids(
        self,
        session: Session,
        *,
        index_version_id: str,
    ) -> tuple[str, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT vector_id
                    FROM chunk_index_refs
                    WHERE index_version_id = CAST(:index_version_id AS uuid)
                      AND visibility_state = 'draft'
                    ORDER BY created_at ASC, vector_id ASC
                    """
                ),
                {"index_version_id": index_version_id},
            ).all()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_VECTOR_REFS_UNAVAILABLE",
                "draft vector refs cannot be read",
                exc,
            ) from exc
        return tuple(str(row._mapping["vector_id"]) for row in rows)

    def _archive_previous_active(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE index_versions
                SET status = 'pending_delete'
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND document_id = CAST(:document_id AS uuid)
                  AND status = 'active'
                  AND id != CAST(:index_version_id AS uuid)
                """
            ),
            {
                "enterprise_id": version.enterprise_id,
                "document_id": version.document_id,
                "index_version_id": version.index_version_id,
            },
        )

    def _activate_index_version(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE index_versions
                SET status = 'active',
                    activated_at = now()
                WHERE id = CAST(:index_version_id AS uuid)
                  AND status = 'ready'
                """
            ),
            {"index_version_id": version.index_version_id},
        )

    def _activate_document_version(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE document_versions
                SET status = 'archived'
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND document_id = CAST(:document_id AS uuid)
                  AND status = 'active'
                  AND id != CAST(:document_version_id AS uuid)
                """
            ),
            {
                "enterprise_id": version.enterprise_id,
                "document_id": version.document_id,
                "document_version_id": version.document_version_id,
            },
        )
        session.execute(
            text(
                """
                UPDATE document_versions
                SET status = 'active',
                    activated_at = now()
                WHERE id = CAST(:document_version_id AS uuid)
                  AND status IN ('chunked', 'indexed')
                """
            ),
            {"document_version_id": version.document_version_id},
        )

    def _activate_document(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE documents
                SET current_version_id = CAST(:document_version_id AS uuid),
                    lifecycle_status = 'active',
                    index_status = 'indexed',
                    updated_at = now()
                WHERE id = CAST(:document_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                """
            ),
            {
                "enterprise_id": version.enterprise_id,
                "document_id": version.document_id,
                "document_version_id": version.document_version_id,
            },
        )

    def _activate_chunks(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE chunks
                SET status = 'active',
                    updated_at = now()
                WHERE document_version_id = CAST(:document_version_id AS uuid)
                  AND status = 'draft'
                """
            ),
            {"document_version_id": version.document_version_id},
        )

    def _activate_index_refs(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE chunk_index_refs
                SET visibility_state = 'active',
                    indexed_permission_version = :permission_version,
                    updated_at = now()
                WHERE index_version_id = CAST(:index_version_id AS uuid)
                  AND visibility_state = 'draft'
                """
            ),
            {
                "index_version_id": version.index_version_id,
                "permission_version": version.permission_version,
            },
        )

    def _activate_keyword_entries(self, session: Session, *, version: ReadyIndexVersion) -> None:
        session.execute(
            text(
                """
                UPDATE keyword_index_entries
                SET visibility_state = 'active',
                    indexed_permission_version = :permission_version,
                    updated_at = now()
                WHERE index_version_id = CAST(:index_version_id AS uuid)
                  AND visibility_state = 'draft'
                """
            ),
            {
                "index_version_id": version.index_version_id,
                "permission_version": version.permission_version,
            },
        )
