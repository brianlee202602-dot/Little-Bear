"""Import retry workflows."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.import_pipeline import request_items as _request_helpers
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import ImportJob, ImportJobList
from sqlalchemy.orm import Session


class ImportRetryService:
    """Create retry jobs from failed or cancelled import jobs."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def create_retry(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str,
        owner_only: bool = True,
    ) -> ImportJob:
        row = self.owner._load_import_job_row(
            session,
            job_id=job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )
        return self.create_retry_from_row(
            session,
            row=row,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            retried_from_job_id=job_id,
        )

    def create_index_job_retries(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        job_ids: list[str],
        owner_only: bool = False,
    ) -> ImportJobList:
        normalized_job_ids = _request_helpers.unique_strings(job_ids)
        if not normalized_job_ids:
            raise ImportServiceError(
                "IMPORT_RETRY_JOBS_REQUIRED",
                "index job retry requires at least one job id",
                status_code=400,
            )
        rows = [
            self.owner._load_import_job_row(
                session,
                job_id=job_id,
                enterprise_id=enterprise_id,
                actor_user_id=actor_user_id,
                owner_only=owner_only,
            )
            for job_id in normalized_job_ids
        ]
        invalid_jobs = [
            {
                "job_id": row["job_id"],
                "job_type": row["job_type"],
                "status": row["status"],
            }
            for row in rows
            if row["job_type"] != "index_rebuild"
            or row["status"] not in {"failed", "cancelled"}
        ]
        if invalid_jobs:
            raise ImportServiceError(
                "IMPORT_INDEX_RETRY_NOT_ALLOWED",
                "only failed or cancelled index rebuild jobs can be retried",
                status_code=409,
                details={"invalid_jobs": invalid_jobs},
            )
        jobs = tuple(
            self.create_retry_from_row(
                session,
                row=row,
                enterprise_id=enterprise_id,
                actor_user_id=actor_user_id,
                retried_from_job_id=row["job_id"],
                risk_level="high",
                batch_job_ids=normalized_job_ids,
            )
            for row in rows
        )
        return ImportJobList(items=jobs, total=len(jobs))

    def create_retry_from_row(
        self,
        session: Session,
        *,
        row: Any,
        enterprise_id: str,
        actor_user_id: str,
        retried_from_job_id: str,
        risk_level: str = "medium",
        batch_job_ids: list[str] | None = None,
    ) -> ImportJob:
        if row["status"] not in {"failed", "cancelled"}:
            raise ImportServiceError(
                "IMPORT_RETRY_NOT_ALLOWED",
                "only failed or cancelled import jobs can be retried",
                status_code=409,
                details={"status": row["status"]},
            )
        request_json = _request_helpers.json_mapping(row["request_json"])
        retry_job_id = str(uuid.uuid4())
        retry_request_json = {
            **request_json,
            "retried_from_job_id": retried_from_job_id,
        }
        initial_stage = "embed" if row["job_type"] == "index_rebuild" else "validate"
        self.owner._insert_import_job(
            session,
            enterprise_id=enterprise_id,
            job_id=retry_job_id,
            job_type=row["job_type"],
            kb_id=row["kb_id"],
            document_id=row["document_id"],
            document_version_id=row["document_version_id"],
            request_json=retry_request_json,
            idempotency_key=None,
            actor_user_id=actor_user_id,
            initial_stage=initial_stage,
        )
        self.owner._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="import_job.retry_created",
            resource_type="import_job",
            resource_id=retry_job_id,
            action="retry",
            result="success",
            risk_level=risk_level,
            summary={
                "retried_from_job_id": retried_from_job_id,
                "batch_job_ids": batch_job_ids or [],
            },
        )
        return ImportJob(
            id=retry_job_id,
            kb_id=row["kb_id"],
            status="queued",
            stage=initial_stage,
            document_ids=tuple(
                _request_helpers.document_ids_from_request(
                    retry_request_json,
                    row["document_id"],
                )
            ),
            job_type=row["job_type"],
        )
