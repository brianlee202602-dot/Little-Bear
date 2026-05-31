"""Role administration service."""

from __future__ import annotations

from typing import Any

from app.modules.admin.access_control import AdminActorContext, RoleBindingInput
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.mappers import (
    _assignable_role_option_from_mapping,
    _role_binding_from_mapping,
    _role_list_item_from_mapping,
)
from app.modules.admin.role_policy import HIGH_RISK_ROLE_CODES, _is_high_risk_role
from app.modules.admin.schemas import (
    AdminAssignableRoleOptionList,
    AdminRole,
    AdminRoleBinding,
    AdminRoleBindingList,
    AdminRoleList,
)
from app.modules.admin.utils import _database_error
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


class AdminRolesService:
    """角色和角色绑定管理写模型。"""

    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_roles(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        scope_type: str | None = None,
    ) -> AdminRoleList:
        """读取角色列表摘要，不暴露 scopes 详情。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = ["enterprise_id = CAST(:enterprise_id AS uuid)"]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if status:
            conditions.append("status = :status")
            params["status"] = status
        else:
            conditions.append("status != 'archived'")
        if scope_type:
            conditions.append("scope_type = :scope_type")
            params["scope_type"] = scope_type
        if keyword:
            conditions.append("(code ILIKE :keyword OR name ILIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT id::text AS role_id, code, name, scope_type, is_builtin, status
                    FROM roles
                    WHERE {where_sql}
                    ORDER BY is_builtin DESC, code
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM roles WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_ROLES_UNAVAILABLE",
                "roles cannot be read",
                exc,
            ) from exc
        return AdminRoleList(
            items=[_role_list_item_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_assignable_role_options(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = "active",
        scope_type: str | None = None,
    ) -> AdminAssignableRoleOptionList:
        """读取可绑定角色选项，返回风险级别但不把 scopes 暴露给前端。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = ["enterprise_id = CAST(:enterprise_id AS uuid)"]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if status:
            conditions.append("status = :status")
            params["status"] = status
        else:
            conditions.append("status != 'archived'")
        if scope_type:
            conditions.append("scope_type = :scope_type")
            params["scope_type"] = scope_type
        if keyword:
            conditions.append("(code ILIKE :keyword OR name ILIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT id::text AS role_id, code, name, scope_type, scopes, is_builtin, status
                    FROM roles
                    WHERE {where_sql}
                    ORDER BY is_builtin DESC, code
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM roles WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_ASSIGNABLE_ROLES_UNAVAILABLE",
                "assignable roles cannot be read",
                exc,
            ) from exc
        return AdminAssignableRoleOptionList(
            items=[_assignable_role_option_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_role(
        self,
        session: Session,
        role_id: str,
        *,
        enterprise_id: str,
    ) -> AdminRole:
        role = self._core_service._load_role(
            session,
            role_id,
            enterprise_id=enterprise_id,
        )
        if role.status == "archived":
            raise AdminServiceError(
                "ADMIN_ROLE_NOT_FOUND",
                "role does not exist",
                status_code=404,
            )
        return role

    def list_role_bindings(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        page: int,
        page_size: int,
        actor_context: AdminActorContext | None = None,
    ) -> AdminRoleBindingList:
        self._core_service._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._core_service._load_user_row(
            session,
            user_id,
            enterprise_id=enterprise_id,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
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
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                "enterprise_id": enterprise_id,
                "user_id": user_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            },
        ).all()
        total_row = session.execute(
            text(
                """
                SELECT count(*) AS total
                FROM role_bindings rb
                WHERE rb.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND rb.user_id = CAST(:user_id AS uuid)
                  AND rb.status = 'active'
                """
            ),
            {"enterprise_id": enterprise_id, "user_id": user_id},
        ).one()
        return AdminRoleBindingList(
            items=[_role_binding_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def create_role_bindings(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        bindings: list[RoleBindingInput],
        confirmed_high_risk: bool,
        actor_context: AdminActorContext | None = None,
    ) -> list[AdminRoleBinding]:
        self._core_service._ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._core_service._load_user_row(
            session,
            user_id,
            enterprise_id=enterprise_id,
        )
        inserted: list[AdminRoleBinding] = []
        roles = [
            self._core_service._load_role(session, item.role_id, enterprise_id=enterprise_id)
            for item in bindings
        ]
        high_risk_roles = [role.code for role in roles if _is_high_risk_role(role)]
        if high_risk_roles and not confirmed_high_risk:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "granting high-risk role requires confirmation",
                status_code=428,
                details={"role_codes": high_risk_roles},
            )
        try:
            for item, role in zip(bindings, roles, strict=True):
                inserted.append(
                    self._core_service._insert_role_binding(
                        session,
                        enterprise_id=enterprise_id,
                        user_id=user_id,
                        role=role,
                        scope_type=item.scope_type,
                        scope_id=item.scope_id,
                        actor_user_id=actor_user_id,
                        actor_context=actor_context,
                    )
                )
        except IntegrityError as exc:
            raise AdminServiceError(
                "ADMIN_ROLE_BINDING_CONFLICT",
                "role binding already exists",
                status_code=409,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_ROLE_BINDING_CREATE_FAILED",
                "role binding cannot be created",
                exc,
            ) from exc

        permission_version = self._core_service._bump_permission_version(
            session,
            enterprise_id,
        )
        for binding in inserted:
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="role_binding.created",
                resource_type="role_binding",
                resource_id=binding.id,
                action="create",
                result="success",
                risk_level="high",
                summary={
                    "binding_id": binding.id,
                    "user_id": user_id,
                    "role_code": binding.role_code,
                    "scope_type": binding.scope_type,
                    "scope_id": binding.scope_id,
                    "permission_version": permission_version,
                },
            )
        return self._core_service._load_role_bindings(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def replace_role_bindings(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        bindings: list[RoleBindingInput],
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> list[AdminRoleBinding]:
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "replacing role bindings requires confirmation",
                status_code=428,
            )
        self._core_service._ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._core_service._load_user_row(
            session,
            user_id,
            enterprise_id=enterprise_id,
        )
        before = self._core_service._load_role_bindings(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        roles = [
            self._core_service._load_role(session, item.role_id, enterprise_id=enterprise_id)
            for item in bindings
        ]
        if any(binding.role_code == "system_admin" for binding in before):
            self._core_service._ensure_not_last_system_admin(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                confirmed=True,
            )
        try:
            session.execute(
                text(
                    """
                    UPDATE role_bindings
                    SET status = 'revoked',
                        revoked_by = CAST(:actor_user_id AS uuid),
                        revoked_at = now()
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "actor_user_id": actor_user_id,
                },
            )
            for item, role in zip(bindings, roles, strict=True):
                self._core_service._insert_role_binding(
                    session,
                    enterprise_id=enterprise_id,
                    user_id=user_id,
                    role=role,
                    scope_type=item.scope_type,
                    scope_id=item.scope_id,
                    actor_user_id=actor_user_id,
                    actor_context=actor_context,
                )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_ROLE_BINDING_REPLACE_FAILED",
                "role bindings cannot be replaced",
                exc,
            ) from exc
        after = self._core_service._load_role_bindings(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        permission_version = self._core_service._bump_permission_version(
            session,
            enterprise_id,
        )
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="role_binding.replaced",
            resource_type="role_binding",
            resource_id=user_id,
            action="replace",
            result="success",
            risk_level="critical",
            summary={
                "user_id": user_id,
                "before": [binding.role_code for binding in before],
                "after": [binding.role_code for binding in after],
                "permission_version": permission_version,
                "high_risk_binding_present": any(
                    binding.role_code in HIGH_RISK_ROLE_CODES for binding in after
                ),
            },
        )
        return after

    def revoke_role_binding(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        binding_id: str,
        confirmed_remove_admin: bool,
        actor_context: AdminActorContext | None = None,
    ) -> None:
        self._core_service._ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        binding = self._core_service._load_role_binding(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            binding_id=binding_id,
        )
        if binding.role_code == "system_admin":
            self._core_service._ensure_not_last_system_admin(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                confirmed=confirmed_remove_admin,
            )
        try:
            session.execute(
                text(
                    """
                    UPDATE role_bindings
                    SET status = 'revoked',
                        revoked_by = CAST(:actor_user_id AS uuid),
                        revoked_at = now()
                    WHERE id = CAST(:binding_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {
                    "binding_id": binding_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "actor_user_id": actor_user_id,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_ROLE_BINDING_REVOKE_FAILED",
                "role binding cannot be revoked",
                exc,
            ) from exc
        permission_version = self._core_service._bump_permission_version(
            session,
            enterprise_id,
        )
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="role_binding.revoked",
            resource_type="role_binding",
            resource_id=binding_id,
            action="revoke",
            result="success",
            risk_level="high",
            summary={
                "binding_id": binding_id,
                "user_id": user_id,
                "role_code": binding.role_code,
                "permission_version": permission_version,
            },
        )
