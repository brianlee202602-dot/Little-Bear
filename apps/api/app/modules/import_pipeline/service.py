"""Import Service 与 Worker 状态推进。

P0-4 先实现“创建导入任务 -> Worker 领取 -> 阶段推进”的最小闭环。真正的
对象存储、解析器、chunk 写入和索引发布在后续 P0-5 接入端口与 adapter。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import (
    DocumentImportItem,
    ImportActorContext,
    ImportJob,
    ImportJobList,
)
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.runtime import build_indexing_service
from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.service import PermissionService
from app.shared.context import get_request_context
from app.shared.json_utils import stable_json_hash
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
TERMINAL_STATUSES = {"success", "partial_success", "failed", "cancelled"}


class ImportService:
    """导入任务写模型和 Worker 任务状态机。"""

    def create_document_import(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        actor_user_id: str,
        job_type: str,
        items: list[DocumentImportItem],
        owner_department_id: str | None = None,
        visibility: str | None = None,
        folder_id: str | None = None,
        idempotency_key: str | None = None,
        actor_context: ImportActorContext | None = None,
    ) -> ImportJob:
        """创建 upload、URL 或 metadata_batch 导入任务，并预创建文档与 draft 版本。"""

        _require_scope(actor_context, "document:import")
        normalized_items = _normalize_items(job_type=job_type, items=items)
        knowledge_base = self._load_knowledge_base(
            session,
            enterprise_id=enterprise_id,
            kb_id=kb_id,
        )
        if knowledge_base["status"] != "active":
            raise ImportServiceError(
                "IMPORT_KB_UNAVAILABLE",
                "knowledge base is not active",
                status_code=409,
                details={"kb_id": kb_id, "status": knowledge_base["status"]},
            )
        _ensure_actor_can_import_to_kb(actor_context, kb_id=kb_id)

        if idempotency_key:
            existing = self._load_job_by_idempotency(
                session,
                enterprise_id=enterprise_id,
                actor_user_id=actor_user_id,
                idempotency_key=idempotency_key,
            )
            if existing:
                return existing

        resolved_owner_department_id = self._resolve_owner_department_id(
            session,
            enterprise_id=enterprise_id,
            requested_owner_department_id=owner_department_id,
            knowledge_base_owner_department_id=knowledge_base["owner_department_id"],
            actor_context=actor_context,
        )
        resolved_visibility = visibility or knowledge_base["default_visibility"]
        self._validate_visibility(
            owner_department_id=resolved_owner_department_id,
            visibility=resolved_visibility,
        )
        if folder_id:
            self._ensure_folder_available(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                folder_id=folder_id,
            )

        permission_version = self._bump_permission_version(session, enterprise_id)
        document_ids: list[str] = []
        document_version_ids: list[str] = []
        request_items: list[dict[str, Any]] = []
        for item in normalized_items:
            document_id = str(uuid.uuid4())
            document_version_id = str(uuid.uuid4())
            content_payload = {
                "job_type": job_type,
                "title": item.title,
                "url": item.url,
                "metadata": item.metadata,
            }
            content_hash = stable_json_hash(content_payload)
            policy_id = self._replace_resource_policy(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=document_id,
                owner_department_id=resolved_owner_department_id,
                visibility=resolved_visibility,
                policy_version=1,
                actor_user_id=actor_user_id,
            )
            snapshot = self._insert_permission_snapshot(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=document_id,
                owner_department_id=resolved_owner_department_id,
                visibility=resolved_visibility,
                permission_version=permission_version,
                policy_version=1,
                policy_id=policy_id,
            )
            self._insert_document(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                folder_id=folder_id,
                document_id=document_id,
                title=item.title,
                source_type="upload" if job_type == "upload" else "api",
                source_uri=item.url or _metadata_source_uri(item.metadata),
                owner_department_id=resolved_owner_department_id,
                visibility=resolved_visibility,
                content_hash=content_hash,
                permission_snapshot_id=snapshot["snapshot_id"],
                tags=_metadata_tags(item.metadata),
                actor_user_id=actor_user_id,
            )
            self._insert_document_version(
                session,
                enterprise_id=enterprise_id,
                document_id=document_id,
                document_version_id=document_version_id,
                object_key=item.url,
                content_hash=content_hash,
                actor_user_id=actor_user_id,
            )
            document_ids.append(document_id)
            document_version_ids.append(document_version_id)
            request_items.append(
                {
                    "document_id": document_id,
                    "document_version_id": document_version_id,
                    "title": item.title,
                    "url": item.url,
                    "metadata": item.metadata,
                    "content_hash": content_hash,
                }
            )

        job_id = str(uuid.uuid4())
        request_json = {
            "job_type": job_type,
            "kb_id": kb_id,
            "document_ids": document_ids,
            "document_version_ids": document_version_ids,
            "owner_department_id": resolved_owner_department_id,
            "visibility": resolved_visibility,
            "folder_id": folder_id,
            "items": request_items,
        }
        self._insert_import_job(
            session,
            enterprise_id=enterprise_id,
            job_id=job_id,
            job_type=job_type,
            kb_id=kb_id,
            document_id=document_ids[0],
            document_version_id=document_version_ids[0],
            request_json=request_json,
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
        )
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="import_job.created",
            resource_type="import_job",
            resource_id=job_id,
            action="create",
            result="success",
            risk_level="high",
            summary={
                "job_type": job_type,
                "kb_id": kb_id,
                "document_ids": document_ids,
                "permission_version": permission_version,
            },
        )
        return ImportJob(
            id=job_id,
            kb_id=kb_id,
            status="queued",
            stage="validate",
            document_ids=tuple(document_ids),
            job_type=job_type,
        )

    def get_import_job(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str | None = None,
        owner_only: bool = True,
    ) -> ImportJob:
        row = self._load_import_job_row(
            session,
            job_id=job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )
        return _job_from_mapping(row)

    def list_import_jobs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        status: str | None = None,
        stage: str | None = None,
        kb_id: str | None = None,
        actor_user_id: str | None = None,
        owner_only: bool = True,
    ) -> ImportJobList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = ["enterprise_id = CAST(:enterprise_id AS uuid)"]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if owner_only:
            conditions.append("created_by = CAST(:actor_user_id AS uuid)")
            params["actor_user_id"] = actor_user_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if stage:
            conditions.append("stage = :stage")
            params["stage"] = stage
        if kb_id:
            conditions.append("kb_id = CAST(:kb_id AS uuid)")
            params["kb_id"] = kb_id
        where_sql = " AND ".join(conditions)
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS job_id,
                        job_type,
                        kb_id::text AS kb_id,
                        document_id::text AS document_id,
                        document_version_id::text AS document_version_id,
                        status,
                        stage,
                        request_json,
                        result_json,
                        error_message
                    FROM import_jobs
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM import_jobs WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "IMPORT_JOBS_UNAVAILABLE",
                "import jobs cannot be read",
                exc,
            ) from exc
        return ImportJobList(
            items=tuple(_job_from_mapping(row._mapping) for row in rows),
            total=int(total_row._mapping["total"]),
        )

    def request_cancel(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str,
        owner_only: bool = True,
    ) -> ImportJob:
        row = self._load_import_job_row(
            session,
            job_id=job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )
        current = row["status"]
        if current in TERMINAL_STATUSES:
            return _job_from_mapping(row)

        if current in {"queued", "retrying"}:
            update_sql = """
                UPDATE import_jobs
                SET status = 'cancelled',
                    cancel_requested_at = now(),
                    cancel_requested_by = CAST(:actor_user_id AS uuid),
                    locked_by = NULL,
                    locked_until = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                RETURNING
                    id::text AS job_id, job_type, kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status, stage, request_json, result_json, error_message
            """
            event_name = "import_job.cancelled"
        else:
            update_sql = """
                UPDATE import_jobs
                SET cancel_requested_at = COALESCE(cancel_requested_at, now()),
                    cancel_requested_by = COALESCE(
                        cancel_requested_by,
                        CAST(:actor_user_id AS uuid)
                    ),
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                RETURNING
                    id::text AS job_id, job_type, kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status, stage, request_json, result_json, error_message
            """
            event_name = "import_job.cancel_requested"

        updated = session.execute(
            text(update_sql),
            {
                "job_id": job_id,
                "enterprise_id": enterprise_id,
                "actor_user_id": actor_user_id,
            },
        ).one()
        job = _job_from_mapping(updated._mapping)
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name=event_name,
            resource_type="import_job",
            resource_id=job.id,
            action="cancel",
            result="success",
            risk_level="medium",
            summary={"previous_status": current, "status": job.status, "stage": job.stage},
        )
        return job

    def create_retry(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str,
        owner_only: bool = True,
    ) -> ImportJob:
        row = self._load_import_job_row(
            session,
            job_id=job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )
        if row["status"] not in {"failed", "cancelled"}:
            raise ImportServiceError(
                "IMPORT_RETRY_NOT_ALLOWED",
                "only failed or cancelled import jobs can be retried",
                status_code=409,
                details={"status": row["status"]},
            )
        request_json = _json_mapping(row["request_json"])
        retry_job_id = str(uuid.uuid4())
        retry_request_json = {
            **request_json,
            "retried_from_job_id": job_id,
        }
        self._insert_import_job(
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
        )
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="import_job.retry_created",
            resource_type="import_job",
            resource_id=retry_job_id,
            action="retry",
            result="success",
            risk_level="medium",
            summary={"retried_from_job_id": job_id},
        )
        return ImportJob(
            id=retry_job_id,
            kb_id=row["kb_id"],
            status="queued",
            stage="validate",
            document_ids=tuple(_document_ids_from_request(retry_request_json, row["document_id"])),
            job_type=row["job_type"],
        )

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
        self._insert_worker_audit_log(
            session,
            enterprise_id=self._job_enterprise_id(session, job.id),
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
        row = self._load_claimed_job(session, job_id=job_id, worker_id=worker_id)
        if row["cancel_requested_at"] is not None:
            return self._cancel_claimed_job(session, row=row, worker_id=worker_id)

        self._apply_stage_effect(session, row=row)
        next_stage = _next_stage(row["stage"])
        if next_stage is None:
            return self._succeed_claimed_job(session, row=row, worker_id=worker_id)
        if next_stage == "finished":
            return self._succeed_claimed_job(session, row=row, worker_id=worker_id)

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
        self._insert_worker_audit_log(
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
        retry_delay_seconds: int = 60,
    ) -> ImportJob:
        row = self._load_claimed_job(session, job_id=job_id, worker_id=worker_id)
        should_retry = retryable and int(row["attempt_count"]) < int(row["max_attempts"])
        status = "retrying" if should_retry else "failed"
        next_retry_at = datetime.now(UTC) + timedelta(seconds=max(retry_delay_seconds, 1))
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
            },
        ).one()
        job = _job_from_mapping(updated._mapping)
        self._insert_worker_audit_log(
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.retry_scheduled" if should_retry else "import_job.failed",
            resource_id=job.id,
            summary={
                "worker_id": worker_id,
                "status": status,
                "error_code": error_code,
                "retryable": retryable,
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

    def _apply_stage_effect(self, session: Session, *, row: Any) -> None:
        stage = row["stage"]
        if stage == "validate":
            self._mark_documents_indexing(session, request_json=_json_mapping(row["request_json"]))
            return
        if stage == "parse":
            self._mark_versions_parsed(session, request_json=_json_mapping(row["request_json"]))
            return
        if stage == "clean":
            self._mark_versions_cleaned(session, request_json=_json_mapping(row["request_json"]))
            return
        if stage == "chunk":
            self._write_draft_chunks(session, request_json=_json_mapping(row["request_json"]))
            return
        if stage not in {"embed", "index", "publish"}:
            return
        try:
            indexing_service = build_indexing_service(session)
            if stage == "embed":
                indexing_service.create_draft_indexes(
                    session,
                    request_json=_json_mapping(row["request_json"]),
                )
                return
            if stage == "index":
                indexing_service.write_draft_indexes(
                    session,
                    request_json=_json_mapping(row["request_json"]),
                )
                return
            if stage == "publish":
                indexing_service.publish_ready_indexes(
                    session,
                    request_json=_json_mapping(row["request_json"]),
                )
                return
        except IndexingServiceError as exc:
            raise ImportServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def _mark_documents_indexing(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> None:
        document_ids = _document_ids_from_request(request_json, None)
        if not document_ids:
            raise ImportServiceError(
                "IMPORT_DOCUMENTS_REQUIRED",
                "import job request does not include document ids",
                status_code=409,
            )
        session.execute(
            text(
                """
                UPDATE documents
                SET index_status = 'indexing',
                    updated_at = now()
                WHERE id = ANY(CAST(:document_ids AS uuid[]))
                  AND index_status IN ('none', 'index_failed')
                  AND lifecycle_status = 'draft'
                """
            ),
            {"document_ids": document_ids},
        )

    def _mark_versions_parsed(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> None:
        document_version_ids = _document_version_ids_from_request(request_json, None)
        if not document_version_ids:
            raise ImportServiceError(
                "IMPORT_DOCUMENT_VERSIONS_REQUIRED",
                "import job request does not include document version ids",
                status_code=409,
            )
        session.execute(
            text(
                """
                UPDATE document_versions
                SET status = CASE WHEN status = 'draft' THEN 'parsed' ELSE status END,
                    parser_version = COALESCE(parser_version, 'plain-text-p0'),
                    parsed_object_key = COALESCE(parsed_object_key, object_key)
                WHERE id = ANY(CAST(:document_version_ids AS uuid[]))
                  AND status IN ('draft', 'parsed')
                """
            ),
            {"document_version_ids": document_version_ids},
        )

    def _mark_versions_cleaned(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> None:
        document_version_ids = _document_version_ids_from_request(request_json, None)
        if not document_version_ids:
            raise ImportServiceError(
                "IMPORT_DOCUMENT_VERSIONS_REQUIRED",
                "import job request does not include document version ids",
                status_code=409,
            )
        session.execute(
            text(
                """
                UPDATE document_versions
                SET cleaned_object_key = COALESCE(cleaned_object_key, parsed_object_key, object_key)
                WHERE id = ANY(CAST(:document_version_ids AS uuid[]))
                  AND status IN ('parsed', 'chunked')
                """
            ),
            {"document_version_ids": document_version_ids},
        )

    def _write_draft_chunks(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> None:
        items = request_json.get("items")
        if not isinstance(items, list) or not items:
            raise ImportServiceError(
                "IMPORT_ITEMS_REQUIRED",
                "import job request does not include items for chunking",
                status_code=409,
            )
        document_version_ids: list[str] = []
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            document_id = item.get("document_id")
            document_version_id = item.get("document_version_id")
            if not isinstance(document_id, str) or not isinstance(document_version_id, str):
                continue
            document_version_ids.append(document_version_id)
            text_content = _item_text_content(item)
            for ordinal, chunk_text in enumerate(_split_plain_text(text_content), start=1):
                preview = chunk_text[:500]
                content_hash = stable_json_hash(
                    {
                        "document_id": document_id,
                        "document_version_id": document_version_id,
                        "ordinal": ordinal,
                        "text": chunk_text,
                    }
                )
                session.execute(
                    text(
                        """
                        INSERT INTO chunks(
                            id, enterprise_id, kb_id, document_id, document_version_id,
                            ordinal, text_preview, heading_path, source_offsets,
                            content_hash, token_count, status, permission_snapshot_id
                        )
                        SELECT
                            CAST(:id AS uuid), d.enterprise_id, d.kb_id, d.id, dv.id,
                            :ordinal, :text_preview, :heading_path,
                            CAST(:source_offsets AS jsonb), :content_hash, :token_count,
                            'draft', d.permission_snapshot_id
                        FROM documents d
                        JOIN document_versions dv
                          ON dv.id = CAST(:document_version_id AS uuid)
                         AND dv.document_id = d.id
                        WHERE d.id = CAST(:document_id AS uuid)
                        ON CONFLICT ON CONSTRAINT uq_chunks_version_ordinal DO NOTHING
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "document_version_id": document_version_id,
                        "ordinal": ordinal,
                        "text_preview": preview,
                        "heading_path": _heading_path(item),
                        "source_offsets": json.dumps(
                            {"item_index": item_index, "chunk_ordinal": ordinal},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "content_hash": content_hash,
                        "token_count": _estimate_token_count(chunk_text),
                    },
                )
        if document_version_ids:
            session.execute(
                text(
                    """
                    UPDATE document_versions
                    SET status = 'chunked',
                        chunker_version = COALESCE(chunker_version, 'plain-text-p0')
                    WHERE id = ANY(CAST(:document_version_ids AS uuid[]))
                      AND status IN ('parsed', 'chunked')
                    """
                ),
                {"document_version_ids": document_version_ids},
            )

    def _load_knowledge_base(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
    ) -> dict[str, Any]:
        row = session.execute(
            text(
                """
                SELECT
                    id::text AS kb_id,
                    owner_department_id::text AS owner_department_id,
                    default_visibility,
                    status,
                    policy_version
                FROM knowledge_bases
                WHERE id = CAST(:kb_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                  AND deleted_at IS NULL
                """
            ),
            {"enterprise_id": enterprise_id, "kb_id": kb_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_KB_NOT_FOUND",
                "knowledge base was not found",
                status_code=404,
                details={"kb_id": kb_id},
            )
        return dict(row._mapping)

    def _resolve_owner_department_id(
        self,
        session: Session,
        *,
        enterprise_id: str,
        requested_owner_department_id: str | None,
        knowledge_base_owner_department_id: str,
        actor_context: ImportActorContext | None,
    ) -> str:
        actor_department_id = (
            actor_context.department_ids[0]
            if actor_context and actor_context.department_ids
            else None
        )
        owner_department_id = (
            requested_owner_department_id
            or actor_department_id
            or knowledge_base_owner_department_id
        )
        row = session.execute(
            text(
                """
                SELECT id::text AS department_id, status
                FROM departments
                WHERE id = CAST(:department_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                  AND deleted_at IS NULL
                """
            ),
            {"enterprise_id": enterprise_id, "department_id": owner_department_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_OWNER_DEPARTMENT_NOT_FOUND",
                "owner department was not found",
                status_code=404,
                details={"owner_department_id": owner_department_id},
            )
        if row._mapping["status"] != "active":
            raise ImportServiceError(
                "IMPORT_OWNER_DEPARTMENT_UNAVAILABLE",
                "owner department is not active",
                status_code=409,
                details={
                    "owner_department_id": owner_department_id,
                    "status": row._mapping["status"],
                },
            )
        if (
            actor_context
            and owner_department_id not in actor_context.department_ids
            and not actor_context.can_import_all_knowledge_bases
        ):
            raise ImportServiceError(
                "IMPORT_OWNER_DEPARTMENT_DENIED",
                "current user cannot import for the requested owner department",
                status_code=403,
                details={"owner_department_id": owner_department_id},
            )
        return owner_department_id

    def _validate_visibility(self, *, owner_department_id: str, visibility: str) -> None:
        try:
            PermissionService().validate_visibility_policy(
                {"owner_department_id": owner_department_id, "visibility": visibility}
            )
        except PermissionServiceError as exc:
            raise ImportServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def _ensure_folder_available(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        folder_id: str,
    ) -> None:
        row = session.execute(
            text(
                """
                SELECT id::text AS folder_id, status
                FROM folders
                WHERE id = CAST(:folder_id AS uuid)
                  AND kb_id = CAST(:kb_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                  AND deleted_at IS NULL
                """
            ),
            {"enterprise_id": enterprise_id, "kb_id": kb_id, "folder_id": folder_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_FOLDER_NOT_FOUND",
                "folder was not found",
                status_code=404,
                details={"folder_id": folder_id},
            )
        if row._mapping["status"] != "active":
            raise ImportServiceError(
                "IMPORT_FOLDER_UNAVAILABLE",
                "folder is not active",
                status_code=409,
                details={"folder_id": folder_id, "status": row._mapping["status"]},
            )

    def _load_job_by_idempotency(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        idempotency_key: str,
    ) -> ImportJob | None:
        row = session.execute(
            text(
                """
                SELECT
                    id::text AS job_id,
                    job_type,
                    kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status,
                    stage,
                    request_json,
                    result_json,
                    error_message
                FROM import_jobs
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND created_by = CAST(:actor_user_id AS uuid)
                  AND idempotency_key = :idempotency_key
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "actor_user_id": actor_user_id,
                "idempotency_key": idempotency_key,
            },
        ).one_or_none()
        return _job_from_mapping(row._mapping) if row else None

    def _bump_permission_version(self, session: Session, enterprise_id: str) -> int:
        row = session.execute(
            text(
                """
                UPDATE enterprises
                SET permission_version = permission_version + 1,
                    updated_at = now()
                WHERE id = CAST(:enterprise_id AS uuid)
                RETURNING permission_version
                """
            ),
            {"enterprise_id": enterprise_id},
        ).one()
        version = int(row._mapping["permission_version"])
        session.execute(
            text(
                """
                INSERT INTO system_state(key, value_json)
                VALUES (
                    'permission_version',
                    jsonb_build_object('version', CAST(:version AS integer))
                )
                ON CONFLICT (key) DO UPDATE
                SET value_json = EXCLUDED.value_json, updated_at = now()
                """
            ),
            {"version": version},
        )
        return version

    def _replace_resource_policy(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
        owner_department_id: str,
        visibility: str,
        policy_version: int,
        actor_user_id: str,
    ) -> str:
        policy_id = str(uuid.uuid4())
        policy = {"owner_department_id": owner_department_id, "visibility": visibility}
        policy_hash = stable_json_hash(policy)
        session.execute(
            text(
                """
                INSERT INTO resource_policies(
                    id, enterprise_id, resource_type, resource_id, version,
                    policy_json, policy_hash, status, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :resource_type,
                    CAST(:resource_id AS uuid), :version,
                    CAST(:policy_json AS jsonb), :policy_hash, 'active',
                    CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": policy_id,
                "enterprise_id": enterprise_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version": policy_version,
                "policy_json": json.dumps(policy, ensure_ascii=False, sort_keys=True),
                "policy_hash": policy_hash,
                "actor_user_id": actor_user_id,
            },
        )
        return policy_id

    def _insert_permission_snapshot(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
        owner_department_id: str,
        visibility: str,
        permission_version: int,
        policy_version: int,
        policy_id: str,
    ) -> dict[str, str]:
        snapshot_id = str(uuid.uuid4())
        snapshot = PermissionService().build_permission_snapshot_payload(
            owner_department_id=owner_department_id,
            visibility=visibility,
            permission_version=permission_version,
            policy_version=policy_version,
        )
        session.execute(
            text(
                """
                INSERT INTO permission_snapshots(
                    id, enterprise_id, resource_type, resource_id, permission_version,
                    policy_id, policy_version, payload_json, payload_hash,
                    owner_department_id, visibility
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :resource_type,
                    CAST(:resource_id AS uuid), :permission_version,
                    CAST(:policy_id AS uuid), :policy_version,
                    CAST(:payload_json AS jsonb), :payload_hash,
                    CAST(:owner_department_id AS uuid), :visibility
                )
                """
            ),
            {
                "id": snapshot_id,
                "enterprise_id": enterprise_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "permission_version": permission_version,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "payload_json": json.dumps(snapshot["payload"], ensure_ascii=False, sort_keys=True),
                "payload_hash": snapshot["payload_hash"],
                "owner_department_id": owner_department_id,
                "visibility": visibility,
            },
        )
        return {"snapshot_id": snapshot_id, "payload_hash": snapshot["payload_hash"]}

    def _insert_document(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        folder_id: str | None,
        document_id: str,
        title: str,
        source_type: str,
        source_uri: str | None,
        owner_department_id: str,
        visibility: str,
        content_hash: str,
        permission_snapshot_id: str,
        tags: list[str],
        actor_user_id: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO documents(
                    id, enterprise_id, kb_id, folder_id, title, source_type, source_uri,
                    lifecycle_status, index_status, owner_department_id, visibility,
                    content_hash, permission_snapshot_id, tags, created_by, updated_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:kb_id AS uuid),
                    CAST(:folder_id AS uuid), :title, :source_type, :source_uri,
                    'draft', 'none', CAST(:owner_department_id AS uuid), :visibility,
                    :content_hash, CAST(:permission_snapshot_id AS uuid), :tags,
                    CAST(:actor_user_id AS uuid), CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": document_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "folder_id": folder_id,
                "title": title,
                "source_type": source_type,
                "source_uri": source_uri,
                "owner_department_id": owner_department_id,
                "visibility": visibility,
                "content_hash": content_hash,
                "permission_snapshot_id": permission_snapshot_id,
                "tags": tags,
                "actor_user_id": actor_user_id,
            },
        )

    def _insert_document_version(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_id: str,
        document_version_id: str,
        object_key: str | None,
        content_hash: str,
        actor_user_id: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO document_versions(
                    id, enterprise_id, document_id, version_no, object_key,
                    content_hash, status, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid),
                    CAST(:document_id AS uuid), 1, :object_key,
                    :content_hash, 'draft', CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": document_version_id,
                "enterprise_id": enterprise_id,
                "document_id": document_id,
                "object_key": object_key,
                "content_hash": content_hash,
                "actor_user_id": actor_user_id,
            },
        )

    def _insert_import_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        job_id: str,
        job_type: str,
        kb_id: str | None,
        document_id: str | None,
        document_version_id: str | None,
        request_json: dict[str, Any],
        idempotency_key: str | None,
        actor_user_id: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO import_jobs(
                    id, enterprise_id, job_type, kb_id, document_id, document_version_id,
                    status, stage, request_json, idempotency_key, max_attempts, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :job_type,
                    CAST(:kb_id AS uuid), CAST(:document_id AS uuid),
                    CAST(:document_version_id AS uuid), 'queued', 'validate',
                    CAST(:request_json AS jsonb), :idempotency_key, 3,
                    CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": job_id,
                "enterprise_id": enterprise_id,
                "job_type": job_type,
                "kb_id": kb_id,
                "document_id": document_id,
                "document_version_id": document_version_id,
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
                "idempotency_key": idempotency_key,
                "actor_user_id": actor_user_id,
            },
        )

    def _load_import_job_row(
        self,
        session: Session,
        *,
        job_id: str,
        enterprise_id: str,
        actor_user_id: str | None,
        owner_only: bool,
    ) -> Any:
        conditions = [
            "id = CAST(:job_id AS uuid)",
            "enterprise_id = CAST(:enterprise_id AS uuid)",
        ]
        params: dict[str, Any] = {"job_id": job_id, "enterprise_id": enterprise_id}
        if owner_only:
            conditions.append("created_by = CAST(:actor_user_id AS uuid)")
            params["actor_user_id"] = actor_user_id
        where_sql = " AND ".join(conditions)
        row = session.execute(
            text(
                f"""
                SELECT
                    id::text AS job_id,
                    job_type,
                    kb_id::text AS kb_id,
                    document_id::text AS document_id,
                    document_version_id::text AS document_version_id,
                    status,
                    stage,
                    request_json,
                    result_json,
                    error_message
                FROM import_jobs
                WHERE {where_sql}
                """
            ),
            params,
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_JOB_NOT_FOUND",
                "import job was not found",
                status_code=404,
                details={"job_id": job_id},
            )
        return row._mapping

    def _load_claimed_job(self, session: Session, *, job_id: str, worker_id: str) -> Any:
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

    def _cancel_claimed_job(self, session: Session, *, row: Any, worker_id: str) -> ImportJob:
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
        self._insert_worker_audit_log(
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.cancelled",
            resource_id=job.id,
            summary={"worker_id": worker_id, "stage": job.stage},
        )
        return job

    def _succeed_claimed_job(self, session: Session, *, row: Any, worker_id: str) -> ImportJob:
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
        self._insert_worker_audit_log(
            session,
            enterprise_id=row["enterprise_id"],
            event_name="import_job.succeeded",
            resource_id=job.id,
            summary={"worker_id": worker_id},
        )
        return job

    def _job_enterprise_id(self, session: Session, job_id: str) -> str:
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

    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, enterprise_id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level, summary_json, error_code
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id, :trace_id,
                    :event_name, 'user', :actor_id, :resource_type, :resource_id,
                    :action, :result, :risk_level, CAST(:summary_json AS jsonb), :error_code
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "result": result,
                "risk_level": risk_level,
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
                "error_code": error_code,
            },
        )

    def _insert_worker_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        event_name: str,
        resource_id: str,
        summary: dict[str, Any],
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, enterprise_id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level, summary_json
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id, :trace_id,
                    :event_name, 'system', :actor_id, 'import_job', :resource_id,
                    'worker_update', 'success', 'low', CAST(:summary_json AS jsonb)
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "actor_id": str(summary.get("worker_id", "worker")),
                "resource_id": resource_id,
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
            },
        )


