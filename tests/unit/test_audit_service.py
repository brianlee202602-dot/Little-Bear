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
        if "FROM query_logs" in sql:
            return _Result(row=_Row(_query_row()), rows=[_Row(_query_row())])
        if "FROM model_call_logs" in sql:
            return _Result(row=_Row(_model_call_row()), rows=[_Row(_model_call_row())])
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


def _query_row() -> dict[str, Any]:
    return {
        "id": "query_log_1",
        "request_id": "req_query",
        "trace_id": "trace_query",
        "user_id": "11111111-1111-1111-1111-111111111111",
        "user_display_name": "系统管理员",
        "kb_ids": ["22222222-2222-2222-2222-222222222222"],
        "knowledge_base_names": ["员工手册"],
        "query_hash": "hash_query",
        "status": "success",
        "degraded": False,
        "degrade_reason": None,
        "config_version": 1,
        "permission_version": 3,
        "permission_filter_hash": "hash_permission",
        "index_version_hash": "hash_index",
        "model_route_hash": "hash_model",
        "latency_ms": 321,
        "candidate_count": 5,
        "citation_count": 2,
        "error_code": None,
        "created_at": datetime.now(UTC),
    }


def _model_call_row() -> dict[str, Any]:
    return {
        "id": "model_call_1",
        "request_id": "req_query",
        "trace_id": "trace_query",
        "caller": "query.answer",
        "model_type": "llm",
        "model_name": "qwen2.5",
        "model_version": None,
        "model_route_hash": "hash_model",
        "status": "success",
        "latency_ms": 654,
        "token_usage_json": {"prompt_tokens": 10, "completion_tokens": 20},
        "degraded": False,
        "config_version": 1,
        "prompt_hash": "hash_prompt",
        "input_hash": "hash_input",
        "output_hash": "hash_output",
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


def test_audit_service_lists_query_logs_with_diagnostic_filters() -> None:
    session = _FakeSession()

    result = AuditService().list_query_logs(
        session,
        enterprise_id="33333333-3333-3333-3333-333333333333",
        page=1,
        page_size=20,
        filters={
            "kb_id": "22222222-2222-2222-2222-222222222222",
            "trace_id": "trace_query",
            "degraded": False,
        },
    )

    assert result.total == 1
    assert result.items[0].request_id == "req_query"
    assert result.items[0].user_display_name == "系统管理员"
    assert result.items[0].knowledge_base_names == ("员工手册",)
    assert result.items[0].kb_ids == ("22222222-2222-2222-2222-222222222222",)
    sql, params = session.statements[0]
    assert "FROM query_logs q" in sql
    assert "LEFT JOIN users u" in sql
    assert "CAST(:kb_id AS uuid) = ANY(q.kb_ids)" in sql
    assert params["enterprise_id"] == "33333333-3333-3333-3333-333333333333"
    assert params["trace_id"] == "trace_query"
    assert params["degraded"] is False


def test_audit_service_gets_single_query_log() -> None:
    log = AuditService().get_query_log(
        _FakeSession(),
        enterprise_id="33333333-3333-3333-3333-333333333333",
        query_log_id="query_log_1",
    )

    assert log.id == "query_log_1"
    assert log.user_display_name == "系统管理员"
    assert log.knowledge_base_names == ("员工手册",)
    assert log.candidate_count == 5


def test_audit_service_lists_model_call_logs_with_trace_filter() -> None:
    session = _FakeSession()

    result = AuditService().list_model_call_logs(
        session,
        enterprise_id="33333333-3333-3333-3333-333333333333",
        page=1,
        page_size=20,
        filters={"trace_id": "trace_query", "model": "qwen", "model_type": "llm"},
    )

    assert result.total == 1
    assert result.items[0].model_name == "qwen2.5"
    sql, params = session.statements[0]
    assert "FROM model_call_logs" in sql
    assert "(model_name ILIKE :model OR COALESCE(model_version, '') ILIKE :model)" in sql
    assert "token_usage_json" not in sql
    assert "prompt_hash" not in sql
    assert "input_hash" not in sql
    assert "output_hash" not in sql
    assert "model_route_hash" not in sql.split("FROM model_call_logs", maxsplit=1)[0]
    assert params["model"] == "%qwen%"


def test_audit_service_gets_single_model_call_log() -> None:
    log = AuditService().get_model_call_log(
        _FakeSession(),
        enterprise_id="33333333-3333-3333-3333-333333333333",
        model_call_log_id="model_call_1",
    )

    assert log.id == "model_call_1"
    assert log.trace_id == "trace_query"
    assert log.token_usage_json == {"prompt_tokens": 10, "completion_tokens": 20}
    assert log.prompt_hash == "hash_prompt"
