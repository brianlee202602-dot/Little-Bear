"""管理后台权限写入器。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.modules.permissions.admin_schemas import PermissionKnowledgeBaseAccessRuleInput
from app.modules.permissions.service import PermissionService
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.orm import Session


class PermissionResourceWriter:
    """写入资源策略、权限快照和访问阻断。"""

    def replace_knowledge_base_access_rules(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        access_rules: tuple[PermissionKnowledgeBaseAccessRuleInput, ...],
        actor_user_id: str,
    ) -> None:
        session.execute(
            text(
                """
                UPDATE knowledge_base_accesses
                SET status = 'revoked',
                    updated_by = CAST(:actor_user_id AS uuid),
                    updated_at = now()
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND kb_id = CAST(:kb_id AS uuid)
                  AND status = 'active'
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "actor_user_id": actor_user_id,
            },
        )
        for rule in access_rules:
            session.execute(
                text(
                    """
                    INSERT INTO knowledge_base_accesses(
                        id, enterprise_id, kb_id, subject_type, subject_id,
                        permission, status, created_by, updated_by
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:kb_id AS uuid),
                        :subject_type, CAST(:subject_id AS uuid), :permission, 'active',
                        CAST(:actor_user_id AS uuid), CAST(:actor_user_id AS uuid)
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "kb_id": kb_id,
                    "subject_type": rule.subject_type,
                    "subject_id": rule.subject_id,
                    "permission": rule.permission,
                    "actor_user_id": actor_user_id,
                },
            )

    def bump_permission_version(self, session: Session, enterprise_id: str) -> int:
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

    def load_resource_permission_version(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
    ) -> int:
        row = session.execute(
            text(
                """
                SELECT permission_version
                FROM permission_snapshots
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND resource_type = :resource_type
                  AND resource_id = CAST(:resource_id AS uuid)
                ORDER BY created_at DESC, permission_version DESC
                LIMIT 1
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        ).one_or_none()
        if row is not None:
            return int(row._mapping["permission_version"])
        row = session.execute(
            text(
                """
                SELECT permission_version
                FROM enterprises
                WHERE id = CAST(:enterprise_id AS uuid)
                LIMIT 1
                """
            ),
            {"enterprise_id": enterprise_id},
        ).one()
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
        PermissionService().validate_visibility_policy(
            {"owner_department_id": owner_department_id, "visibility": visibility}
        )
        policy_id = str(uuid.uuid4())
        policy = {
            "owner_department_id": owner_department_id,
            "visibility": visibility,
        }
        policy_hash = stable_json_hash(policy)
        session.execute(
            text(
                """
                UPDATE resource_policies
                SET status = 'archived', archived_at = now()
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND resource_type = :resource_type
                  AND resource_id = CAST(:resource_id AS uuid)
                  AND status = 'active'
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
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
                "payload_json": json.dumps(
                    snapshot["payload"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "payload_hash": snapshot["payload_hash"],
                "owner_department_id": owner_department_id,
                "visibility": visibility,
            },
        )
        return {"snapshot_id": snapshot_id, "payload_hash": snapshot["payload_hash"]}

    def insert_access_block(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
        reason: str,
        block_level: str,
        actor_user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        access_block_id = str(uuid.uuid4())
        session.execute(
            text(
                """
                INSERT INTO access_blocks(
                    id, enterprise_id, resource_type, resource_id, reason, block_level,
                    status, created_by, metadata_json
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :resource_type,
                    CAST(:resource_id AS uuid), :reason, :block_level, 'active',
                    CAST(:actor_user_id AS uuid), CAST(:metadata_json AS jsonb)
                )
                """
            ),
            {
                "id": access_block_id,
                "enterprise_id": enterprise_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "reason": reason,
                "block_level": block_level,
                "actor_user_id": actor_user_id,
                "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            },
        )
        return access_block_id


class PermissionRefreshJobWriter:
    """写入权限 payload 刷新任务。"""

    def enqueue_permission_refresh_job(
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