def _normalize_items(*, job_type: str, items: list[DocumentImportItem]) -> list[DocumentImportItem]:
    if job_type not in {"upload", "url", "metadata_batch"}:
        raise ImportServiceError(
            "IMPORT_JOB_TYPE_INVALID",
            "document import job_type must be upload, url or metadata_batch",
            status_code=400,
            details={"job_type": job_type},
        )
    if not items:
        raise ImportServiceError(
            "IMPORT_ITEMS_REQUIRED",
            "document import requires at least one item",
            status_code=400,
        )
    normalized: list[DocumentImportItem] = []
    for index, item in enumerate(items):
        title = item.title.strip()
        if not title:
            raise ImportServiceError(
                "IMPORT_ITEM_TITLE_REQUIRED",
                "document import item title is required",
                status_code=400,
                details={"item_index": index},
            )
        if job_type == "url" and not item.url:
            raise ImportServiceError(
                "IMPORT_ITEM_URL_REQUIRED",
                "url import item requires url",
                status_code=400,
                details={"item_index": index},
            )
        if job_type == "upload" and not _metadata_text(item.metadata):
            raise ImportServiceError(
                "IMPORT_ITEM_CONTENT_REQUIRED",
                "upload import item requires text content",
                status_code=400,
                details={"item_index": index},
            )
        normalized.append(
            DocumentImportItem(
                title=title,
                url=item.url.strip() if item.url else None,
                metadata=item.metadata,
            )
        )
    return normalized


