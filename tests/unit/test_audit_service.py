from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from app.modules.audit.errors import AuditServiceError
from app.modules.audit.service import AuditService


class _Result:
    def __init__(self, *, rows: list[Any] | None = None, row: Any | None = None) -> None:
        self.rows = rows or []
        self.row = row

    def all(self):
        return self.rows

    def one(self):
        return self.row

    def one_or_none(self):
        return self.row


class _Row:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping


class _FakeSession:
    def __init__(self, *, row_present: bool = True) -> None:
        self.row_present = row_present
        self.statements: list[tuple[str, dict[str, Any]]] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if "count(*) AS total" in sql:
            return _Result(row=_Row({"total": 1}))
        if "WHERE id::text = :audit_id" in sql:
            return _Result(row=_Row(_audit_row()) if self.row_present else None)
        if "FROM audit_logs" in sql:
            return _Result(rows=[_Row(_audit_row())])
        raise AssertionError(f"unexpected SQL: {sql}")


def _audit_row() -> dict[str, Any]:
    return {
        "id": "audit_1",
        "request_id": "req_1",
        "trace_id": "trace_1",
        "event_name": "config.published",
        "actor_type": "user",
        "actor_id": "user_1",
        "action": "publish",
        "resource_type": "config",
        "resource_id": "2",
        "result": "success",
        "risk_level": "critical",
        "config_version": 2,
        "permission_version": None,
        "index_version_hash": None,
        "summary_json": {"previous_active_version": 1},
        "error_code": None,
        "created_at": datetime.now(UTC),
    }


def test_audit_service_lists_logs_with_filters() -> None:
    session = _FakeSession()

    result = AuditService().list_audit_logs(
        session,
        page=2,
        page_size=10,
        filters={"resource_type": "config", "result": "success"},
    )

    assert result.total == 1
    assert result.items[0].event_name == "config.published"
    first_query_params = session.statements[0][1]
    assert first_query_params["resource_type"] == "config"
    assert first_query_params["result"] == "success"
    assert first_query_params["offset"] == 10


def test_audit_service_gets_single_log() -> None:
    log = AuditService().get_audit_log(_FakeSession(), "audit_1")

    assert log.id == "audit_1"
    assert log.summary_json["previous_active_version"] == 1


def test_audit_service_rejects_missing_log() -> None:
    with pytest.raises(AuditServiceError) as exc_info:
        AuditService().get_audit_log(_FakeSession(row_present=False), "missing")

    assert exc_info.value.error_code == "AUDIT_LOG_NOT_FOUND"
