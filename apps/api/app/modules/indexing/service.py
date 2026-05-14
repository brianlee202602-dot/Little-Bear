"""Indexing Service P0 实现。

服务负责维护 index_versions / chunk_index_refs 事实账本、PostgreSQL 关键词索引，
并通过向量写入端口把 draft point 写入外部 VectorStore。
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Protocol

from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import (
    DraftIndexChunk,
    DraftVectorPoint,
    IndexTarget,
    ReadyIndexVersion,
)
from app.shared.context import get_request_context
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

DEFAULT_EMBEDDING_MODEL = "p0-placeholder-embedding"
DEFAULT_MODEL_VERSION = "p0"
DEFAULT_DIMENSION = 0
DEFAULT_COLLECTION = "little_bear_p0"
VECTOR_ID_NAMESPACE = uuid.UUID("93b57e36-2c2a-4f74-9f56-e9cdb2a9c3c2")


class VectorIndexWriter(Protocol):
    """索引侧向量写入端口。"""

    def upsert_draft_points(self, points: tuple[DraftVectorPoint, ...]) -> None:
        ...

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        ...


class NoopVectorIndexWriter:
    """本地最小链路默认不触碰外部 VectorStore。"""

    def upsert_draft_points(self, points: tuple[DraftVectorPoint, ...]) -> None:
        return None

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        return None


class IndexingService:
    """索引版本创建、draft 索引写入和 active 发布。"""

    def __init__(
        self,
        *,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        model_version: str = DEFAULT_MODEL_VERSION,
        dimension: int = DEFAULT_DIMENSION,
        collection_name: str = DEFAULT_COLLECTION,
        vector_index_writer: VectorIndexWriter | None = None,
    ) -> None:
        self.embedding_model = embedding_model
        self.model_version = model_version
        self.dimension = dimension
        self.collection_name = collection_name
        self.vector_index_writer = vector_index_writer or NoopVectorIndexWriter()

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
        embedding_model = embedding_model or self.embedding_model
        model_version = model_version or self.model_version
        dimension = self.dimension if dimension is None else dimension
        collection_name = collection_name or self.collection_name
        targets = self._load_index_targets(session, request_json=request_json)
        index_version_ids: list[str] = []
        for target in targets:
            existing = self._load_existing_index_version(
                session,
                enterprise_id=target.enterprise_id,
                document_version_id=target.document_version_id,
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
            self._insert_audit_log(
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

        self._write_draft_vector_points(chunks)
        self._mark_index_versions_ready(session, index_version_ids=sorted(ready_index_ids))
        for index_version_id in sorted(ready_index_ids):
            self._insert_audit_log(
                session,
                enterprise_id=chunks[0].enterprise_id,
                event_name="index_version.ready",
                resource_id=chunks[0].document_id,
                summary={"index_version_id": index_version_id},
            )
        return sorted(ready_index_ids)

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
            self._insert_audit_log(
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

    def _load_index_targets(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> list[IndexTarget]:
        document_version_ids = _document_version_ids_from_request(request_json)
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
                     AND c.status = 'draft'
                    WHERE dv.id = ANY(CAST(:document_version_ids AS uuid[]))
                      AND dv.status IN ('chunked', 'indexed', 'active')
                      AND d.lifecycle_status IN ('draft', 'active')
                    GROUP BY d.enterprise_id, d.kb_id, d.id, dv.id, d.created_by, ps.payload_hash
                    ORDER BY d.created_at ASC
                    """
                ),
                {"document_version_ids": document_version_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
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
    ) -> dict[str, str] | None:
        row = session.execute(
            text(
                """
                SELECT id::text AS index_version_id, status
                FROM index_versions
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND document_version_id = CAST(:document_version_id AS uuid)
                  AND status IN ('draft', 'ready', 'active')
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"enterprise_id": enterprise_id, "document_version_id": document_version_id},
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
        document_version_ids = _document_version_ids_from_request(request_json)
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
                      AND c.status = 'draft'
                    ORDER BY c.document_version_id, c.ordinal
                    """
                ),
                {"document_version_ids": document_version_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
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
                page_start=_optional_int(row._mapping["page_start"]),
                page_end=_optional_int(row._mapping["page_end"]),
            )
            for row in rows
        ]

    def _insert_keyword_index(self, session: Session, *, chunk: DraftIndexChunk) -> str:
        keyword_id = str(uuid.uuid4())
        payload_hash = _chunk_index_payload_hash(chunk)
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
        vector_id = _vector_id(chunk)
        payload_hash = _chunk_index_payload_hash(chunk)
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
                "vector_id": vector_id,
                "keyword_id": keyword_id,
                "indexed_permission_version": chunk.indexed_permission_version,
                "payload_hash": payload_hash,
            },
        )

    def _write_draft_vector_points(self, chunks: list[DraftIndexChunk]) -> None:
        points = tuple(_draft_vector_point(chunk) for chunk in chunks)
        try:
            self.vector_index_writer.upsert_draft_points(points)
        except Exception as exc:
            raise IndexingServiceError(
                "INDEX_VECTOR_WRITE_FAILED",
                "draft vector points cannot be written",
                status_code=503,
                retryable=True,
                details={"point_count": len(points)},
            ) from exc

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

    def _load_ready_index_versions(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> list[ReadyIndexVersion]:
        document_version_ids = _document_version_ids_from_request(request_json)
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
            raise _database_error(
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
        if self.dimension > 0 and version.dimension != self.dimension:
            raise IndexingServiceError(
                "INDEX_DIMENSION_MISMATCH",
                "ready index embedding dimension does not match active config",
                status_code=409,
                details={
                    "index_version_id": version.index_version_id,
                    "index_dimension": version.dimension,
                    "active_config_dimension": self.dimension,
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
            row = session.execute(
                text(
                    """
                    SELECT
                        iv.chunk_count::integer AS expected_chunk_count,
                        (
                            SELECT count(*)::integer
                            FROM chunks c
                            WHERE c.document_version_id = iv.document_version_id
                              AND c.status = 'draft'
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
                {"index_version_id": version.index_version_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
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
            raise _database_error(
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
        if isinstance(self.vector_index_writer, NoopVectorIndexWriter):
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
            self.vector_index_writer.activate_points(
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
            raise _database_error(
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
                SET status = 'archived'
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

    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        event_name: str,
        resource_id: str,
        summary: dict[str, Any],
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, enterprise_id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level, summary_json
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id, :trace_id,
                    :event_name, 'system', 'indexing', 'document', :resource_id,
                    'index', 'success', 'low', CAST(:summary_json AS jsonb)
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "resource_id": resource_id,
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
            },
        )


def _document_version_ids_from_request(request_json: dict[str, Any]) -> list[str]:
    value = request_json.get("document_version_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _vector_id(chunk: DraftIndexChunk) -> str:
    return str(
        uuid.uuid5(
            VECTOR_ID_NAMESPACE,
            f"{chunk.chunk_id}:{chunk.index_version_id}:{chunk.chunk_content_hash}",
        )
    )


def _draft_vector_point(chunk: DraftIndexChunk) -> DraftVectorPoint:
    payload_hash = _chunk_index_payload_hash(chunk)
    return DraftVectorPoint(
        collection_name=chunk.collection_name,
        vector_id=_vector_id(chunk),
        text=chunk.text,
        payload={
            "enterprise_id": chunk.enterprise_id,
            "kb_id": chunk.kb_id,
            "document_id": chunk.document_id,
            "doc_id": chunk.document_id,
            "document_version_id": chunk.document_version_id,
            "chunk_id": chunk.chunk_id,
            "index_version_id": chunk.index_version_id,
            "title": chunk.title,
            "visibility_state": "draft",
            "document_status": "draft",
            "document_index_status": "indexing",
            "chunk_status": "draft",
            "owner_department_id": chunk.owner_department_id,
            "visibility": chunk.visibility,
            "permission_version": chunk.indexed_permission_version,
            "indexed_permission_version": chunk.indexed_permission_version,
            "is_deleted": False,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "payload_hash": payload_hash,
        },
    )


def _chunk_index_payload_hash(chunk: DraftIndexChunk) -> str:
    return stable_json_hash(
        {
            "chunk_id": chunk.chunk_id,
            "index_version_id": chunk.index_version_id,
            "owner_department_id": chunk.owner_department_id,
            "visibility": chunk.visibility,
            "indexed_permission_version": chunk.indexed_permission_version,
            "index_payload_hash": chunk.index_payload_hash,
        }
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _database_error(error_code: str, message: str, exc: SQLAlchemyError) -> IndexingServiceError:
    original = getattr(exc, "orig", None) or exc.__cause__
    return IndexingServiceError(
        error_code,
        message,
        status_code=500,
        retryable=True,
        details={
            "database_error": {
                "type": exc.__class__.__name__,
                "driver": original.__class__.__name__ if original is not None else None,
            }
        },
    )
