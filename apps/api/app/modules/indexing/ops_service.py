"""索引运维诊断 facade。"""

from __future__ import annotations

from app.modules.indexing.collection_health_repository import (
    IndexCollectionHealthRepository,
)
from app.modules.indexing.collection_health_service import IndexCollectionHealthService
from app.modules.indexing.qdrant_snapshot_service import (
    QdrantCollectionOperator,
    QdrantSnapshotService,
)
from app.modules.indexing.schemas import (
    IndexCollectionHealthList,
    IndexCollectionOperationResult,
    IndexCollectionSnapshot,
    IndexCollectionSnapshotList,
)
from sqlalchemy.orm import Session


class IndexOpsService:
    def __init__(
        self,
        *,
        qdrant_inspector: QdrantCollectionOperator | None = None,
        expected_dimension: int | None = None,
        qdrant_config_issue: str | None = None,
        repository: IndexCollectionHealthRepository | None = None,
    ) -> None:
        self.repository = repository or IndexCollectionHealthRepository()
        self.qdrant_inspector = qdrant_inspector
        self.expected_dimension = expected_dimension
        self.qdrant_config_issue = qdrant_config_issue

    def list_collection_health(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> IndexCollectionHealthList:
        return self._collection_health().list_collection_health(
            session,
            enterprise_id=enterprise_id,
            page=page,
            page_size=page_size,
        )

    def list_collection_snapshots(
        self,
        session: Session,
        *,
        enterprise_id: str,
        collection_name: str,
        page: int = 1,
        page_size: int = 20,
    ) -> IndexCollectionSnapshotList:
        return self._snapshots().list_collection_snapshots(
            session,
            enterprise_id=enterprise_id,
            collection_name=collection_name,
            page=page,
            page_size=page_size,
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
        return self._snapshots().create_collection_snapshot(
            session,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            collection_name=collection_name,
            confirmed=confirmed,
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
        return self._snapshots().recover_collection_snapshot(
            session,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            collection_name=collection_name,
            location=location,
            priority=priority,
            checksum=checksum,
            confirmed=confirmed,
        )

    def _collection_health(self) -> IndexCollectionHealthService:
        return IndexCollectionHealthService(
            repository=self.repository,
            qdrant_inspector=self.qdrant_inspector,
            expected_dimension=self.expected_dimension,
            qdrant_config_issue=self.qdrant_config_issue,
        )

    def _snapshots(self) -> QdrantSnapshotService:
        return QdrantSnapshotService(
            repository=self.repository,
            qdrant_operator=self.qdrant_inspector,
            qdrant_config_issue=self.qdrant_config_issue,
        )
