from __future__ import annotations

import json

import pytest
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import DocumentImportItem, ImportActorContext
from app.modules.import_pipeline.service import ImportService


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(
        self,
        *,
        one: _Row | None = None,
        one_or_none: _Row | None = None,
        all_rows: list[_Row] | None = None,
    ) -> None:
        self._one = one
        self._one_or_none = one_or_none
        self._all_rows = all_rows or []

    def one(self) -> _Row:
        assert self._one is not None
        return self._one

    def one_or_none(self) -> _Row | None:
        return self._one_or_none

    def all(self) -> list[_Row]:
        return self._all_rows


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []
        self.results: list[_Result] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        if self.results:
            return self.results.pop(0)
        return _Result()


_ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
_USER_ID = "11111111-1111-1111-1111-111111111111"
_KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_DEPARTMENT_ID = "22222222-2222-2222-2222-222222222222"


def _actor() -> ImportActorContext:
    return ImportActorContext(
        user_id=_USER_ID,
        scopes=("document:import", "import_job:read:self", "import_job:manage:self"),
        department_ids=(_DEPARTMENT_ID,),
        can_import_all_knowledge_bases=True,
    )


def _job_row(
    *,
    job_id: str = "99999999-9999-9999-9999-999999999999",
    status: str = "queued",
    stage: str = "validate",
    request_json: dict[str, object] | None = None,
) -> _Row:
    payload = request_json or {
        "document_ids": ["44444444-4444-4444-4444-444444444444"]
    }
    return _Row(
        {
            "job_id": job_id,
            "job_type": "metadata_batch",
            "kb_id": _KB_ID,
            "document_id": "44444444-4444-4444-4444-444444444444",
            "document_version_id": "55555555-5555-5555-5555-555555555555",
            "status": status,
            "stage": stage,
            "request_json": payload,
            "result_json": {},
            "error_message": None,
        }
    )


def test_create_document_import_writes_documents_versions_and_job(monkeypatch) -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            one_or_none=_Row(
                {
                    "kb_id": _KB_ID,
                    "owner_department_id": _DEPARTMENT_ID,
                    "default_visibility": "department",
                    "status": "active",
                    "policy_version": 1,
                }
            )
        ),
        _Result(one_or_none=_Row({"department_id": _DEPARTMENT_ID, "status": "active"})),
    ]
    service = ImportService()
    monkeypatch.setattr(service, "_bump_permission_version", lambda *_args: 9)
    monkeypatch.setattr(
        service,
        "_replace_resource_policy",
        lambda *_args, **_kwargs: "66666666-6666-6666-6666-666666666666",
    )
    monkeypatch.setattr(
        service,
        "_insert_permission_snapshot",
        lambda *_args, **_kwargs: {
            "snapshot_id": "77777777-7777-7777-7777-777777777777",
            "payload_hash": "hash_1",
        },
    )
    audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_insert_audit_log",
        lambda _session, **kwargs: audits.append(kwargs),
    )

    job = service.create_document_import(
        session,
        enterprise_id=_ENTERPRISE_ID,
        kb_id=_KB_ID,
        actor_user_id=_USER_ID,
        job_type="metadata_batch",
        items=[DocumentImportItem(title="员工手册", metadata={"tags": ["HR", "HR"]})],
        actor_context=_actor(),
    )

    assert job.status == "queued"
    assert job.stage == "validate"
    assert len(job.document_ids) == 1
    assert any("INSERT INTO documents" in statement for statement, _ in session.executed)
    assert any("INSERT INTO document_versions" in statement for statement, _ in session.executed)
    job_insert = next(
        params
        for statement, params in session.executed
        if "INSERT INTO import_jobs" in statement
    )
    assert job_insert["job_type"] == "metadata_batch"
    request_json = json.loads(job_insert["request_json"])
    assert request_json["document_ids"] == list(job.document_ids)
    assert audits[0]["event_name"] == "import_job.created"


def test_create_document_import_returns_existing_idempotent_job() -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            one_or_none=_Row(
                {
                    "kb_id": _KB_ID,
                    "owner_department_id": _DEPARTMENT_ID,
                    "default_visibility": "department",
                    "status": "active",
                    "policy_version": 1,
                }
            )
        ),
        _Result(one_or_none=_job_row(status="running", stage="parse")),
    ]

    job = ImportService().create_document_import(
        session,
        enterprise_id=_ENTERPRISE_ID,
        kb_id=_KB_ID,
        actor_user_id=_USER_ID,
        job_type="metadata_batch",
        items=[DocumentImportItem(title="员工手册")],
        idempotency_key="same-request",
        actor_context=_actor(),
    )

    assert job.status == "running"
    assert job.stage == "parse"
    assert not any("INSERT INTO documents" in statement for statement, _ in session.executed)


def test_create_document_import_requires_url_for_url_job() -> None:
    with pytest.raises(ImportServiceError) as exc_info:
        ImportService().create_document_import(
            _FakeSession(),
            enterprise_id=_ENTERPRISE_ID,
            kb_id=_KB_ID,
            actor_user_id=_USER_ID,
            job_type="url",
            items=[DocumentImportItem(title="官网制度")],
            actor_context=_actor(),
        )

    assert exc_info.value.error_code == "IMPORT_ITEM_URL_REQUIRED"


