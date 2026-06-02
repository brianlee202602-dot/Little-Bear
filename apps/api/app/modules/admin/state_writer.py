"""Shared state mutation helpers for admin services."""

from __future__ import annotations

from typing import Any

from app.modules.audit import AuditWriter
from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminStateWriterMixin:
    """管理后台权限、组织、会话和审计状态写入 helper。"""

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

    def _bump_org_version(self, session: Session, enterprise_id: str) -> int:
        row = session.execute(
            text(
                """
                UPDATE enterprises
                SET org_version = org_version + 1,
                    updated_at = now()
                WHERE id = CAST(:enterprise_id AS uuid)
                RETURNING org_version
                """
            ),
            {"enterprise_id": enterprise_id},
        ).one()
        return int(row._mapping["org_version"])

    def _revoke_user_tokens(self, session: Session, user_id: str, *, reason: str) -> int:
        row = session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'revoked',
                    revoked_at = now()
                WHERE subject_user_id = CAST(:user_id AS uuid)
                  AND status = 'active'
                RETURNING jti
                """
            ),
            {"user_id": user_id},
        )
        return len(row.all())

    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
        resource_type: str,
        resource_id: str | None,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        AuditWriter().write(
            session,
            enterprise_id=enterprise_id,
            actor_type="user",
            actor_id=actor_id,
            event_name=event_name,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            risk_level=risk_level,
            summary=summary,
            error_code=error_code,
        )
