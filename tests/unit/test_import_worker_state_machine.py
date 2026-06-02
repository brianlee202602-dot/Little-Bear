from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.service import ImportService

ENTERPRISE_ID = "33333333-3333-3333-3333-333333333333"
KB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOCUMENT_ID = "44444444-4444-4444-4444-444444444444"
DOCUMENT_VERSION_ID = "55555555-5555-5555-5555-555555555555"


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(
        self,
        *,
        one: _Row | None = None,
        one_or_none: _Row | None = None,
    ) -> None:
        self._one = one
        self._one_or_none = one_or_none

    def one(self) -> _Row:
        assert self._one is not None
        return self._one

    def one_or_none(self) -> _Row | None:
        return self._one_or_none


class _StatefulWorkerSession:
    def __init__(self, *, jobs: list[dict[str, object]], now: datetime) -> None:
        self.jobs = jobs
        self.now = now
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement: object, params: dict[str, object] | None = None) -> _Result:
        sql = str(statement)
        query_params = params or {}
        self.executed.append((sql, query_params))
        if "WITH candidate AS" in sql and "UPDATE import_jobs AS job" in sql:
            return _Result(one_or_none=self._claim(query_params))
        if "SELECT enterprise_id::text AS enterprise_id" in sql:
            job = self._job(query_params["job_id"])
            return _Result(one=_Row({"enterprise_id": job["enterprise_id"]}))
        if "cancel_requested_at" in sql and "locked_until > now()" in sql:
            return _Result(one_or_none=self._load_claimed(query_params))
        if "SET stage = :next_stage" in sql:
            return _Result(one=self._advance_stage(query_params))
        if "jsonb_set" in sql and "SET status = :status" in sql:
            return _Result(one=self._mark_failed(query_params))
        if "SET locked_until = :locked_until" in sql:
            self._heartbeat(query_params)
            return _Result()
        raise AssertionError(f"unexpected SQL: {sql}")

    def _claim(self, params: dict[str, object]) -> _Row | None:
        now = params["now"]
        assert isinstance(now, datetime)
        for job in sorted(self.jobs, key=lambda item: item["created_at"]):
            if not self._can_claim(job, now):
                continue
            job["status"] = "running"
            if job["stage"] == "finished":
                job["stage"] = "validate"
            job["attempt_count"] = int(job["attempt_count"]) + 1
            job["locked_by"] = params["worker_id"]
            job["locked_until"] = params["locked_until"]
            job["next_retry_at"] = None
            job["error_code"] = None
            job["error_message"] = None
            return _Row(_job_response(job))
        return None

    def _can_claim(self, job: dict[str, object], now: datetime) -> bool:
        locked_until = job.get("locked_until")
        lock_released = locked_until is None or locked_until < now
        next_retry_at = job.get("next_retry_at")
        retry_ready = next_retry_at is None or next_retry_at <= now
        return lock_released and (
            (job["status"] in {"queued", "retrying"} and retry_ready)
            or job["status"] == "running"
        )

    def _load_claimed(self, params: dict[str, object]) -> _Row | None:
        job = self._job(params["job_id"])
        if (
            job["locked_by"] != params["worker_id"]
            or job["status"] != "running"
            or job["locked_until"] <= self.now
        ):
            return None
        return _Row(_claimed_job_row(job))

    def _advance_stage(self, params: dict[str, object]) -> _Row:
        job = self._job(params["job_id"])
        assert job["locked_by"] == params["worker_id"]
        assert job["status"] == "running"
        job["stage"] = params["next_stage"]
        return _Row(_job_response(job))

    def _mark_failed(self, params: dict[str, object]) -> _Row:
        job = self._job(params["job_id"])
        assert job["locked_by"] == params["worker_id"]
        assert job["status"] == "running"
        job["status"] = params["status"]
        job["locked_by"] = None
        job["locked_until"] = None
        job["next_retry_at"] = params["next_retry_at"]
        job["error_code"] = params["error_code"]
        job["error_message"] = params["error_message"]
        job["result_json"] = {"last_error": params["error_details_json"]}
        return _Row(_job_response(job))

    def _heartbeat(self, params: dict[str, object]) -> None:
        job = self._job(params["job_id"])
        if job["locked_by"] == params["worker_id"] and job["status"] == "running":
            job["locked_until"] = params["locked_until"]

    def _job(self, job_id: object) -> dict[str, object]:
        for job in self.jobs:
            if job["id"] == job_id:
                return job
        raise AssertionError(f"missing fake job: {job_id}")


def test_worker_claims_multiple_available_jobs_without_duplicate_lock(monkeypatch) -> None:
    now = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    session = _StatefulWorkerSession(
        jobs=[
            _job("99999999-9999-9999-9999-999999999999", created_at=now),
            _job("88888888-8888-8888-8888-888888888888", created_at=now + timedelta(seconds=1)),
        ],
        now=now,
    )
    service = ImportService()
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    first = service.claim_next_job(session, worker_id="worker_1", now=now)
    second = service.claim_next_job(session, worker_id="worker_2", now=now)
    third = service.claim_next_job(session, worker_id="worker_3", now=now)

    assert first is not None
    assert second is not None
    assert first.id == "99999999-9999-9999-9999-999999999999"
    assert second.id == "88888888-8888-8888-8888-888888888888"
    assert third is None
    assert session.jobs[0]["locked_by"] == "worker_1"
    assert session.jobs[1]["locked_by"] == "worker_2"


