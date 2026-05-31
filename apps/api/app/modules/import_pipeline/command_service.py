"""Import API command and query workflows."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.import_pipeline import request_items as _request_helpers
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import (
    DocumentImportItem,
    ImportActorContext,
    ImportJob,
    ImportJobList,
)
from app.modules.import_pipeline.upload_validation import (
    validate_upload_file as validate_upload_file_policy,
)
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

TERMINAL_STATUSES = {"success", "partial_success", "failed", "cancelled"}


class ImportCommandService:
    """Create, list, read and cancel import jobs."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def validate_upload_file(
        self,
        *,
        filename: str,
        content_type: str | None,
        size_bytes: int,
        file_index: int,
    ) -> str:
        return validate_upload_file_policy(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            file_index=file_index,
            max_upload_bytes=self.owner.max_upload_bytes,
            allowed_file_types=self.owner.allowed_file_types,
        )

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

        self.owner.permission_guard.require_scope(actor_context, "document:import")
        normalized_items = _request_helpers.normalize_items(job_type=job_type, items=items)
        knowledge_base = self.owner.permission_guard.load_knowledge_base(
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
        self.owner.permission_guard.ensure_actor_can_import_to_kb(
            actor_context,
            knowledge_base=knowledge_base,
        )

        if idempotency_key:
            existing = self.owner._load_job_by_idempotency(
                session,
                enterprise_id=enterprise_id,
                actor_user_id=actor_user_id,
                idempotency_key=idempotency_key,
            )
            if existing:
                return existing

        resolved_owner_department_id = self.owner.permission_guard.resolve_owner_department_id(
            session,
            enterprise_id=enterprise_id,
            requested_owner_department_id=owner_department_id,
            default_document_owner_department_id=knowledge_base[
                "default_document_owner_department_id"
            ],
            knowledge_base=knowledge_base,
            actor_context=actor_context,
        )
        resolved_visibility = visibility or knowledge_base["default_document_visibility"]
        self.owner.permission_guard.validate_visibility(
            owner_department_id=resolved_owner_department_id,
            visibility=resolved_visibility,
        )
        self.owner.permission_guard.ensure_document_permission_within_parent_knowledge_base(
            knowledge_base=knowledge_base,
            visibility=resolved_visibility,
            owner_department_id=resolved_owner_department_id,
        )
        if folder_id:
            self.owner.permission_guard.ensure_folder_available(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                folder_id=folder_id,
            )

        permission_version = self.owner._load_permission_version(session, enterprise_id)
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
            policy_id = self.owner._replace_resource_policy(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=document_id,
                owner_department_id=resolved_owner_department_id,
                visibility=resolved_visibility,
                policy_version=1,
                actor_user_id=actor_user_id,
            )
            snapshot = self.owner._insert_permission_snapshot(
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
            self.owner.document_writer.insert_document(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                folder_id=folder_id,
                document_id=document_id,
                title=item.title,
                source_type="upload" if job_type == "upload" else "api",
                source_uri=item.url or _request_helpers.metadata_source_uri(item.metadata),
                owner_department_id=resolved_owner_department_id,
                visibility=resolved_visibility,
                content_hash=content_hash,
                permission_snapshot_id=snapshot["snapshot_id"],
                tags=_request_helpers.metadata_tags(item.metadata),
                actor_user_id=actor_user_id,
            )
            object_key = None
            if job_type == "upload":
                object_key = self.owner.document_writer.store_upload_object(
                    enterprise_id=enterprise_id,
                    kb_id=kb_id,
                    document_id=document_id,
                    actor_user_id=actor_user_id,
                    item=item,
                )
            self.owner.document_writer.insert_document_version(
                session,
                enterprise_id=enterprise_id,
                document_id=document_id,
                document_version_id=document_version_id,
                object_key=object_key,
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
                    "object_key": object_key,
                    "content_type": item.content_type,
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
        self.owner._insert_import_job(
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
        self.owner._insert_audit_log(
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
        row = self.owner._load_import_job_row(
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
        job_type: str | None = None,
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
        if job_type:
            conditions.append("job_type = :job_type")
            params["job_type"] = job_type
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
        row = self.owner._load_import_job_row(
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
        self.owner._insert_audit_log(
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
