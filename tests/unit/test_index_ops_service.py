from __future__ import annotations

import pytest
from app.adapters.qdrant import QdrantCollectionInfo, QdrantSnapshotInfo
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.ops_service import IndexOpsService


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def all(self) -> list[_Row]:
        return self._rows

    def first(self) -> _Row | None:
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []
        self.rows: list[_Row] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        return _Result(self.rows)


class _FakeQdrantInspector:
    def __init__(self, info: QdrantCollectionInfo) -> None:
        self.info = info
        self.collections: list[str] = []
        self.snapshots = (
            QdrantSnapshotInfo(
                name="little_bear_p0.snapshot",
                size=123,
                creation_time="2026-05-21T00:00:00Z",
                checksum="sha256:abc",
            ),
        )
        self.created_snapshot = QdrantSnapshotInfo(name="created.snapshot", size=456)
        self.recover_calls: list[dict[str, object]] = []

    def collection_info(self, collection_name: str) -> QdrantCollectionInfo:
        self.collections.append(collection_name)
        return self.info

    def list_collection_snapshots(self, collection_name: str) -> tuple[QdrantSnapshotInfo, ...]:
        self.collections.append(collection_name)
        return self.snapshots

    def create_collection_snapshot(self, collection_name: str) -> QdrantSnapshotInfo:
        self.collections.append(collection_name)
        return self.created_snapshot

    def recover_collection_snapshot(
        self,
        collection_name: str,
        *,
        location: str,
        priority: str | None = None,
        checksum: str | None = None,
    ) -> bool:
        self.recover_calls.append(
            {
                "collection_name": collection_name,
                "location": location,
                "priority": priority,
                "checksum": checksum,
            }
        )
        return True


def test_index_ops_service_reports_collection_health() -> None:
    session = _FakeSession()
    session.rows = [
        _Row(
            {
                "collection_name": "little_bear_p0",
                "db_index_version_count": 3,
                "active_index_version_count": 1,
                "pending_delete_index_version_count": 1,
                "failed_index_version_count": 0,
                "active_ref_count": 5,
                "draft_ref_count": 0,
                "deleted_ref_count": 5,
                "pending_delete_ref_count": 0,
                "active_ref_mismatch_count": 0,
            }
        )
    ]
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(
            collection_name="little_bear_p0",
            exists=True,
            status="green",
            vector_size=768,
            points_count=10,
        )
    )

    result = IndexOpsService(
        qdrant_inspector=inspector,
        expected_dimension=768,
    ).list_collection_health(session, enterprise_id="33333333-3333-3333-3333-333333333333")

    assert len(result.items) == 1
    assert result.total == 1
    assert result.items[0].collection_name == "little_bear_p0"
    assert result.items[0].qdrant_reachable is True
    assert result.items[0].qdrant_exists is True
    assert result.items[0].active_ref_count == 5
    assert result.items[0].issues == ()
    assert inspector.collections == ["little_bear_p0"]
    assert session.executed[0][1]["enterprise_id"] == "33333333-3333-3333-3333-333333333333"
    assert session.executed[0][1]["limit"] == 20
    assert session.executed[0][1]["offset"] == 0


def test_index_ops_service_flags_mismatches_and_pending_cleanup() -> None:
    session = _FakeSession()
    session.rows = [
        _Row(
            {
                "collection_name": "little_bear_p0",
                "db_index_version_count": 2,
                "active_index_version_count": 1,
                "pending_delete_index_version_count": 1,
                "failed_index_version_count": 1,
                "active_ref_count": 5,
                "draft_ref_count": 1,
                "deleted_ref_count": 0,
                "pending_delete_ref_count": 2,
                "active_ref_mismatch_count": 1,
            }
        )
    ]
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(
            collection_name="little_bear_p0",
            exists=True,
            status="yellow",
            vector_size=384,
            points_count=4,
            error="count failed",
        )
    )

    result = IndexOpsService(
        qdrant_inspector=inspector,
        expected_dimension=768,
    ).list_collection_health(session, enterprise_id="33333333-3333-3333-3333-333333333333")

    assert result.items[0].issues == (
        "qdrant_count_unavailable",
        "qdrant_vector_size_mismatch",
        "qdrant_points_less_than_active_refs",
        "active_index_ref_count_mismatch",
        "pending_delete_cleanup_required",
        "failed_index_versions_present",
    )


