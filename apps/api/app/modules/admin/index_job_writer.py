"""Index and permission-refresh job write helpers for admin services."""

from __future__ import annotations

import json
import uuid

from app.modules.admin.mappers import _IndexRebuildTarget
from app.modules.admin.utils import _database_error
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminIndexJobWriterMixin:
    """Compatibility mixin exposing historical AdminService index job writes."""

    def _enqueue_index_delete_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        actor_user_id: str,
        reason: str,
        folder_id: str | None = None,
        document_id: str | None = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        if document_id:
            resource_type = "document"
        elif folder_id:
            resource_type = "folder"
        else:
            resource_type = "knowledge_base"
        request_json = {
            "document_id": document_id,
            "folder_id": folder_id,
            "kb_id": kb_id,
            "reason": reason,
            "resource_type": resource_type,
        }
        session.execute(
            text(
                """
                INSERT INTO import_jobs(
                    id, enterprise_id, job_type, kb_id, document_id, status, stage,
                    request_json, max_attempts, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), 'index_delete',
                    CAST(:kb_id AS uuid), CAST(:document_id AS uuid), 'queued', 'cleanup',
                    CAST(:request_json AS jsonb), 3, CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": job_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "document_id": document_id,
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
                "actor_user_id": actor_user_id,
            },
        )
        return job_id

    def _enqueue_permission_refresh_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        doc_id: str | None,
        actor_user_id: str,
        reason: str,
        permission_snapshot_id: str,
        permission_version: int,
        resource_type: str = "document",
    ) -> str:
        job_id = str(uuid.uuid4())
        request_json = {
            "enterprise_id": enterprise_id,
            "document_id": doc_id,
            "kb_id": kb_id,
            "permission_snapshot_id": permission_snapshot_id,
            "permission_version": permission_version,
            "reason": reason,
            "resource_type": resource_type,
        }
        session.execute(
            text(
                """
                INSERT INTO import_jobs(
                    id, enterprise_id, job_type, kb_id, document_id, status, stage,
                    request_json, max_attempts, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), 'permission_refresh',
                    CAST(:kb_id AS uuid), CAST(:doc_id AS uuid), 'queued', 'index',
                    CAST(:request_json AS jsonb), 3, CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": job_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "doc_id": doc_id,
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
                "actor_user_id": actor_user_id,
            },
        )
        return job_id

    def _enqueue_index_rebuild_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        doc_id: str,
        document_version_id: str,
        actor_user_id: str,
    ) -> str:
        job_id = str(uuid.uuid4())
        request_json = {
            "enterprise_id": enterprise_id,
            "document_ids": [doc_id],
            "document_version_ids": [document_version_id],
            "job_type": "index_rebuild",
            "kb_id": kb_id,
            "reason": "admin_rebuild",
            "rebuild": True,
        }
        session.execute(
            text(
                """
                INSERT INTO import_jobs(
                    id, enterprise_id, job_type, kb_id, document_id,
                    document_version_id, status, stage, request_json,
                    max_attempts, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), 'index_rebuild',
                    CAST(:kb_id AS uuid), CAST(:doc_id AS uuid),
                    CAST(:document_version_id AS uuid), 'queued', 'embed',
                    CAST(:request_json AS jsonb), 3, CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": job_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "doc_id": doc_id,
                "document_version_id": document_version_id,
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
                "actor_user_id": actor_user_id,
            },
        )
        return job_id

    def _enqueue_index_rebuild_batch_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str | None,
        targets: list[_IndexRebuildTarget],
        actor_user_id: str,
    ) -> str:
        job_id = str(uuid.uuid4())
        document_ids = [target.document_id for target in targets]
        document_version_ids = [target.document_version_id for target in targets]
        single_target = targets[0] if len(targets) == 1 else None
        request_json = {
            "enterprise_id": enterprise_id,
            "document_ids": document_ids,
            "document_version_ids": document_version_ids,
            "job_type": "index_rebuild",
            "kb_id": kb_id,
            "reason": "admin_batch_rebuild",
            "rebuild": True,
        }
        session.execute(
            text(
                """
                INSERT INTO import_jobs(
                    id, enterprise_id, job_type, kb_id, document_id,
                    document_version_id, status, stage, request_json,
                    max_attempts, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), 'index_rebuild',
                    CAST(:kb_id AS uuid), CAST(:document_id AS uuid),
                    CAST(:document_version_id AS uuid), 'queued', 'embed',
                    CAST(:request_json AS jsonb), 3, CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": job_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "document_id": single_target.document_id if single_target else None,
                "document_version_id": (
                    single_target.document_version_id if single_target else None
                ),
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
                "actor_user_id": actor_user_id,
            },
        )
        return job_id

    def _enqueue_index_version_cleanup_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str | None,
        document_id: str | None,
        document_version_id: str | None,
        index_version_ids: list[str],
        actor_user_id: str,
    ) -> str:
        job_id = str(uuid.uuid4())
        request_json = {
            "enterprise_id": enterprise_id,
            "document_id": document_id,
            "document_version_id": document_version_id,
            "index_version_ids": index_version_ids,
            "job_type": "index_delete",
            "kb_id": kb_id,
            "reason": "admin_index_version_cleanup",
            "resource_type": "index_version",
        }
        session.execute(
            text(
                """
                INSERT INTO import_jobs(
                    id, enterprise_id, job_type, kb_id, document_id,
                    document_version_id, status, stage, request_json,
                    max_attempts, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), 'index_delete',
                    CAST(:kb_id AS uuid), CAST(:document_id AS uuid),
                    CAST(:document_version_id AS uuid), 'queued', 'cleanup',
                    CAST(:request_json AS jsonb), 3, CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": job_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "document_id": document_id,
                "document_version_id": document_version_id,
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
                "actor_user_id": actor_user_id,
            },
        )
        return job_id

    def _mark_index_rebuild_targets_indexing(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_ids: list[str],
    ) -> None:
        try:
            session.execute(
                text(
                    """
                    UPDATE documents
                    SET index_status = 'indexing',
                        updated_at = now()
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND id = ANY(CAST(:document_ids AS uuid[]))
                    """
                ),
                {"enterprise_id": enterprise_id, "document_ids": document_ids},
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_REBUILD_DOCUMENT_UPDATE_FAILED",
                "document index rebuild state cannot be updated",
                exc,
            ) from exc
