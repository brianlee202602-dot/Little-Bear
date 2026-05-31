"""Role binding read helpers for admin services."""

from __future__ import annotations

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.mappers import _role_binding_from_mapping
from app.modules.admin.schemas import AdminRoleBinding
from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminRoleBindingReader:
    """读取用户角色绑定。"""

    def load_role_bindings(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> list[AdminRoleBinding]:
        rows = session.execute(
            text(
                """
                SELECT
                    rb.id::text AS binding_id,
                    rb.role_id::text AS role_id,
                    rb.user_id::text AS user_id,
                    rb.scope_type,
                    rb.scope_id::text AS scope_id,
                    r.code AS role_code,
                    r.name AS role_name
                FROM role_bindings rb
                JOIN roles r ON r.id = rb.role_id
                WHERE rb.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND rb.user_id = CAST(:user_id AS uuid)
                  AND rb.status = 'active'
                ORDER BY r.code, rb.created_at
                """
            ),
            {"enterprise_id": enterprise_id, "user_id": user_id},
        ).all()
        return [_role_binding_from_mapping(row._mapping) for row in rows]

    def load_role_binding(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        binding_id: str,
    ) -> AdminRoleBinding:
        row = session.execute(
            text(
                """
                SELECT
                    rb.id::text AS binding_id,
                    rb.role_id::text AS role_id,
                    rb.user_id::text AS user_id,
                    rb.scope_type,
                    rb.scope_id::text AS scope_id,
                    r.code AS role_code,
                    r.name AS role_name
                FROM role_bindings rb
                JOIN roles r ON r.id = rb.role_id
                WHERE rb.id = CAST(:binding_id AS uuid)
                  AND rb.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND rb.user_id = CAST(:user_id AS uuid)
                  AND rb.status = 'active'
                LIMIT 1
                """
            ),
            {"binding_id": binding_id, "enterprise_id": enterprise_id, "user_id": user_id},
        ).one_or_none()
        if row is None:
            raise AdminServiceError(
                "ADMIN_ROLE_BINDING_NOT_FOUND",
                "role binding does not exist",
                status_code=404,
            )
        return _role_binding_from_mapping(row._mapping)

    def user_has_role(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        role_code: str,
    ) -> bool:
        row = session.execute(
            text(
                """
                SELECT 1
                FROM role_bindings rb
                JOIN roles r ON r.id = rb.role_id
                WHERE rb.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND rb.user_id = CAST(:user_id AS uuid)
                  AND rb.status = 'active'
                  AND r.code = :role_code
                LIMIT 1
                """
            ),
            {"enterprise_id": enterprise_id, "user_id": user_id, "role_code": role_code},
        ).one_or_none()
        return row is not None