def test_index_ops_service_reports_qdrant_config_issue() -> None:
    session = _FakeSession()
    session.rows = [
        _Row(
            {
                "collection_name": "little_bear_p0",
                "db_index_version_count": 1,
                "active_index_version_count": 1,
                "pending_delete_index_version_count": 0,
                "failed_index_version_count": 0,
                "active_ref_count": 3,
                "draft_ref_count": 0,
                "deleted_ref_count": 0,
                "pending_delete_ref_count": 0,
                "active_ref_mismatch_count": 0,
            }
        )
    ]

    result = IndexOpsService(
        expected_dimension=768,
        qdrant_config_issue="qdrant_base_url_missing",
    ).list_collection_health(session, enterprise_id="33333333-3333-3333-3333-333333333333")

    assert result.items[0].qdrant_reachable is False
    assert result.items[0].issues == ("qdrant_base_url_missing",)


def test_index_ops_service_lists_collection_snapshots_after_enterprise_check() -> None:
    session = _FakeSession()
    session.rows = [_Row({"exists": 1})]
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(collection_name="little_bear_p0", exists=True),
    )
    inspector.snapshots = (
        QdrantSnapshotInfo(name="first.snapshot", size=100),
        QdrantSnapshotInfo(name="second.snapshot", size=200),
    )

    result = IndexOpsService(qdrant_inspector=inspector).list_collection_snapshots(
        session,
        enterprise_id="33333333-3333-3333-3333-333333333333",
        collection_name=" little_bear_p0 ",
        page=2,
        page_size=1,
    )

    assert result.items[0].collection_name == "little_bear_p0"
    assert result.items[0].name == "second.snapshot"
    assert result.total == 2
    assert inspector.collections == ["little_bear_p0"]


def test_index_ops_service_create_snapshot_requires_confirmation() -> None:
    session = _FakeSession()
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(collection_name="little_bear_p0", exists=True),
    )

    with pytest.raises(IndexingServiceError) as exc_info:
        IndexOpsService(qdrant_inspector=inspector).create_collection_snapshot(
            session,
            enterprise_id="33333333-3333-3333-3333-333333333333",
            actor_user_id="11111111-1111-1111-1111-111111111111",
            collection_name="little_bear_p0",
            confirmed=False,
        )

    assert exc_info.value.error_code == "INDEX_CONFIRMATION_REQUIRED"
    assert exc_info.value.status_code == 428


def test_index_ops_service_creates_snapshot_and_audit_log() -> None:
    session = _FakeSession()
    session.rows = [_Row({"exists": 1})]
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(collection_name="little_bear_p0", exists=True),
    )

    result = IndexOpsService(qdrant_inspector=inspector).create_collection_snapshot(
        session,
        enterprise_id="33333333-3333-3333-3333-333333333333",
        actor_user_id="11111111-1111-1111-1111-111111111111",
        collection_name="little_bear_p0",
        confirmed=True,
    )

    assert result.name == "created.snapshot"
    assert inspector.collections == ["little_bear_p0"]
    assert "INSERT INTO audit_logs" in session.executed[-1][0]
    assert session.executed[-1][1]["event_name"] == "index_collection.snapshot_created"


def test_index_ops_service_recovers_snapshot_and_audit_log() -> None:
    session = _FakeSession()
    session.rows = [_Row({"exists": 1})]
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(collection_name="little_bear_p0", exists=True),
    )

    result = IndexOpsService(qdrant_inspector=inspector).recover_collection_snapshot(
        session,
        enterprise_id="33333333-3333-3333-3333-333333333333",
        actor_user_id="11111111-1111-1111-1111-111111111111",
        collection_name="little_bear_p0",
        location="https://snapshots.example/little_bear.snapshot",
        priority="Snapshot",
        checksum="sha256:abc",
        confirmed=True,
    )

    assert result.accepted is True
    assert inspector.recover_calls == [
        {
            "collection_name": "little_bear_p0",
            "location": "https://snapshots.example/little_bear.snapshot",
            "priority": "Snapshot",
            "checksum": "sha256:abc",
        }
    ]
    assert session.executed[-1][1]["event_name"] == "index_collection.snapshot_recovered"


def test_index_ops_service_rejects_unknown_snapshot_location_scheme() -> None:
    session = _FakeSession()
    session.rows = [_Row({"exists": 1})]
    inspector = _FakeQdrantInspector(
        QdrantCollectionInfo(collection_name="little_bear_p0", exists=True),
    )

    with pytest.raises(IndexingServiceError) as exc_info:
        IndexOpsService(qdrant_inspector=inspector).recover_collection_snapshot(
            session,
            enterprise_id="33333333-3333-3333-3333-333333333333",
            actor_user_id="11111111-1111-1111-1111-111111111111",
            collection_name="little_bear_p0",
            location="ftp://snapshots.example/little_bear.snapshot",
            priority="Snapshot",
            checksum=None,
            confirmed=True,
        )

    assert exc_info.value.error_code == "INDEX_SNAPSHOT_LOCATION_INVALID"