def test_worker_can_take_over_expired_running_job_lock(monkeypatch) -> None:
    now = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    session = _StatefulWorkerSession(
        jobs=[
            _job(
                "99999999-9999-9999-9999-999999999999",
                status="running",
                stage="chunk",
                attempt_count=1,
                locked_by="dead_worker",
                locked_until=now - timedelta(seconds=1),
                created_at=now,
            )
        ],
        now=now,
    )
    service = ImportService()
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    job = service.claim_next_job(session, worker_id="worker_2", lock_seconds=30, now=now)

    assert job is not None
    assert job.id == "99999999-9999-9999-9999-999999999999"
    assert job.stage == "chunk"
    assert session.jobs[0]["locked_by"] == "worker_2"
    assert session.jobs[0]["attempt_count"] == 2
    assert "OR status = 'running'" in session.executed[0][0]


def test_non_lock_owner_cannot_advance_claimed_job(monkeypatch) -> None:
    now = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    session = _StatefulWorkerSession(
        jobs=[
            _job(
                "99999999-9999-9999-9999-999999999999",
                status="running",
                stage="parse",
                locked_by="worker_1",
                locked_until=now + timedelta(seconds=60),
                created_at=now,
            )
        ],
        now=now,
    )
    stage_effects: list[str] = []
    service = ImportService()
    monkeypatch.setattr(
        service,
        "_apply_stage_effect",
        lambda _session, *, row: stage_effects.append(row["stage"]),
    )

    with pytest.raises(ImportServiceError) as exc_info:
        service.advance_claimed_job(
            session,
            job_id="99999999-9999-9999-9999-999999999999",
            worker_id="worker_2",
        )

    assert exc_info.value.error_code == "IMPORT_JOB_LOCK_REQUIRED"
    assert stage_effects == []
    assert session.jobs[0]["stage"] == "parse"


def test_retryable_failure_releases_lock_and_next_worker_recovers_after_retry_delay(
    monkeypatch,
) -> None:
    now = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    session = _StatefulWorkerSession(
        jobs=[
            _job(
                "99999999-9999-9999-9999-999999999999",
                status="running",
                stage="parse",
                attempt_count=1,
                max_attempts=3,
                locked_by="worker_1",
                locked_until=now + timedelta(seconds=60),
                created_at=now,
            )
        ],
        now=now,
    )
    service = ImportService()
    monkeypatch.setattr(service, "_insert_worker_audit_log", lambda *_args, **_kwargs: None)

    failed = service.mark_claimed_job_failed(
        session,
        job_id="99999999-9999-9999-9999-999999999999",
        worker_id="worker_1",
        error_code="TEMPORARY_FAILURE",
        error_message="temporary unavailable",
        retryable=True,
        retry_delay_seconds=5,
    )
    next_retry_at = session.jobs[0]["next_retry_at"]
    assert isinstance(next_retry_at, datetime)

    too_early = service.claim_next_job(
        session,
        worker_id="worker_2",
        now=next_retry_at - timedelta(milliseconds=1),
    )
    recovered = service.claim_next_job(
        session,
        worker_id="worker_2",
        now=next_retry_at + timedelta(milliseconds=1),
    )

    assert failed.status == "retrying"
    assert too_early is None
    assert recovered is not None
    assert recovered.id == "99999999-9999-9999-9999-999999999999"
    assert recovered.stage == "parse"
    assert session.jobs[0]["locked_by"] == "worker_2"
    assert session.jobs[0]["attempt_count"] == 2


def _job(
    job_id: str,
    *,
    job_type: str = "metadata_batch",
    status: str = "queued",
    stage: str = "validate",
    attempt_count: int = 0,
    max_attempts: int = 3,
    locked_by: str | None = None,
    locked_until: datetime | None = None,
    next_retry_at: datetime | None = None,
    created_at: datetime,
) -> dict[str, object]:
    return {
        "id": job_id,
        "enterprise_id": ENTERPRISE_ID,
        "job_type": job_type,
        "kb_id": KB_ID,
        "document_id": DOCUMENT_ID,
        "document_version_id": DOCUMENT_VERSION_ID,
        "status": status,
        "stage": stage,
        "request_json": {"document_ids": [DOCUMENT_ID]},
        "result_json": {},
        "error_message": None,
        "error_code": None,
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
        "cancel_requested_at": None,
        "locked_by": locked_by,
        "locked_until": locked_until,
        "next_retry_at": next_retry_at,
        "created_at": created_at,
    }


def _job_response(job: dict[str, object]) -> dict[str, object]:
    return {
        "job_id": job["id"],
        "job_type": job["job_type"],
        "kb_id": job["kb_id"],
        "document_id": job["document_id"],
        "document_version_id": job["document_version_id"],
        "status": job["status"],
        "stage": job["stage"],
        "request_json": job["request_json"],
        "result_json": job["result_json"],
        "error_message": job["error_message"],
    }


def _claimed_job_row(job: dict[str, object]) -> dict[str, object]:
    row = _job_response(job)
    row.update(
        {
            "enterprise_id": job["enterprise_id"],
            "attempt_count": job["attempt_count"],
            "max_attempts": job["max_attempts"],
            "cancel_requested_at": job["cancel_requested_at"],
        }
    )
    return row
