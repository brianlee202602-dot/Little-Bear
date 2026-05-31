"""Permission version read helpers for admin services."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminPermissionVersionReader:
    """读取资源当前权限版本。"""

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

