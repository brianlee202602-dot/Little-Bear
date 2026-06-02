"""索引 collection 健康检查数据库读取。"""

from __future__ import annotations

from typing import Any

from app.modules.indexing.errors import IndexingServiceError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class IndexCollectionHealthRepository:
    def load_collection_rows(
        self,
        session: Session,
        *,
        enterprise_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            rows = session.execute(
                text(
                    """
                    WITH version_ref_counts AS (
                        SELECT
                            iv.id,
                            iv.collection_name,
                            iv.status,
                            iv.chunk_count,
                            count(cir.id)::integer AS ref_count,
                            count(cir.id) FILTER (
                                WHERE cir.visibility_state = 'active'
                            )::integer AS active_ref_count,
                            count(cir.id) FILTER (
                                WHERE cir.visibility_state = 'draft'
                            )::integer AS draft_ref_count,
                            count(cir.id) FILTER (
                                WHERE cir.visibility_state = 'deleted'
                            )::integer AS deleted_ref_count,
                            count(cir.id) FILTER (
                                WHERE cir.visibility_state != 'deleted'
                            )::integer AS non_deleted_ref_count
                        FROM index_versions iv
                        LEFT JOIN chunk_index_refs cir ON cir.index_version_id = iv.id
                        WHERE iv.enterprise_id = CAST(:enterprise_id AS uuid)
                        GROUP BY iv.id, iv.collection_name, iv.status, iv.chunk_count
                    ),
                    collection_health AS (
                        SELECT
                            collection_name,
                            count(*)::integer AS db_index_version_count,
                            count(*) FILTER (
                                WHERE status = 'active'
                            )::integer AS active_index_version_count,
                            count(*) FILTER (
                                WHERE status = 'pending_delete'
                            )::integer AS pending_delete_index_version_count,
                            count(*) FILTER (
                                WHERE status = 'failed'
                            )::integer AS failed_index_version_count,
                            COALESCE(sum(active_ref_count), 0)::integer AS active_ref_count,
                            COALESCE(sum(draft_ref_count), 0)::integer AS draft_ref_count,
                            COALESCE(sum(deleted_ref_count), 0)::integer AS deleted_ref_count,
                            COALESCE(sum(non_deleted_ref_count) FILTER (
                                WHERE status = 'pending_delete'
                            ), 0)::integer AS pending_delete_ref_count,
                            count(*) FILTER (
                                WHERE status = 'active'
                                  AND chunk_count != active_ref_count
                            )::integer AS active_ref_mismatch_count
                        FROM version_ref_counts
                        GROUP BY collection_name
                    )
                    SELECT
                        collection_name,
                        db_index_version_count,
                        active_index_version_count,
                        pending_delete_index_version_count,
                        failed_index_version_count,
                        active_ref_count,
                        draft_ref_count,
                        deleted_ref_count,
                        pending_delete_ref_count,
                        active_ref_mismatch_count,
                        count(*) OVER()::integer AS total_count
                    FROM collection_health
                    ORDER BY collection_name
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "limit": limit,
                    "offset": offset,
                },
            ).all()
        except SQLAlchemyError as exc:
            raise _index_health_error(exc) from exc
        items = [dict(row._mapping) for row in rows]
        if items:
            total = int(items[0].get("total_count", len(items)))
        elif offset > 0:
            total = self.count_collection_rows(session, enterprise_id=enterprise_id)
        else:
            total = 0
        return items, total

    def count_collection_rows(
        self,
        session: Session,
        *,
        enterprise_id: str,
    ) -> int:
        try:
            total = session.execute(
                text(
                    """
                    SELECT count(DISTINCT collection_name)::integer AS total
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).scalar_one()
        except SQLAlchemyError as exc:
            raise _index_health_error(exc) from exc
        return int(total)

    def ensure_collection_known(
        self,
        session: Session,
        *,
        enterprise_id: str,
        collection_name: str,
    ) -> None:
        try:
            row = session.execute(
                text(
                    """
                    SELECT 1
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND collection_name = :collection_name
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id, "collection_name": collection_name},
            ).first()
        except SQLAlchemyError as exc:
            raise IndexingServiceError(
                "INDEX_COLLECTION_LOOKUP_FAILED",
                "index collection cannot be validated",
                status_code=503,
                retryable=True,
                details={"source_error": exc.__class__.__name__},
            ) from exc
        if row is None:
            raise IndexingServiceError(
                "INDEX_COLLECTION_NOT_FOUND",
                "index collection does not belong to this enterprise",
                status_code=404,
                details={"collection_name": collection_name},
            )


def _index_health_error(exc: SQLAlchemyError) -> IndexingServiceError:
    return IndexingServiceError(
        "INDEX_HEALTH_UNAVAILABLE",
        "index collection health cannot be read",
        status_code=503,
        retryable=True,
        details={"source_error": exc.__class__.__name__},
    )