def test_request_cancel_marks_queued_job_cancelled(monkeypatch) -> None:
    session = _FakeSession()
    session.results = [
        _Result(one_or_none=_job_row(status="queued")),
        _Result(one=_job_row(status="cancelled")),
    ]
    service = ImportService()
    monkeypatch.setattr(service, "_insert_audit_log", lambda *_args, **_kwargs: None)

    job = service.request_cancel(
        session,
        "99999999-9999-9999-9999-999999999999",
        enterprise_id=_ENTERPRISE_ID,
        actor_user_id=_USER_ID,
    )

    assert job.status == "cancelled"
    assert any("status = 'cancelled'" in statement for statement, _ in session.executed)


def test_claim_next_job_uses_skip_locked_and_sets_worker_lock(monkeypatch) -> None:
    session = _FakeSession()
    session.results = [
        _Result(one_or_none=_job_row(status="running")),
    ]
    service = ImportService()
    monkeypatch.setattr(service, "_job_enterprise_id", lambda *_args: _ENTERPRISE_ID)
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    job = service.claim_next_job(session, worker_id="worker_1")

    assert job is not None
    assert job.status == "running"
    sql, params = session.executed[0]
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert params["worker_id"] == "worker_1"


def test_advance_claimed_job_moves_to_next_stage(monkeypatch) -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            one_or_none=_Row(
                {
                    "job_id": "99999999-9999-9999-9999-999999999999",
                    "enterprise_id": _ENTERPRISE_ID,
                    "job_type": "metadata_batch",
                    "kb_id": _KB_ID,
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "document_version_id": "55555555-5555-5555-5555-555555555555",
                    "status": "running",
                    "stage": "validate",
                    "request_json": {
                        "document_ids": ["44444444-4444-4444-4444-444444444444"]
                    },
                    "result_json": {},
                    "error_message": None,
                    "attempt_count": 1,
                    "max_attempts": 3,
                    "cancel_requested_at": None,
                }
            )
        ),
        _Result(),
        _Result(one=_job_row(status="running", stage="parse")),
    ]
    service = ImportService()
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    job = service.advance_claimed_job(
        session,
        job_id="99999999-9999-9999-9999-999999999999",
        worker_id="worker_1",
    )

    assert job.stage == "parse"
    assert any("stage = :next_stage" in statement for statement, _ in session.executed)


def test_advance_claimed_job_chunk_stage_writes_draft_chunks(monkeypatch) -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            one_or_none=_Row(
                {
                    "job_id": "99999999-9999-9999-9999-999999999999",
                    "enterprise_id": _ENTERPRISE_ID,
                    "job_type": "upload",
                    "kb_id": _KB_ID,
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "document_version_id": "55555555-5555-5555-5555-555555555555",
                    "status": "running",
                    "stage": "chunk",
                    "request_json": {
                        "document_ids": ["44444444-4444-4444-4444-444444444444"],
                        "document_version_ids": ["55555555-5555-5555-5555-555555555555"],
                        "items": [
                            {
                                "document_id": "44444444-4444-4444-4444-444444444444",
                                "document_version_id": "55555555-5555-5555-5555-555555555555",
                                "title": "handbook.md",
                                "metadata": {"content": "# 员工手册\n\n请遵守制度。"},
                            }
                        ],
                    },
                    "result_json": {},
                    "error_message": None,
                    "attempt_count": 1,
                    "max_attempts": 3,
                    "cancel_requested_at": None,
                }
            )
        ),
        _Result(),
        _Result(),
        _Result(one=_job_row(status="running", stage="embed")),
    ]
    service = ImportService()
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    job = service.advance_claimed_job(
        session,
        job_id="99999999-9999-9999-9999-999999999999",
        worker_id="worker_1",
    )

    assert job.stage == "embed"
    assert any("INSERT INTO chunks" in statement for statement, _ in session.executed)
    assert any("chunker_version" in statement for statement, _ in session.executed)


def test_mark_claimed_job_failed_schedules_retry(monkeypatch) -> None:
    session = _FakeSession()
    session.results = [
        _Result(
            one_or_none=_Row(
                {
                    "job_id": "99999999-9999-9999-9999-999999999999",
                    "enterprise_id": _ENTERPRISE_ID,
                    "job_type": "metadata_batch",
                    "kb_id": _KB_ID,
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "document_version_id": "55555555-5555-5555-5555-555555555555",
                    "status": "running",
                    "stage": "parse",
                    "request_json": {
                        "document_ids": ["44444444-4444-4444-4444-444444444444"]
                    },
                    "result_json": {},
                    "error_message": None,
                    "attempt_count": 1,
                    "max_attempts": 3,
                    "cancel_requested_at": None,
                }
            )
        ),
        _Result(one=_job_row(status="retrying", stage="parse")),
    ]
    service = ImportService()
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    job = service.mark_claimed_job_failed(
        session,
        job_id="99999999-9999-9999-9999-999999999999",
        worker_id="worker_1",
        error_code="TEMPORARY_FAILURE",
        error_message="temporary unavailable",
        retryable=True,
    )

    assert job.status == "retrying"
    update_params = session.executed[1][1]
    assert update_params["status"] == "retrying"