def _require_scope(actor_context: ImportActorContext | None, required_scope: str) -> None:
    if actor_context is None or not _has_scope(actor_context.scopes, required_scope):
        raise ImportServiceError(
            "IMPORT_SCOPE_REQUIRED",
            "current user does not include required scope",
            status_code=403,
            details={"required_scope": required_scope},
        )


def _ensure_actor_can_import_to_kb(actor_context: ImportActorContext | None, *, kb_id: str) -> None:
    if actor_context is None:
        return
    if actor_context.can_import_all_knowledge_bases:
        return
    if kb_id in actor_context.knowledge_base_ids:
        return
    raise ImportServiceError(
        "IMPORT_KB_DENIED",
        "current user cannot import to the requested knowledge base",
        status_code=403,
        details={"kb_id": kb_id},
    )


def _has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes


def _metadata_tags(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("tags")
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        tag = item.strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _metadata_source_uri(metadata: dict[str, Any]) -> str | None:
    filename = metadata.get("filename")
    if isinstance(filename, str) and filename:
        return f"upload://{filename}"
    source_uri = metadata.get("source_uri")
    return source_uri if isinstance(source_uri, str) and source_uri else None


def _metadata_text(metadata: dict[str, Any]) -> str | None:
    for key in ("content", "text", "markdown"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _item_text_content(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    metadata_text = _metadata_text(metadata if isinstance(metadata, dict) else {})
    if metadata_text:
        return metadata_text
    title = item.get("title")
    url = item.get("url")
    parts = [value for value in (title, url) if isinstance(value, str) and value.strip()]
    return "\n".join(parts) or "empty document"


def _heading_path(item: dict[str, Any]) -> str | None:
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        heading = metadata.get("heading_path")
        if isinstance(heading, str) and heading.strip():
            return heading.strip()
    title = item.get("title")
    return title.strip() if isinstance(title, str) and title.strip() else None


def _split_plain_text(text_content: str, *, max_chars: int = 1600) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text_content.replace("\r\n", "\n").split("\n"))
    blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
    if not blocks:
        blocks = [normalized.strip()] if normalized.strip() else ["empty document"]

    chunks: list[str] = []
    current = ""
    for block in blocks:
        if not current:
            current = block
            continue
        if len(current) + len(block) + 2 <= max_chars:
            current = f"{current}\n\n{block}"
            continue
        chunks.extend(_split_long_block(current, max_chars=max_chars))
        current = block
    if current:
        chunks.extend(_split_long_block(current, max_chars=max_chars))
    return chunks


def _split_long_block(block: str, *, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]
    return [block[index : index + max_chars].strip() for index in range(0, len(block), max_chars)]


def _estimate_token_count(text_content: str) -> int:
    # P0 没有 tokenizer 端口，先用字符数近似，后续接模型 tokenizer 后替换。
    return max(1, len(text_content) // 4)


def _job_from_mapping(row: Any) -> ImportJob:
    request_json = _json_mapping(row["request_json"])
    result_json = _json_mapping(row["result_json"])
    return ImportJob(
        id=row["job_id"],
        kb_id=row["kb_id"],
        status=row["status"],
        stage=row["stage"],
        document_ids=tuple(_document_ids_from_request(request_json, row.get("document_id"))),
        error_summary=row["error_message"] or result_json.get("error_summary"),
        job_type=row.get("job_type"),
    )


def _document_ids_from_request(request_json: dict[str, Any], fallback: str | None) -> list[str]:
    value = request_json.get("document_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return [fallback] if fallback else []


def _document_version_ids_from_request(
    request_json: dict[str, Any],
    fallback: str | None,
) -> list[str]:
    value = request_json.get("document_version_ids")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return [fallback] if fallback else []


def _json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


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
