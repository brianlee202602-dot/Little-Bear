"""索引 collection 健康诊断服务。"""

from __future__ import annotations

from typing import Any, Protocol

from app.adapters.qdrant import QdrantClientError, QdrantCollectionInfo
from app.modules.indexing.collection_health_repository import (
    IndexCollectionHealthRepository,
)
from app.modules.indexing.schemas import IndexCollectionHealth, IndexCollectionHealthList
from sqlalchemy.orm import Session


class QdrantCollectionInspector(Protocol):
    def collection_info(self, collection_name: str) -> QdrantCollectionInfo:
        ...


class IndexCollectionHealthService:
    def __init__(
        self,
        *,
        repository: IndexCollectionHealthRepository | None = None,
        qdrant_inspector: QdrantCollectionInspector | None = None,
        expected_dimension: int | None = None,
        qdrant_config_issue: str | None = None,
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
        rows, total = self.repository.load_collection_rows(
            session,
            enterprise_id=enterprise_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return IndexCollectionHealthList(
            items=tuple(self._health_from_row(row) for row in rows),
            total=total,
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
