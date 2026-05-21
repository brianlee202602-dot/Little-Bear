"""索引运维诊断服务。"""

from __future__ import annotations

import json
import uuid
from typing import Any, Protocol
from urllib.parse import urlparse

from app.adapters.qdrant import QdrantClientError, QdrantCollectionInfo, QdrantSnapshotInfo
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import (
    IndexCollectionHealth,
    IndexCollectionOperationResult,
    IndexCollectionSnapshot,
)
from app.shared.context import get_request_context
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class QdrantCollectionInspector(Protocol):
    def collection_info(self, collection_name: str) -> QdrantCollectionInfo:
        ...


class QdrantCollectionOperator(QdrantCollectionInspector, Protocol):
    def list_collection_snapshots(self, collection_name: str) -> tuple[QdrantSnapshotInfo, ...]:
        ...

    def create_collection_snapshot(self, collection_name: str) -> QdrantSnapshotInfo:
        ...

    def recover_collection_snapshot(
        self,
        collection_name: str,
        *,
        location: str,
        priority: str | None = None,
        checksum: str | None = None,
    ) -> bool:
        ...


class IndexOpsService:
    def __init__(
        self,
        *,
        qdrant_inspector: QdrantCollectionOperator | None = None,
        expected_dimension: int | None = None,
        qdrant_config_issue: str | None = None,
    ) -> None:
        self.qdrant_inspector = qdrant_inspector
        self.expected_dimension = expected_dimension
        self.qdrant_config_issue = qdrant_config_issue

    def list_collection_health(
        self,
        session: Session,
        *,
        enterprise_id: str,
    ) -> tuple[IndexCollectionHealth, ...]:
        rows = self._load_collection_rows(session, enterprise_id=enterprise_id)
        return tuple(self._health_from_row(row) for row in rows)

    def list_collection_snapshots(
        self,
        session: Session,
        *,
        enterprise_id: str,
        collection_name: str,
    ) -> tuple[IndexCollectionSnapshot, ...]:
        collection_name = self._normalize_collection_name(collection_name)
        self._ensure_collection_known(
            session,
            enterprise_id=enterprise_id,
            collection_name=collection_name,
        )
        operator = self._qdrant_operator()
        try:
            snapshots = operator.list_collection_snapshots(collection_name)
        except QdrantClientError as exc:
            raise IndexingServiceError(
                "INDEX_SNAPSHOT_UNAVAILABLE",
                "qdrant collection snapshots cannot be read",
                status_code=503,
                retryable=True,
                details={
                    "collection_name": collection_name,
                    "source_error": str(exc),
                },
            ) from exc
        return tuple(
            IndexCollectionSnapshot(
                collection_name=collection_name,
                name=snapshot.name,
                size=snapshot.size,
                creation_time=snapshot.creation_time,
                checksum=snapshot.checksum,
            )
            for snapshot in snapshots
        )

    def create_collection_snapshot(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        collection_name: str,
        confirmed: bool,
    ) -> IndexCollectionSnapshot:
        collection_name = self._normalize_collection_name(collection_name)
        if not confirmed:
            raise IndexingServiceError(
                "INDEX_CONFIRMATION_REQUIRED",
                "qdrant snapshot creation requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: snapshot"},
            )
        self._ensure_collection_known(
            session,
            enterprise_id=enterprise_id,
            collection_name=collection_name,
        )
        operator = self._qdrant_operator()
        try:
            snapshot = operator.create_collection_snapshot(collection_name)
        except QdrantClientError as exc:
            raise IndexingServiceError(
                "INDEX_SNAPSHOT_CREATE_FAILED",
                "qdrant collection snapshot cannot be created",
                status_code=503,
                retryable=True,
                details={
                    "collection_name": collection_name,
                    "source_error": str(exc),
                },
            ) from exc
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="index_collection.snapshot_created",
            resource_id=collection_name,
            action="qdrant_snapshot",
            result="success",
            risk_level="high",
            summary={
                "collection_name": collection_name,
                "snapshot_name": snapshot.name,
                "size": snapshot.size,
                "checksum": snapshot.checksum,
            },
        )
        return IndexCollectionSnapshot(
            collection_name=collection_name,
            name=snapshot.name,
            size=snapshot.size,
            creation_time=snapshot.creation_time,
            checksum=snapshot.checksum,
        )

    def recover_collection_snapshot(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        collection_name: str,
        location: str,
        priority: str | None,
        checksum: str | None,
        confirmed: bool,
    ) -> IndexCollectionOperationResult:
        collection_name = self._normalize_collection_name(collection_name)
        location = location.strip()
        checksum = checksum.strip() if checksum else None
        if not confirmed:
            raise IndexingServiceError(
                "INDEX_CONFIRMATION_REQUIRED",
                "qdrant snapshot recovery requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: restore"},
            )
        if priority not in {None, "Snapshot", "Replica"}:
            raise IndexingServiceError(
                "INDEX_SNAPSHOT_RECOVER_PRIORITY_INVALID",
                "qdrant snapshot recovery priority is invalid",
                status_code=400,
                details={"priority": priority},
            )
        self._validate_snapshot_location(location)
        self._ensure_collection_known(
            session,
            enterprise_id=enterprise_id,
            collection_name=collection_name,
        )
        operator = self._qdrant_operator()
        try:
            result = operator.recover_collection_snapshot(
                collection_name,
                location=location,
                priority=priority,
                checksum=checksum,
            )
        except QdrantClientError as exc:
            raise IndexingServiceError(
                "INDEX_SNAPSHOT_RECOVER_FAILED",
                "qdrant collection snapshot cannot be recovered",
                status_code=503,
                retryable=True,
                details={
                    "collection_name": collection_name,
                    "source_error": str(exc),
                },
            ) from exc
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="index_collection.snapshot_recovered",
            resource_id=collection_name,
            action="qdrant_restore",
            result="success",
            risk_level="critical",
            summary={
                "collection_name": collection_name,
                "location": location,
                "priority": priority,
                "checksum": checksum,
                "qdrant_result": result,
            },
        )
        return IndexCollectionOperationResult(
            collection_name=collection_name,
            operation="snapshot_recover",
            accepted=True,
            result=result,
        )

    def _load_collection_rows(
        self,
        session: Session,
        *,
        enterprise_id: str,
    ) -> list[dict[str, Any]]:
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
                    )
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
                    ORDER BY collection_name
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise IndexingServiceError(
                "INDEX_HEALTH_UNAVAILABLE",
                "index collection health cannot be read",
                status_code=503,
                retryable=True,
                details={"source_error": exc.__class__.__name__},
            ) from exc
        return [dict(row._mapping) for row in rows]

    def _ensure_collection_known(
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

    def _qdrant_operator(self) -> QdrantCollectionOperator:
        if self.qdrant_config_issue:
            raise IndexingServiceError(
                "INDEX_QDRANT_CONFIG_UNAVAILABLE",
                "qdrant configuration is unavailable",
                status_code=503,
                retryable=True,
                details={"issue": self.qdrant_config_issue},
            )
        if self.qdrant_inspector is None:
            raise IndexingServiceError(
                "INDEX_QDRANT_OPERATOR_UNAVAILABLE",
                "qdrant operator is unavailable",
                status_code=503,
                retryable=True,
            )
        return self.qdrant_inspector

    def _normalize_collection_name(self, collection_name: str) -> str:
        normalized = collection_name.strip()
        if not normalized:
            raise IndexingServiceError(
                "INDEX_COLLECTION_INVALID",
                "index collection name is required",
                status_code=400,
            )
        return normalized

    def _validate_snapshot_location(self, location: str) -> None:
        if not location:
            raise IndexingServiceError(
                "INDEX_SNAPSHOT_LOCATION_REQUIRED",
                "qdrant snapshot location is required",
                status_code=400,
            )
        parsed = urlparse(location)
        if parsed.scheme not in {"http", "https", "file"}:
            raise IndexingServiceError(
                "INDEX_SNAPSHOT_LOCATION_INVALID",
                "qdrant snapshot location must be http, https, or file uri",
                status_code=400,
                details={"scheme": parsed.scheme},
            )

    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
        resource_id: str,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, enterprise_id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level, summary_json, error_code
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id, :trace_id,
                    :event_name, 'user', :actor_id, 'config', :resource_id,
                    :action, :result, :risk_level, CAST(:summary_json AS jsonb), :error_code
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "actor_id": actor_id,
                "resource_id": resource_id,
                "action": action,
                "result": result,
                "risk_level": risk_level,
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
                "error_code": error_code,
            },
        )

    def _health_from_row(self, row: dict[str, Any]) -> IndexCollectionHealth:
        collection_name = str(row["collection_name"])
        issues: list[str] = []
        qdrant_reachable = False
        qdrant_exists: bool | None = None
        qdrant_status: str | None = None
        qdrant_vector_size: int | None = None
        qdrant_points_count: int | None = None

        if self.qdrant_config_issue:
            issues.append(self.qdrant_config_issue)
        elif self.qdrant_inspector is None:
            issues.append("qdrant_inspector_unavailable")
        else:
            try:
                info = self.qdrant_inspector.collection_info(collection_name)
            except QdrantClientError:
                issues.append("qdrant_unreachable")
            else:
                qdrant_reachable = True
                qdrant_exists = info.exists
                qdrant_status = info.status
                qdrant_vector_size = info.vector_size
                qdrant_points_count = info.points_count
                if not info.exists and int(row["active_ref_count"]) > 0:
                    issues.append("qdrant_collection_missing")
                if info.error:
                    issues.append("qdrant_count_unavailable")
                if (
                    info.vector_size is not None
                    and self.expected_dimension is not None
                    and info.vector_size != self.expected_dimension
                ):
                    issues.append("qdrant_vector_size_mismatch")
                if (
                    info.points_count is not None
                    and int(row["active_ref_count"]) > 0
                    and info.points_count < int(row["active_ref_count"])
                ):
                    issues.append("qdrant_points_less_than_active_refs")

        if int(row["active_ref_mismatch_count"]) > 0:
            issues.append("active_index_ref_count_mismatch")
        if int(row["pending_delete_ref_count"]) > 0:
            issues.append("pending_delete_cleanup_required")
        if int(row["failed_index_version_count"]) > 0:
            issues.append("failed_index_versions_present")

        return IndexCollectionHealth(
            collection_name=collection_name,
            expected_dimension=self.expected_dimension,
            qdrant_reachable=qdrant_reachable,
            qdrant_exists=qdrant_exists,
            qdrant_status=qdrant_status,
            qdrant_vector_size=qdrant_vector_size,
            qdrant_points_count=qdrant_points_count,
            db_index_version_count=int(row["db_index_version_count"]),
            active_index_version_count=int(row["active_index_version_count"]),
            pending_delete_index_version_count=int(row["pending_delete_index_version_count"]),
            failed_index_version_count=int(row["failed_index_version_count"]),
            active_ref_count=int(row["active_ref_count"]),
            draft_ref_count=int(row["draft_ref_count"]),
            deleted_ref_count=int(row["deleted_ref_count"]),
            pending_delete_ref_count=int(row["pending_delete_ref_count"]),
            active_ref_mismatch_count=int(row["active_ref_mismatch_count"]),
            issues=tuple(dict.fromkeys(issues)),
        )
