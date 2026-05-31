"""Import worker state-machine workflows."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.import_pipeline import request_items as _request_helpers
from app.modules.import_pipeline.audit_writer import ImportAuditWriter
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import ImportJob
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

IMPORT_STAGES = (
    "validate",
    "parse",
    "clean",
    "chunk",
    "embed",
    "index",
    "publish",
    "cleanup",
    "finished",
)


class ImportWorkerService:
    """Claim, advance, heartbeat and finish import worker jobs."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def claim_next_job(
        self,
        session: Session,
        *,
        worker_id: str,
        lock_seconds: int = 60,
        now: datetime | None = None,
    ) -> ImportJob | None:
        current_time = now or datetime.now(UTC)
        locked_until = current_time + timedelta(seconds=max(lock_seconds, 1))
        try:
            row = session.execute(
                text(
                    """
                    WITH candidate AS (
                        SELECT id
                        FROM import_jobs
                        WHERE status IN ('queued', 'retrying')
                          AND (next_retry_at IS NULL OR next_retry_at <= :now)
                          AND (locked_until IS NULL OR locked_until < :now)
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE import_jobs AS job
                    SET status = 'running',
                        stage = CASE
                            WHEN job.stage = 'finished' THEN 'validate'
                            ELSE job.stage
                        END,
                        attempt_count = job.attempt_count + 1,
                        locked_by = :worker_id,
                        locked_until = :locked_until,
                        next_retry_at = NULL,
                        error_code = NULL,
                        error_message = NULL,
                        updated_at = :now
                    FROM candidate
                    WHERE job.id = candidate.id
                    RETURNING
                        job.id::text AS job_id,
                        job.job_type,
                        job.kb_id::text AS kb_id,
                        job.document_id::text AS document_id,
                        job.document_version_id::text AS document_version_id,
                        job.status,
                        job.stage,
                        job.request_json,
                        job.result_json,
                        job.error_message
                    """
                ),
                {"worker_id": worker_id, "locked_until": locked_until, "now": current_time},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "IMPORT_CLAIM_FAILED",
                "import job cannot be claimed",
                exc,
            ) from exc
        if row is None:
            return None
        job = _job_from_mapping(row._mapping)
        enterprise_id = _owner_job_enterprise_id(self.owner, session, job.id)
        _owner_worker_audit_log(
            self.owner,
            session,
            enterprise_id=enterprise_id,
            event_name="import_job.claimed",
            resource_id=job.id,
            summary={"worker_id": worker_id, "stage": job.stage},
        )
        return job

    def advance_claimed_job(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
    ) -> ImportJob:
        row = self.load_claimed_job(session, job_id=job_id, worker_id=worker_id)
        if row["cancel_requested_at"] is not None:
            return self.cancel_claimed_job(session, row=row, worker_id=worker_id)

        self.owner._apply_stage_effect(session, row=row)
        next_stage = _next_stage(row["stage"])
        if next_stage is None:
            return self.succeed_claimed_job(session, row=row, worker_id=worker_id)
        if next_stage == "finished":
            return self.succeed_claimed_job(session, row=row, worker_id=worker_id)

        updated = session.execute(
            text(
                """
                UPDATE import_jobs
                SET stage = :next_stage,
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND locked_by = :worker_id
                  AND status = 'running'
                RETURNING
                    id::text AS job_id, job_type, kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status, stage, request_json, result_json, error_message
                """
            ),
            {"job_id": job_id, "worker_id": worker_id, "next_stage": next_stage},
        ).one()
        job = _job_from_mapping(updated._mapping)
        _owner_worker_audit_log(
            self.owner,
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.stage_advanced",
            resource_id=job.id,
            summary={"worker_id": worker_id, "stage": job.stage},
        )
        return job

    def mark_claimed_job_failed(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        error_details: dict[str, Any] | None = None,
        retry_delay_seconds: int = 60,
    ) -> ImportJob:
        row = self.load_claimed_job(session, job_id=job_id, worker_id=worker_id)
        should_retry = retryable and int(row["attempt_count"]) < int(row["max_attempts"])
        status = "retrying" if should_retry else "failed"
        next_retry_at = datetime.now(UTC) + timedelta(seconds=max(retry_delay_seconds, 1))
        error_details_json = json.dumps(
            {
                "error_code": error_code,
                "error_message": error_message[:500],
                "retryable": retryable,
                "details": error_details or {},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        updated = session.execute(
            text(
                """
                UPDATE import_jobs
                SET status = :status,
                    locked_by = NULL,
                    locked_until = NULL,
                    next_retry_at = :next_retry_at,
                    error_code = :error_code,
                    error_message = :error_message,
                    result_json = jsonb_set(
                        COALESCE(result_json, '{}'::jsonb),
                        '{last_error}',
                        CAST(:error_details_json AS jsonb),
                        true
                    ),
                    finished_at = CASE WHEN :status = 'failed' THEN now() ELSE finished_at END,
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND locked_by = :worker_id
                  AND status = 'running'
                RETURNING
                    id::text AS job_id, job_type, kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status, stage, request_json, result_json, error_message
                """
            ),
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "status": status,
                "next_retry_at": next_retry_at if should_retry else None,
                "error_code": error_code,
                "error_message": error_message[:500],
                "error_details_json": error_details_json,
            },
        ).one()
        job = _job_from_mapping(updated._mapping)
        _owner_worker_audit_log(
            self.owner,
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.retry_scheduled" if should_retry else "import_job.failed",
            resource_id=job.id,
            summary={
                "worker_id": worker_id,
                "status": status,
                "error_code": error_code,
                "retryable": retryable,
                "details": error_details or {},
            },
        )
        return job

    def heartbeat_claimed_job(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        lock_seconds: int = 60,
    ) -> None:
        locked_until = datetime.now(UTC) + timedelta(seconds=max(lock_seconds, 1))
        session.execute(
            text(
                """
                UPDATE import_jobs
                SET locked_until = :locked_until,
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND locked_by = :worker_id
                  AND status = 'running'
                """
            ),
            {"job_id": job_id, "worker_id": worker_id, "locked_until": locked_until},
        )

    def load_claimed_job(self, session: Session, *, job_id: str, worker_id: str) -> Any:
        row = session.execute(
            text(
                """
                SELECT
                    id::text AS job_id,
                    enterprise_id::text AS enterprise_id,
                    job_type,
                    kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status,
                    stage,
                    request_json,
                    result_json,
                    error_message,
                    attempt_count,
                    max_attempts,
                    cancel_requested_at
                FROM import_jobs
                WHERE id = CAST(:job_id AS uuid)
                  AND locked_by = :worker_id
                  AND status = 'running'
                  AND locked_until > now()
                """
            ),
            {"job_id": job_id, "worker_id": worker_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_JOB_LOCK_REQUIRED",
                "worker does not hold an active lock for the import job",
                status_code=409,
                details={"job_id": job_id, "worker_id": worker_id},
            )
        return row._mapping

    def cancel_claimed_job(self, session: Session, *, row: Any, worker_id: str) -> ImportJob:
        updated = session.execute(
            text(
                """
                UPDATE import_jobs
                SET status = 'cancelled',
                    locked_by = NULL,
                    locked_until = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND locked_by = :worker_id
                  AND status = 'running'
                RETURNING
                    id::text AS job_id, job_type, kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status, stage, request_json, result_json, error_message
                """
            ),
            {"job_id": row["job_id"], "worker_id": worker_id},
        ).one()
        job = _job_from_mapping(updated._mapping)
        _owner_worker_audit_log(
            self.owner,
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.cancelled",
            resource_id=job.id,
            summary={"worker_id": worker_id, "stage": job.stage},
        )
        return job

    def succeed_claimed_job(self, session: Session, *, row: Any, worker_id: str) -> ImportJob:
        updated = session.execute(
            text(
                """
                UPDATE import_jobs
                SET status = 'success',
                    stage = 'finished',
                    result_json = jsonb_build_object('completed_at', now()),
                    locked_by = NULL,
                    locked_until = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND locked_by = :worker_id
                  AND status = 'running'
                RETURNING
                    id::text AS job_id, job_type, kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status, stage, request_json, result_json, error_message
                """
            ),
            {"job_id": row["job_id"], "worker_id": worker_id},
        ).one()
        job = _job_from_mapping(updated._mapping)
        _owner_worker_audit_log(
            self.owner,
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.succeeded",
            resource_id=job.id,
            summary={"worker_id": worker_id},
        )
        return job

    def job_enterprise_id(self, session: Session, job_id: str) -> str:
        row = session.execute(
            text(
                """
                SELECT enterprise_id::text AS enterprise_id
                FROM import_jobs
                WHERE id = CAST(:job_id AS uuid)
                """
            ),
            {"job_id": job_id},
        ).one()
        return str(row._mapping["enterprise_id"])

    def insert_worker_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        event_name: str,
        resource_id: str,
        summary: dict[str, Any],
    ) -> None:
        ImportAuditWriter().write_worker_event(
            session,
            enterprise_id=enterprise_id,
            event_name=event_name,
            resource_id=resource_id,
            summary=summary,
        )


def _owner_job_enterprise_id(owner: Any, session: Session, job_id: str) -> str:
    return owner._job_enterprise_id(session, job_id)


def _owner_worker_audit_log(
    owner: Any,
    session: Session,
    *,
    enterprise_id: str,
    event_name: str,
    resource_id: str,
    summary: dict[str, Any],
) -> None:
    owner._insert_worker_audit_log(
        session,
        enterprise_id=enterprise_id,
        event_name=event_name,
        resource_id=resource_id,
        summary=summary,
    )


def _job_from_mapping(row: Any) -> ImportJob:
    request_json = _request_helpers.json_mapping(row["request_json"])
    result_json = _request_helpers.json_mapping(row["result_json"])
    return ImportJob(
        id=row["job_id"],
        kb_id=row["kb_id"],
        status=row["status"],
        stage=row["stage"],
        document_ids=tuple(
            _request_helpers.document_ids_from_request(
                request_json,
                row.get("document_id"),
            )
        ),
        error_summary=row["error_message"] or result_json.get("error_summary"),
        job_type=row.get("job_type"),
    )


def _next_stage(stage: str) -> str | None:
    try:
        index = IMPORT_STAGES.index(stage)
    except ValueError:
        raise ImportServiceError(
            "IMPORT_STAGE_INVALID",
            "import job stage is invalid",
            status_code=409,
            details={"stage": stage},
        ) from None
    if index >= len(IMPORT_STAGES) - 1:
        return None
    return IMPORT_STAGES[index + 1]


def _database_error(error_code: str, message: str, exc: SQLAlchemyError) -> ImportServiceError:
    original = getattr(exc, "orig", None) or exc.__cause__
    return ImportServiceError(
        error_code,
        message,
        status_code=500,
        retryable=True,
        details={
            "database_error": {
                "type": exc.__class__.__name__,
                "driver": original.__class__.__name__ if original is not None else None,
            }
        },
    )
