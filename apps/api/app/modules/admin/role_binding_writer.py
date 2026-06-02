"""Role binding and membership write helpers for admin services."""

from __future__ import annotations

import uuid

from app.modules.admin.access_control import AdminActorContext
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import AdminRole, AdminRoleBinding
from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminRoleBindingWriterMixin:
    """管理后台用户部门成员关系和角色绑定写入 helper。"""

    def _insert_department_membership(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        department_id: str,
        actor_user_id: str,
        is_primary: bool,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO user_department_memberships(
                    id, enterprise_id, user_id, department_id, is_primary, status, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:user_id AS uuid),
                    CAST(:department_id AS uuid), :is_primary, 'active',
                    CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "user_id": user_id,
                "department_id": department_id,
                "is_primary": is_primary,
                "actor_user_id": actor_user_id,
            },
        )

    def _insert_role_binding(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        role: AdminRole,
        scope_type: str,
        scope_id: str | None,
        actor_user_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminRoleBinding:
        if role.status != "active":
            raise AdminServiceError(
                "ADMIN_ROLE_INACTIVE",
                "inactive role cannot be granted",
                status_code=409,
                details={"role_code": role.code},
            )
        if scope_type != role.scope_type:
            raise AdminServiceError(
                "ADMIN_ROLE_SCOPE_MISMATCH",
                "binding scope must match role scope",
                status_code=409,
                details={"role_code": role.code, "role_scope_type": role.scope_type},
            )
        normalized_scope_id = None if scope_type == "enterprise" else scope_id
        if scope_type != "enterprise" and not normalized_scope_id:
            raise AdminServiceError(
                "ADMIN_ROLE_SCOPE_REQUIRED",
                "scoped role binding requires scope_id",
                status_code=409,
                details={"role_code": role.code, "scope_type": scope_type},
            )
        self._ensure_role_binding_scope_exists(
            session,
            enterprise_id=enterprise_id,
            scope_type=scope_type,
            scope_id=normalized_scope_id,
        )
        self._ensure_actor_can_manage_role_scope(
            actor_context,
            role=role,
            scope_type=scope_type,
            scope_id=normalized_scope_id,
        )
        binding_id = str(uuid.uuid4())
        session.execute(
            text(
                """
                INSERT INTO role_bindings(
                    id, enterprise_id, user_id, role_id, scope_type, scope_id, status, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:user_id AS uuid),
                    CAST(:role_id AS uuid), :scope_type, CAST(:scope_id AS uuid),
                    'active', CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": binding_id,
                "enterprise_id": enterprise_id,
                "user_id": user_id,
                "role_id": role.id,
                "scope_type": scope_type,
                "scope_id": normalized_scope_id,
                "actor_user_id": actor_user_id,
            },
        )
        return AdminRoleBinding(
            id=binding_id,
            role_id=role.id,
            subject_type="user",
            subject_id=user_id,
            scope_type=scope_type,
            scope_id=normalized_scope_id,
            role_code=role.code,
            role_name=role.name,
        )

    def _ensure_role_binding_scope_exists(
        self,
        session: Session,
        *,
        enterprise_id: str,
        scope_type: str,
        scope_id: str | None,
    ) -> None:
        if scope_type == "enterprise":
            return
        if scope_type == "department":
            row = session.execute(
                text(
                    """
                    SELECT 1
                    FROM departments
                    WHERE id = CAST(:scope_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"scope_id": scope_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        elif scope_type == "knowledge_base":
            row = session.execute(
                text(
                    """
                    SELECT 1
                    FROM knowledge_bases
                    WHERE id = CAST(:scope_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"scope_id": scope_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        else:
            raise AdminServiceError(
                "ADMIN_ROLE_SCOPE_INVALID",
                "role binding scope_type is invalid",
                status_code=400,
                details={"scope_type": scope_type},
            )
        if row is None:
            raise AdminServiceError(
                "ADMIN_ROLE_SCOPE_NOT_FOUND",
                "role binding scope does not exist",
                status_code=404,
                details={"scope_type": scope_type, "scope_id": scope_id},
            )

    def _ensure_not_last_system_admin(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        confirmed: bool,
    ) -> None:
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "removing admin capability requires confirmation",
                status_code=428,
            )
        row = session.execute(
            text(
                """
                SELECT count(DISTINCT u.id) AS admin_count
                FROM users u
                JOIN role_bindings rb ON rb.user_id = u.id
                JOIN roles r ON r.id = rb.role_id
                WHERE u.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND u.status = 'active'
                  AND u.deleted_at IS NULL
                  AND rb.status = 'active'
                  AND r.code = 'system_admin'
                """
            ),
            {"enterprise_id": enterprise_id},
        ).one()
        has_admin = self.role_binding_reader.user_has_role(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            role_code="system_admin",
        )
        if has_admin and int(row._mapping["admin_count"]) <= 1:
            raise AdminServiceError(
                "ADMIN_LAST_SYSTEM_ADMIN",
                "last active system_admin cannot be removed",
                status_code=409,
            )
