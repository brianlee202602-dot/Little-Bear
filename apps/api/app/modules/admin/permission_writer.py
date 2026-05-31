"""Permission and resource policy write helpers for admin services."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.modules.admin.schemas import AdminKnowledgeBaseAccessRuleInput
from app.modules.permissions.service import PermissionService
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminPermissionWriterMixin:
    """Compatibility mixin exposing historical AdminService permission writes."""

    def _replace_knowledge_base_access_rules(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        access_rules: tuple[AdminKnowledgeBaseAccessRuleInput, ...],
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

    def _insert_access_block(
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
