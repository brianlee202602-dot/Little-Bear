"""Import pipeline database repository."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.modules.import_pipeline import request_items as _request_helpers
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import ImportJob
from app.modules.permissions.service import PermissionService
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.orm import Session


class ImportPipelineRepository:
    """导入域 PostgreSQL 读写封装。

    PostgreSQL 是导入任务、权限快照和任务账本的事实源；这里不处理 HTTP 展示、
    外部 provider 或复杂权限决策，只封装本模块需要的 SQL 读写。
    """

    def load_job_by_idempotency(
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

    def load_permission_version(self, session: Session, enterprise_id: str) -> int:
        row = session.execute(
            text(
                """
                SELECT permission_version
                FROM enterprises
                WHERE id = CAST(:enterprise_id AS uuid)
                  AND status = 'active'
                LIMIT 1
                """
            ),
            {"enterprise_id": enterprise_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_ENTERPRISE_UNAVAILABLE",
                "enterprise is not active",
                status_code=409,
                details={"enterprise_id": enterprise_id},
            )
        return int(row._mapping["permission_version"])

    def replace_resource_policy(
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

    def insert_permission_snapshot(
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

    def insert_import_job(
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
        initial_stage: str = "validate",
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
                    CAST(:document_version_id AS uuid), 'queued', :initial_stage,
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
                "initial_stage": initial_stage,
            },
        )

    def load_import_job_row(
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
