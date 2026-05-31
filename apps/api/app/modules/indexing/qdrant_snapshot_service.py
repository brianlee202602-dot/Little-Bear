"""Qdrant collection 快照运维服务。"""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from app.adapters.qdrant import QdrantClientError, QdrantSnapshotInfo
from app.modules.indexing.collection_health_repository import (
    IndexCollectionHealthRepository,
)
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.index_ops_audit import IndexOpsAuditWriter
from app.modules.indexing.schemas import (
    IndexCollectionOperationResult,
    IndexCollectionSnapshot,
    IndexCollectionSnapshotList,
)
from sqlalchemy.orm import Session


class QdrantCollectionOperator(Protocol):
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


class QdrantSnapshotService:
    def __init__(
        self,
        *,
        repository: IndexCollectionHealthRepository | None = None,
        audit_writer: IndexOpsAuditWriter | None = None,
        qdrant_operator: QdrantCollectionOperator | None = None,
        qdrant_config_issue: str | None = None,
    ) -> None:
        self.repository = repository or IndexCollectionHealthRepository()
        self.audit_writer = audit_writer or IndexOpsAuditWriter()
        self.qdrant_operator = qdrant_operator
        self.qdrant_config_issue = qdrant_config_issue

    def list_collection_snapshots(
        self,
        session: Session,
        *,
        enterprise_id: str,
        collection_name: str,
        page: int = 1,
        page_size: int = 20,
    ) -> IndexCollectionSnapshotList:
        collection_name = self._normalize_collection_name(collection_name)
        self.repository.ensure_collection_known(
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
        offset = (page - 1) * page_size
        return IndexCollectionSnapshotList(
            items=tuple(
                _snapshot_schema(collection_name, snapshot)
                for snapshot in snapshots[offset : offset + page_size]
            ),
            total=len(snapshots),
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
        self.repository.ensure_collection_known(
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
        self.audit_writer.write(
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
        return _snapshot_schema(collection_name, snapshot)

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
        self.repository.ensure_collection_known(
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
        self.audit_writer.write(
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

    def _qdrant_operator(self) -> QdrantCollectionOperator:
        if self.qdrant_config_issue:
            raise IndexingServiceError(
                "INDEX_QDRANT_CONFIG_UNAVAILABLE",
                "qdrant configuration is unavailable",
                status_code=503,
                retryable=True,
                details={"issue": self.qdrant_config_issue},
            )
        if self.qdrant_operator is None:
            raise IndexingServiceError(
                "INDEX_QDRANT_OPERATOR_UNAVAILABLE",
                "qdrant operator is unavailable",
                status_code=503,
                retryable=True,
            )
        return self.qdrant_operator

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


def _snapshot_schema(
    collection_name: str,
    snapshot: QdrantSnapshotInfo,
) -> IndexCollectionSnapshot:
    return IndexCollectionSnapshot(
        collection_name=collection_name,
        name=snapshot.name,
        size=snapshot.size,
        creation_time=snapshot.creation_time,
        checksum=snapshot.checksum,
    )
