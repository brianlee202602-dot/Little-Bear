"""Draft index workflow service."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import DraftIndexChunk, IndexTarget
from app.modules.indexing.utils import (
    chunk_index_payload_hash,
    database_error,
    document_version_ids_from_request,
    draft_vector_point,
    is_rebuild_request,
    optional_int,
    source_error,
    vector_id,
)
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class DraftIndexService:
    """Creates draft index versions and writes draft keyword/vector refs."""

    def __init__(self, core) -> None:
        self.core = core

    def create_draft_indexes(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
        embedding_model: str | None = None,
        model_version: str | None = None,
        dimension: int | None = None,
        collection_name: str | None = None,
    ) -> list[str]:
        embedding_model = embedding_model or self.core.embedding_model
        model_version = model_version or self.core.model_version
        dimension = self.core.dimension if dimension is None else dimension
        collection_name = collection_name or self.core.collection_name
        targets = self._load_index_targets(session, request_json=request_json)
        force_rebuild = is_rebuild_request(request_json)
        index_version_ids: list[str] = []
        for target in targets:
            existing = self._load_existing_index_version(
                session,
                enterprise_id=target.enterprise_id,
                document_version_id=target.document_version_id,
                force_rebuild=force_rebuild,
            )
            if existing:
                index_version_ids.append(existing["index_version_id"])
                continue
            if target.chunk_count <= 0:
                raise IndexingServiceError(
                    "INDEX_CHUNKS_REQUIRED",
                    "cannot create index version without draft chunks",
                    status_code=409,
                    details={"document_version_id": target.document_version_id},
                )
            index_version_id = str(uuid.uuid4())
            payload_hash = stable_json_hash(
                {
                    "document_id": target.document_id,
                    "document_version_id": target.document_version_id,
                    "embedding_model": embedding_model,
                    "model_version": model_version,
                    "dimension": dimension,
                    "permission_snapshot_hash": target.permission_snapshot_hash,
                    "chunk_count": target.chunk_count,
                }
            )
            self._insert_index_version(
                session,
                index_version_id=index_version_id,
                target=target,
                embedding_model=embedding_model,
                model_version=model_version,
                dimension=dimension,
                collection_name=collection_name,
                payload_hash=payload_hash,
            )
            self.core._insert_audit_log(
                session,
                enterprise_id=target.enterprise_id,
                event_name="index_version.created",
                resource_id=target.document_id,
                summary={
                    "index_version_id": index_version_id,
                    "document_version_id": target.document_version_id,
                    "chunk_count": target.chunk_count,
                },
            )
            index_version_ids.append(index_version_id)
        return index_version_ids

    def write_draft_indexes(self, session: Session, *, request_json: dict[str, Any]) -> list[str]:
        chunks = self._load_draft_index_chunks(session, request_json=request_json)
        if not chunks:
            raise IndexingServiceError(
                "INDEX_CHUNKS_REQUIRED",
                "cannot write draft index without chunks",
                status_code=409,
            )

        ready_index_ids: set[str] = set()
        for chunk in chunks:
            keyword_id = self._insert_keyword_index(session, chunk=chunk)
            self._insert_chunk_index_ref(session, chunk=chunk, keyword_id=keyword_id)
            ready_index_ids.add(chunk.index_version_id)

        self.write_draft_vector_points(chunks)
        self._mark_index_versions_ready(session, index_version_ids=sorted(ready_index_ids))
        for index_version_id in sorted(ready_index_ids):
            self.core._insert_audit_log(
                session,
                enterprise_id=chunks[0].enterprise_id,
                event_name="index_version.ready",
                resource_id=chunks[0].document_id,
                summary={"index_version_id": index_version_id},
            )
        return sorted(ready_index_ids)

    def _load_index_targets(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> list[IndexTarget]:
        document_version_ids = document_version_ids_from_request(request_json)
        if not document_version_ids:
            raise IndexingServiceError(
                "INDEX_DOCUMENT_VERSIONS_REQUIRED",
                "indexing request does not include document version ids",
                status_code=409,
            )
        try:
            chunk_statuses = ["draft", "active"] if is_rebuild_request(request_json) else ["draft"]
            rows = session.execute(
                text(
                    """
                    SELECT
                        d.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        dv.id::text AS document_version_id,
                        d.created_by::text AS created_by,
                        count(c.id)::integer AS chunk_count,
                        ps.payload_hash AS permission_snapshot_hash
                    FROM document_versions dv
                    JOIN documents d ON d.id = dv.document_id
                    JOIN permission_snapshots ps ON ps.id = d.permission_snapshot_id
                    LEFT JOIN chunks c
                      ON c.document_version_id = dv.id
                     AND c.status = ANY(CAST(:chunk_statuses AS text[]))
                    WHERE dv.id = ANY(CAST(:document_version_ids AS uuid[]))
                      AND dv.status IN ('chunked', 'indexed', 'active')
                      AND d.lifecycle_status IN ('draft', 'active')
                    GROUP BY d.enterprise_id, d.kb_id, d.id, dv.id, d.created_by, ps.payload_hash
                    ORDER BY d.created_at ASC
                    """
                ),
                {"document_version_ids": document_version_ids, "chunk_statuses": chunk_statuses},
            ).all()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_TARGETS_UNAVAILABLE",
                "index targets cannot be read",
                exc,
            ) from exc
        return [
            IndexTarget(
                enterprise_id=row._mapping["enterprise_id"],
                kb_id=row._mapping["kb_id"],
                document_id=row._mapping["document_id"],
                document_version_id=row._mapping["document_version_id"],
                created_by=row._mapping["created_by"],
                chunk_count=int(row._mapping["chunk_count"]),
                permission_snapshot_hash=row._mapping["permission_snapshot_hash"],
            )
            for row in rows
        ]

    def _load_existing_index_version(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_version_id: str,
        force_rebuild: bool = False,
    ) -> dict[str, str] | None:
        statuses = ["draft", "ready"] if force_rebuild else ["draft", "ready", "active"]
        row = session.execute(
            text(
                """
                SELECT id::text AS index_version_id, status
                FROM index_versions
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND document_version_id = CAST(:document_version_id AS uuid)
                  AND status = ANY(CAST(:statuses AS text[]))
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "document_version_id": document_version_id,
                "statuses": statuses,
            },
        ).one_or_none()
        return dict(row._mapping) if row else None

    def _insert_index_version(
        self,
        session: Session,
        *,
        index_version_id: str,
        target: IndexTarget,
        embedding_model: str,
        model_version: str,
        dimension: int,
        collection_name: str,
        payload_hash: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO index_versions(
                    id, enterprise_id, kb_id, document_id, document_version_id,
                    embedding_model, model_version, dimension, collection_name, status,
                    chunk_count, permission_snapshot_hash, payload_hash, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:kb_id AS uuid),
                    CAST(:document_id AS uuid), CAST(:document_version_id AS uuid),
                    :embedding_model, :model_version, :dimension, :collection_name, 'draft',
                    :chunk_count, :permission_snapshot_hash, :payload_hash,
                    CAST(:created_by AS uuid)
                )
                """
            ),
            {
                "id": index_version_id,
                "enterprise_id": target.enterprise_id,
                "kb_id": target.kb_id,
                "document_id": target.document_id,
                "document_version_id": target.document_version_id,
                "embedding_model": embedding_model,
                "model_version": model_version,
                "dimension": dimension,
                "collection_name": collection_name,
                "chunk_count": target.chunk_count,
                "permission_snapshot_hash": target.permission_snapshot_hash,
                "payload_hash": payload_hash,
                "created_by": target.created_by,
            },
        )

    def _load_draft_index_chunks(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> list[DraftIndexChunk]:
        document_version_ids = document_version_ids_from_request(request_json)
        if not document_version_ids:
            raise IndexingServiceError(
                "INDEX_DOCUMENT_VERSIONS_REQUIRED",
                "indexing request does not include document version ids",
                status_code=409,
            )
        try:
            chunk_statuses = ["draft", "active"] if is_rebuild_request(request_json) else ["draft"]
            rows = session.execute(
                text(
                    """
                    SELECT
                        c.enterprise_id::text AS enterprise_id,
                        c.kb_id::text AS kb_id,
                        c.id::text AS chunk_id,
                        c.document_id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        iv.id::text AS index_version_id,
                        d.title,
                        iv.collection_name,
                        c.text_preview AS text,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        ps.permission_version,
                        c.content_hash AS chunk_content_hash,
                        iv.payload_hash AS index_payload_hash,
                        c.page_start,
                        c.page_end
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    JOIN permission_snapshots ps ON ps.id = c.permission_snapshot_id
                    JOIN index_versions iv
                      ON iv.document_version_id = c.document_version_id
                     AND iv.document_id = c.document_id
                     AND iv.status = 'draft'
                    WHERE c.document_version_id = ANY(CAST(:document_version_ids AS uuid[]))
                      AND c.status = ANY(CAST(:chunk_statuses AS text[]))
                    ORDER BY c.document_version_id, c.ordinal
                    """
                ),
                {"document_version_ids": document_version_ids, "chunk_statuses": chunk_statuses},
            ).all()
        except SQLAlchemyError as exc:
            raise database_error(
                "INDEX_CHUNKS_UNAVAILABLE",
                "index chunks cannot be read",
                exc,
            ) from exc
        return [
            DraftIndexChunk(
                enterprise_id=row._mapping["enterprise_id"],
                kb_id=row._mapping["kb_id"],
                chunk_id=row._mapping["chunk_id"],
                document_id=row._mapping["document_id"],
                document_version_id=row._mapping["document_version_id"],
                index_version_id=row._mapping["index_version_id"],
                title=row._mapping["title"],
                collection_name=row._mapping["collection_name"],
                text=row._mapping["text"],
                owner_department_id=row._mapping["owner_department_id"],
                visibility=row._mapping["visibility"],
                indexed_permission_version=int(row._mapping["permission_version"]),
                chunk_content_hash=row._mapping["chunk_content_hash"],
                index_payload_hash=row._mapping["index_payload_hash"],
                page_start=optional_int(row._mapping["page_start"]),
                page_end=optional_int(row._mapping["page_end"]),
            )
            for row in rows
        ]

    def _insert_keyword_index(self, session: Session, *, chunk: DraftIndexChunk) -> str | None:
        keyword_id = str(uuid.uuid4())
        payload_hash = chunk_index_payload_hash(chunk)
        row = session.execute(
            text(
                """
                INSERT INTO keyword_index_entries(
                    id, enterprise_id, chunk_id, document_id, index_version_id,
                    search_text, search_tsv, owner_department_id, visibility,
                    visibility_state, indexed_permission_version, payload_hash
                )
                SELECT
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:chunk_id AS uuid),
                    CAST(:document_id AS uuid), CAST(:index_version_id AS uuid),
                    :search_text, to_tsvector('simple', :search_text),
                    CAST(:owner_department_id AS uuid), :visibility,
                    'draft', :indexed_permission_version, :payload_hash
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM chunk_index_refs
                    WHERE chunk_id = CAST(:chunk_id AS uuid)
                      AND index_version_id = CAST(:index_version_id AS uuid)
                )
                RETURNING id::text AS keyword_id
                """
            ),
            {
                "id": keyword_id,
                "enterprise_id": chunk.enterprise_id,
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "index_version_id": chunk.index_version_id,
                "search_text": chunk.text,
                "owner_department_id": chunk.owner_department_id,
                "visibility": chunk.visibility,
                "indexed_permission_version": chunk.indexed_permission_version,
                "payload_hash": payload_hash,
            },
        ).one_or_none()
        return row._mapping["keyword_id"] if row else self._load_existing_keyword_id(session, chunk)

    def _load_existing_keyword_id(self, session: Session, chunk: DraftIndexChunk) -> str | None:
        row = session.execute(
            text(
                """
                SELECT keyword_id::text AS keyword_id
                FROM chunk_index_refs
                WHERE chunk_id = CAST(:chunk_id AS uuid)
                  AND index_version_id = CAST(:index_version_id AS uuid)
                """
            ),
            {"chunk_id": chunk.chunk_id, "index_version_id": chunk.index_version_id},
        ).one_or_none()
        return row._mapping["keyword_id"] if row else None

    def _insert_chunk_index_ref(
        self,
        session: Session,
        *,
        chunk: DraftIndexChunk,
        keyword_id: str | None,
    ) -> None:
        current_vector_id = vector_id(chunk)
        payload_hash = chunk_index_payload_hash(chunk)
        session.execute(
            text(
                """
                INSERT INTO chunk_index_refs(
                    id, enterprise_id, chunk_id, index_version_id, vector_id, keyword_id,
                    visibility_state, indexed_permission_version, payload_hash
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:chunk_id AS uuid),
                    CAST(:index_version_id AS uuid), :vector_id, CAST(:keyword_id AS uuid),
                    'draft', :indexed_permission_version, :payload_hash
                )
                ON CONFLICT (vector_id) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": chunk.enterprise_id,
                "chunk_id": chunk.chunk_id,
                "index_version_id": chunk.index_version_id,
                "vector_id": current_vector_id,
                "keyword_id": keyword_id,
                "indexed_permission_version": chunk.indexed_permission_version,
                "payload_hash": payload_hash,
            },
        )

    def _mark_index_versions_ready(self, session: Session, *, index_version_ids: list[str]) -> None:
        session.execute(
            text(
                """
                UPDATE index_versions
                SET status = 'ready'
                WHERE id = ANY(CAST(:index_version_ids AS uuid[]))
                  AND status = 'draft'
                  AND chunk_count = (
                      SELECT count(*)
                      FROM chunk_index_refs cir
                      WHERE cir.index_version_id = index_versions.id
                        AND cir.visibility_state = 'draft'
                  )
                """
            ),
            {"index_version_ids": index_version_ids},
        )

    def write_draft_vector_points(self, chunks) -> None:
        points = tuple(draft_vector_point(chunk) for chunk in chunks)
        try:
            self.core.vector_index_writer.upsert_draft_points(points)
        except Exception as exc:
            raise IndexingServiceError(
                "INDEX_VECTOR_WRITE_FAILED",
                "draft vector points cannot be written",
                status_code=503,
                retryable=True,
                details={
                    "point_count": len(points),
                    "source_error": source_error(exc),
                },
            ) from exc
