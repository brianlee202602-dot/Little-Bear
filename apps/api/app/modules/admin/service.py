"""管理后台用户与角色服务。

P0 只覆盖本地账号、内置角色读取和用户角色绑定。涉及授权范围扩大的操作在事务内
递增 permission_version，并写入审计日志；高风险角色必须由路由层传入确认标记。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminDepartmentList,
    AdminRole,
    AdminRoleBinding,
    AdminUser,
    AdminUserList,
)
from app.modules.auth.password_service import PasswordPolicy, PasswordService
from app.modules.config.service import ConfigService
from app.shared.context import get_request_context
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

HIGH_RISK_ROLE_CODES = {"system_admin", "security_admin", "audit_admin"}
HIGH_RISK_SCOPE_EXACT = {
    "config:manage",
    "user:manage",
    "role:manage",
    "permission:manage",
}
HIGH_RISK_SCOPE_PREFIXES = ("config:", "user:", "role:", "permission:")


@dataclass(frozen=True)
class AdminActorContext:
    """管理后台操作者的最小权限上下文。

    JWT 只负责证明身份和粗粒度 scope；资源范围校验仍在服务层按当前数据库状态执行。
    """

    user_id: str
    scopes: tuple[str, ...]
    department_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoleBindingInput:
    role_id: str
    scope_type: str
    scope_id: str | None = None


class AdminService:
    """用户、角色和角色绑定的管理后台写模型。"""

    def __init__(self, *, password_service: PasswordService | None = None) -> None:
        self.password_service = password_service or PasswordService()

    def list_users(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminUserList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = ["enterprise_id = CAST(:enterprise_id AS uuid)", "deleted_at IS NULL"]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("(username ILIKE :keyword OR display_name ILIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if actor_context and not _actor_can_access_all_users(actor_context):
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM user_department_memberships actor_udm
                    JOIN user_department_memberships target_udm
                      ON target_udm.department_id = actor_udm.department_id
                    WHERE actor_udm.user_id = CAST(:actor_user_id AS uuid)
                      AND actor_udm.enterprise_id = users.enterprise_id
                      AND actor_udm.status = 'active'
                      AND target_udm.user_id = users.id
                      AND target_udm.enterprise_id = users.enterprise_id
                      AND target_udm.status = 'active'
                )
                """
            )
            params["actor_user_id"] = actor_context.user_id
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT id::text AS user_id
                    FROM users
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM users WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error("ADMIN_USERS_UNAVAILABLE", "users cannot be read", exc) from exc

        return AdminUserList(
            items=[
                self.get_user(session, row._mapping["user_id"], enterprise_id=enterprise_id)
                for row in rows
            ],
            total=int(total_row._mapping["total"]),
        )

    def list_departments(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
    ) -> AdminDepartmentList:
        """读取当前企业部门列表，用于用户归属部门选择器。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "enterprise_id = CAST(:enterprise_id AS uuid)",
            "deleted_at IS NULL",
            "status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("(code ILIKE :keyword OR name ILIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("status = :status")
            params["status"] = status
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT id::text AS department_id, code, name, status, is_default
                    FROM departments
                    WHERE {where_sql}
                    ORDER BY is_default DESC, code
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM departments WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DEPARTMENTS_UNAVAILABLE",
                "departments cannot be read",
                exc,
            ) from exc
        return AdminDepartmentList(
            items=[_department_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_department(
        self,
        session: Session,
        department_id: str,
        *,
        enterprise_id: str,
    ) -> AdminDepartment:
        """读取单个部门详情。"""

        try:
            row = session.execute(
                text(
                    """
                    SELECT id::text AS department_id, code, name, status, is_default, org_version
                    FROM departments
                    WHERE id = CAST(:department_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"department_id": department_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DEPARTMENT_UNAVAILABLE",
                "department cannot be read",
                exc,
            ) from exc
        if row is None:
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_NOT_FOUND",
                "department does not exist",
                status_code=404,
            )
        return _department_from_mapping(row._mapping)

    def get_user(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminUser:
        row = self._load_user_row(session, user_id, enterprise_id=enterprise_id)
        self._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        roles = self._load_user_roles(session, user_id, enterprise_id=enterprise_id)
        departments = self._load_user_departments(session, user_id, enterprise_id=enterprise_id)
        return AdminUser(
            id=row["user_id"],
            username=row["username"],
            name=row["display_name"],
            status=row["status"],
            enterprise_id=row["enterprise_id"],
            email=row["email"],
            phone=row["phone"],
            departments=departments,
            roles=roles,
            scopes=_merge_scopes(roles),
        )

    def create_user(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        username: str,
        name: str,
        initial_password: str,
        department_ids: list[str],
        role_ids: list[str],
        confirmed_high_risk: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminUser:
        username = username.strip()
        name = name.strip()
        if not username or not name:
            raise AdminServiceError("ADMIN_USER_INVALID", "username and name are required")

        auth_config = ConfigService().load_active_config(session).section("auth")
        self.password_service.validate_policy(
            initial_password,
            PasswordPolicy.from_auth_config(auth_config),
        )
        departments = self._resolve_departments(
            session,
            enterprise_id=enterprise_id,
            department_ids=department_ids,
        )
        roles = self._resolve_roles(session, enterprise_id=enterprise_id, role_ids=role_ids)
        if role_ids:
            self._ensure_actor_can_grant_roles(actor_context, roles)
        high_risk_roles = [role.code for role in roles if _is_high_risk_role(role)]
        if high_risk_roles and not confirmed_high_risk:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "granting high-risk role requires confirmation",
                status_code=428,
                details={"role_codes": high_risk_roles},
            )
        scoped_roles = [role.code for role in roles if role.scope_type != "enterprise"]
        if scoped_roles:
            raise AdminServiceError(
                "ADMIN_ROLE_SCOPE_REQUIRED",
                "scoped roles must be granted through role binding API",
                status_code=409,
                details={"role_codes": scoped_roles},
            )

        user_id = str(uuid.uuid4())
        password_hash = self.password_service.hash(initial_password)
        try:
            session.execute(
                text(
                    """
                    INSERT INTO users(
                        id, enterprise_id, username, display_name, status, created_by, updated_by
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid),
                        :username, :display_name, 'active',
                        CAST(:actor_user_id AS uuid), CAST(:actor_user_id AS uuid)
                    )
                    """
                ),
                {
                    "id": user_id,
                    "enterprise_id": enterprise_id,
                    "username": username,
                    "display_name": name,
                    "actor_user_id": actor_user_id,
                },
            )
            session.execute(
                text(
                    """
                    INSERT INTO user_credentials(
                        user_id, password_hash, password_alg, force_change_password
                    )
                    VALUES (CAST(:user_id AS uuid), :password_hash, 'argon2id', true)
                    """
                ),
                {"user_id": user_id, "password_hash": password_hash},
            )
            for index, department in enumerate(departments):
                self._insert_department_membership(
                    session,
                    enterprise_id=enterprise_id,
                    user_id=user_id,
                    department_id=department.id,
                    actor_user_id=actor_user_id,
                    is_primary=index == 0,
                )
            for role in roles:
                self._insert_role_binding(
                    session,
                    enterprise_id=enterprise_id,
                    user_id=user_id,
                    role=role,
                    scope_type="enterprise",
                    scope_id=None,
                    actor_user_id=actor_user_id,
                )
        except IntegrityError as exc:
            raise AdminServiceError(
                "ADMIN_USER_CONFLICT",
                "user already exists",
                status_code=409,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_CREATE_FAILED", "user cannot be created", exc
            ) from exc

        permission_version = self._bump_permission_version(session, enterprise_id)
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="user.created",
            resource_type="user",
            resource_id=user_id,
            action="create",
            result="success",
            risk_level="high",
            summary={
                "user_id": user_id,
                "username_masked": _mask_username(username),
                "department_ids": [department.id for department in departments],
                "role_codes": [role.code for role in roles],
                "force_change_password": True,
                "permission_version": permission_version,
            },
        )
        return self.get_user(
            session,
            user_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )

    def create_department(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        code: str,
        name: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDepartment:
        """创建当前企业下的普通部门，并刷新权限版本。"""

        self._ensure_actor_can_manage_departments(actor_context)
        code = code.strip()
        name = name.strip()
        if not code or not name:
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_INVALID",
                "department code and name are required",
                status_code=400,
            )

        department_id = str(uuid.uuid4())
        try:
            department_org_version = self._bump_org_version(session, enterprise_id)
            session.execute(
                text(
                    """
                    INSERT INTO departments(
                        id, enterprise_id, code, name, status, is_default,
                        org_version, created_by, updated_by
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :code, :name,
                        'active', false, :org_version,
                        CAST(:actor_user_id AS uuid), CAST(:actor_user_id AS uuid)
                    )
                    """
                ),
                {
                    "id": department_id,
                    "enterprise_id": enterprise_id,
                    "code": code,
                    "name": name,
                    "org_version": department_org_version,
                    "actor_user_id": actor_user_id,
                },
            )
            permission_version = self._bump_permission_version(session, enterprise_id)
            self._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="department.created",
                resource_type="department",
                resource_id=department_id,
                action="create",
                result="success",
                risk_level="medium",
                summary={
                    "department_id": department_id,
                    "department_code": code,
                    "org_version": department_org_version,
                    "permission_version": permission_version,
                },
            )
        except IntegrityError as exc:
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_CONFLICT",
                "department already exists",
                status_code=409,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DEPARTMENT_CREATE_FAILED",
                "department cannot be created",
                exc,
            ) from exc
        return AdminDepartment(
            id=department_id,
            code=code,
            name=name,
            status="active",
            is_default=False,
            org_version=department_org_version,
        )

    def patch_department(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        department_id: str,
        name: str | None = None,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDepartment:
        """更新部门名称或状态。"""

        self._ensure_actor_can_manage_departments(actor_context)
        current = self.get_department(session, department_id, enterprise_id=enterprise_id)
        updates: list[str] = []
        params: dict[str, Any] = {
            "department_id": department_id,
            "enterprise_id": enterprise_id,
            "actor_user_id": actor_user_id,
        }
        before = {
            "name": current.name,
            "status": current.status,
            "is_default": current.is_default,
            "org_version": current.org_version,
        }
        if name is not None:
            name = name.strip()
            if not name:
                raise AdminServiceError(
                    "ADMIN_DEPARTMENT_INVALID",
                    "department name is required",
                    status_code=400,
                )
            updates.append("name = :name")
            params["name"] = name
        if status is not None:
            if status not in {"active", "disabled"}:
                raise AdminServiceError(
                    "ADMIN_DEPARTMENT_STATUS_INVALID",
                    "department status is invalid",
                    status_code=400,
                )
            if current.is_default and status == "disabled":
                raise AdminServiceError(
                    "ADMIN_DEFAULT_DEPARTMENT_PROTECTED",
                    "default department cannot be disabled",
                    status_code=409,
                )
            updates.append("status = :status")
            params["status"] = status
        if not updates:
            return current

        try:
            org_version = self._bump_org_version(session, enterprise_id)
            updates.append("org_version = :org_version")
            params["org_version"] = org_version
            session.execute(
                text(
                    f"""
                    UPDATE departments
                    SET {", ".join(updates)},
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:department_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                params,
            )
            if status == "disabled":
                session.execute(
                    text(
                        """
                        UPDATE user_department_memberships
                        SET status = 'deleted',
                            deleted_at = now()
                        WHERE department_id = CAST(:department_id AS uuid)
                          AND enterprise_id = CAST(:enterprise_id AS uuid)
                          AND status = 'active'
                        """
                    ),
                    {"department_id": department_id, "enterprise_id": enterprise_id},
                )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DEPARTMENT_UPDATE_FAILED",
                "department cannot be updated",
                exc,
            ) from exc

        permission_version = self._bump_permission_version(session, enterprise_id)
        after = self.get_department(session, department_id, enterprise_id=enterprise_id)
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="department.updated",
            resource_type="department",
            resource_id=department_id,
            action="update",
            result="success",
            risk_level="medium",
            summary={
                "department_id": department_id,
                "before": before,
                "after": {
                    "name": after.name,
                    "status": after.status,
                    "is_default": after.is_default,
                    "org_version": after.org_version,
                },
                "changed_fields": [field.split(" = ", 1)[0] for field in updates if field != "org_version = :org_version"],
                "org_version": after.org_version,
                "permission_version": permission_version,
            },
        )
        return after

    def delete_department(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        department_id: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> None:
        """软删除部门，并同步清理成员关系。"""

        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "deleting department requires confirmation",
                status_code=428,
            )
        self._ensure_actor_can_manage_departments(actor_context)
        current = self.get_department(session, department_id, enterprise_id=enterprise_id)
        if current.is_default:
            raise AdminServiceError(
                "ADMIN_DEFAULT_DEPARTMENT_PROTECTED",
                "default department cannot be deleted",
                status_code=409,
            )
        active_members = session.execute(
            text(
                """
                SELECT count(*) AS active_members
                FROM user_department_memberships
                WHERE department_id = CAST(:department_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                  AND status = 'active'
                """
            ),
            {"department_id": department_id, "enterprise_id": enterprise_id},
        ).one()
        if int(active_members._mapping["active_members"]) > 0:
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_HAS_ACTIVE_MEMBERS",
                "department still has active members",
                status_code=409,
                details={"department_id": department_id},
            )
        try:
            org_version = self._bump_org_version(session, enterprise_id)
            session.execute(
                text(
                    """
                    UPDATE departments
                    SET status = 'deleted', deleted_at = now(), updated_at = now(),
                        updated_by = CAST(:actor_user_id AS uuid), org_version = :org_version
                    WHERE id = CAST(:department_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                {
                    "department_id": department_id,
                    "enterprise_id": enterprise_id,
                    "actor_user_id": actor_user_id,
                    "org_version": org_version,
                },
            )
            session.execute(
                text(
                    """
                    UPDATE user_department_memberships
                    SET status = 'deleted', deleted_at = now()
                    WHERE department_id = CAST(:department_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {"department_id": department_id, "enterprise_id": enterprise_id},
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DEPARTMENT_DELETE_FAILED",
                "department cannot be deleted",
                exc,
            ) from exc

        permission_version = self._bump_permission_version(session, enterprise_id)
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="department.deleted",
            resource_type="department",
            resource_id=department_id,
            action="delete",
            result="success",
            risk_level="high",
            summary={
                "department_id": department_id,
                "department_code": current.code,
                "org_version": current.org_version + 1,
                "permission_version": permission_version,
            },
        )

    def patch_user(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        name: str | None = None,
        status: str | None = None,
        confirmed_disable_admin: bool = False,
        actor_context: AdminActorContext | None = None,
    ) -> AdminUser:
        self._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        current = self.get_user(session, user_id, enterprise_id=enterprise_id)
        updates: list[str] = []
        params: dict[str, Any] = {
            "user_id": user_id,
            "enterprise_id": enterprise_id,
            "actor_user_id": actor_user_id,
        }
        if name is not None:
            updates.append("display_name = :display_name")
            params["display_name"] = name.strip()
        if status is not None:
            if status not in {"active", "disabled", "locked"}:
                raise AdminServiceError("ADMIN_USER_STATUS_INVALID", "user status is invalid")
            if status == "disabled" and _has_system_admin(current):
                self._ensure_not_last_system_admin(
                    session,
                    enterprise_id=enterprise_id,
                    user_id=user_id,
                    confirmed=confirmed_disable_admin,
                )
            updates.append("status = :status")
            params["status"] = status
        if not updates:
            return current

        try:
            session.execute(
                text(
                    f"""
                    UPDATE users
                    SET {", ".join(updates)}, updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                params,
            )
            if status == "disabled":
                revoked = self._revoke_user_tokens(session, user_id, reason="user_disabled")
                permission_version = self._bump_permission_version(session, enterprise_id)
                self._insert_audit_log(
                    session,
                    enterprise_id=enterprise_id,
                    actor_id=actor_user_id,
                    event_name="user.disabled",
                    resource_type="user",
                    resource_id=user_id,
                    action="disable",
                    result="success",
                    risk_level="high",
                    summary={
                        "user_id": user_id,
                        "reason": "admin_disabled",
                        "revoked_sessions": revoked,
                        "permission_version": permission_version,
                    },
                )
            elif status == "locked":
                permission_version = self._bump_permission_version(session, enterprise_id)
                self._insert_audit_log(
                    session,
                    enterprise_id=enterprise_id,
                    actor_id=actor_user_id,
                    event_name="user.locked",
                    resource_type="user",
                    resource_id=user_id,
                    action="lock",
                    result="success",
                    risk_level="high",
                    summary={
                        "user_id": user_id,
                        "reason": "admin_locked",
                        "permission_version": permission_version,
                    },
                )
            elif status == "active":
                self._bump_permission_version(session, enterprise_id)
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_UPDATE_FAILED", "user cannot be updated", exc
            ) from exc
        return self.get_user(
            session,
            user_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )

    def delete_user(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> None:
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "deleting user requires confirmation",
                status_code=428,
            )
        self._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        current = self.get_user(session, user_id, enterprise_id=enterprise_id)
        if _has_system_admin(current):
            self._ensure_not_last_system_admin(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                confirmed=True,
            )
        try:
            session.execute(
                text(
                    """
                    UPDATE users
                    SET status = 'deleted', deleted_at = now(), updated_at = now(),
                        updated_by = CAST(:actor_user_id AS uuid)
                    WHERE id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                {
                    "user_id": user_id,
                    "enterprise_id": enterprise_id,
                    "actor_user_id": actor_user_id,
                },
            )
            session.execute(
                text(
                    """
                    UPDATE role_bindings
                    SET status = 'revoked',
                        revoked_by = CAST(:actor_user_id AS uuid),
                        revoked_at = now()
                    WHERE user_id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {
                    "user_id": user_id,
                    "enterprise_id": enterprise_id,
                    "actor_user_id": actor_user_id,
                },
            )
            session.execute(
                text(
                    """
                    UPDATE user_department_memberships
                    SET status = 'deleted', deleted_at = now()
                    WHERE user_id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            )
            revoked = self._revoke_user_tokens(session, user_id, reason="user_deleted")
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_DELETE_FAILED", "user cannot be deleted", exc
            ) from exc

        permission_version = self._bump_permission_version(session, enterprise_id)
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="user.deleted",
            resource_type="user",
            resource_id=user_id,
            action="delete",
            result="success",
            risk_level="critical",
            summary={
                "user_id": user_id,
                "reason": "admin_deleted",
                "revoked_sessions": revoked,
                "permission_version": permission_version,
            },
        )

    def reset_user_password(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        new_password: str,
        force_change_password: bool,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> None:
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "resetting password requires confirmation",
                status_code=428,
            )
        self._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._load_user_row(session, user_id, enterprise_id=enterprise_id)
        auth_config = ConfigService().load_active_config(session).section("auth")
        self.password_service.validate_policy(
            new_password,
            PasswordPolicy.from_auth_config(auth_config),
        )
        password_hash = self.password_service.hash(new_password)
        try:
            session.execute(
                text(
                    """
                    UPDATE user_credentials
                    SET password_hash = :password_hash,
                        password_alg = 'argon2id',
                        password_updated_at = now(),
                        force_change_password = :force_change_password,
                        failed_login_count = 0,
                        locked_until = null,
                        updated_at = now()
                    WHERE user_id = CAST(:user_id AS uuid)
                    """
                ),
                {
                    "user_id": user_id,
                    "password_hash": password_hash,
                    "force_change_password": force_change_password,
                },
            )
            revoked = self._revoke_user_tokens(session, user_id, reason="password_reset")
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_PASSWORD_RESET_FAILED",
                "password cannot be reset",
                exc,
            ) from exc
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="user.password_reset",
            resource_type="user",
            resource_id=user_id,
            action="reset_password",
            result="success",
            risk_level="high",
            summary={
                "user_id": user_id,
                "force_change_password": force_change_password,
                "credential_version_bumped": True,
                "revoked_sessions": revoked,
            },
        )

    def unlock_user(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> None:
        self._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._load_user_row(session, user_id, enterprise_id=enterprise_id)
        try:
            session.execute(
                text(
                    """
                    UPDATE user_credentials
                    SET failed_login_count = 0, locked_until = null, updated_at = now()
                    WHERE user_id = CAST(:user_id AS uuid)
                    """
                ),
                {"user_id": user_id},
            )
            session.execute(
                text(
                    """
                    UPDATE users
                    SET status = CASE WHEN status = 'locked' THEN 'active' ELSE status END,
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                    """
                ),
                {
                    "user_id": user_id,
                    "enterprise_id": enterprise_id,
                    "actor_user_id": actor_user_id,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_UNLOCK_FAILED", "user cannot be unlocked", exc
            ) from exc
        self._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="user.unlocked",
            resource_type="user",
            resource_id=user_id,
            action="unlock",
            result="success",
            risk_level="high",
            summary={"user_id": user_id, "reason": "admin_unlock"},
        )

    def list_roles(self, session: Session, *, enterprise_id: str) -> list[AdminRole]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT id::text AS role_id, code, name, scope_type, scopes, is_builtin, status
                    FROM roles
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND status != 'archived'
                    ORDER BY is_builtin DESC, code
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error("ADMIN_ROLES_UNAVAILABLE", "roles cannot be read", exc) from exc
        return [_role_from_mapping(row._mapping) for row in rows]

    def get_role(self, session: Session, role_id: str, *, enterprise_id: str) -> AdminRole:
        role = self._load_role(session, role_id, enterprise_id=enterprise_id)
        if role.status == "archived":
            raise AdminServiceError("ADMIN_ROLE_NOT_FOUND", "role does not exist", status_code=404)
        return role

    def list_role_bindings(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> list[AdminRoleBinding]:
        self._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._load_user_row(session, user_id, enterprise_id=enterprise_id)
        return self._load_role_bindings(session, enterprise_id=enterprise_id, user_id=user_id)

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
        self._ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._load_user_row(session, user_id, enterprise_id=enterprise_id)
        inserted: list[AdminRoleBinding] = []
        roles = [
            self._load_role(session, item.role_id, enterprise_id=enterprise_id) for item in bindings
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
                    self._insert_role_binding(
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

        permission_version = self._bump_permission_version(session, enterprise_id)
        for binding in inserted:
            self._insert_audit_log(
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
        return self._load_role_bindings(session, enterprise_id=enterprise_id, user_id=user_id)

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
        self._ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._load_user_row(session, user_id, enterprise_id=enterprise_id)
        before = self._load_role_bindings(session, enterprise_id=enterprise_id, user_id=user_id)
        roles = [
            self._load_role(session, item.role_id, enterprise_id=enterprise_id) for item in bindings
        ]
        if any(binding.role_code == "system_admin" for binding in before):
            self._ensure_not_last_system_admin(
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
                self._insert_role_binding(
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
        after = self._load_role_bindings(session, enterprise_id=enterprise_id, user_id=user_id)
        permission_version = self._bump_permission_version(session, enterprise_id)
        self._insert_audit_log(
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
        self._ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        binding = self._load_role_binding(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            binding_id=binding_id,
        )
        if binding.role_code == "system_admin":
            self._ensure_not_last_system_admin(
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
        permission_version = self._bump_permission_version(session, enterprise_id)
        self._insert_audit_log(
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

    def _load_user_row(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
    ) -> dict[str, Any]:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS user_id,
                        enterprise_id::text AS enterprise_id,
                        username,
                        display_name,
                        email,
                        phone,
                        status
                    FROM users
                    WHERE id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error("ADMIN_USER_UNAVAILABLE", "user cannot be read", exc) from exc
        if row is None:
            raise AdminServiceError("ADMIN_USER_NOT_FOUND", "user does not exist", status_code=404)
        return dict(row._mapping)

    def _load_user_roles(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
    ) -> tuple[AdminRole, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        r.id::text AS role_id,
                        r.code,
                        r.name,
                        r.scope_type,
                        r.scopes,
                        r.is_builtin,
                        r.status
                    FROM role_bindings rb
                    JOIN roles r ON r.id = rb.role_id
                    WHERE rb.user_id = CAST(:user_id AS uuid)
                      AND rb.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND rb.status = 'active'
                      AND r.status = 'active'
                    ORDER BY r.code
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_ROLES_UNAVAILABLE",
                "user roles cannot be read",
                exc,
            ) from exc
        return tuple(_role_from_mapping(row._mapping) for row in rows)

    def _load_user_departments(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
    ) -> tuple[AdminDepartment, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS department_id,
                        d.code,
                        d.name,
                        d.status,
                        udm.is_primary,
                        d.is_default
                    FROM user_department_memberships udm
                    JOIN departments d ON d.id = udm.department_id
                    WHERE udm.user_id = CAST(:user_id AS uuid)
                      AND udm.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND udm.status = 'active'
                    ORDER BY udm.is_primary DESC, d.code
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_DEPARTMENTS_UNAVAILABLE",
                "user departments cannot be read",
                exc,
            ) from exc
        return tuple(
            AdminDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                status=row._mapping["status"],
                is_primary=bool(row._mapping["is_primary"]),
                is_default=bool(row._mapping["is_default"]),
            )
            for row in rows
        )

    def _resolve_departments(
        self,
        session: Session,
        *,
        enterprise_id: str,
        department_ids: list[str],
    ) -> list[AdminDepartment]:
        if not department_ids:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS department_id,
                        code,
                        name,
                        status,
                        true AS is_primary,
                        is_default
                    FROM departments
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND is_default = true
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).one_or_none()
            if row is None:
                raise AdminServiceError(
                    "ADMIN_DEFAULT_DEPARTMENT_MISSING",
                    "default department is missing",
                    status_code=409,
                )
            return [
                AdminDepartment(
                    id=row._mapping["department_id"],
                    code=row._mapping["code"],
                    name=row._mapping["name"],
                    status=row._mapping["status"],
                    is_primary=True,
                    is_default=bool(row._mapping["is_default"]),
                )
            ]

        rows = session.execute(
            text(
                """
                SELECT id::text AS department_id, code, name, status, is_default
                FROM departments
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND id = ANY(CAST(:department_ids AS uuid[]))
                  AND status = 'active'
                ORDER BY code
                """
            ),
            {"enterprise_id": enterprise_id, "department_ids": department_ids},
        ).all()
        if len(rows) != len(set(department_ids)):
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_NOT_FOUND",
                "one or more departments do not exist",
                status_code=404,
            )
        return [
            AdminDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                status=row._mapping["status"],
                is_default=bool(row._mapping["is_default"]),
            )
            for row in rows
        ]

    def _resolve_roles(
        self,
        session: Session,
        *,
        enterprise_id: str,
        role_ids: list[str],
    ) -> list[AdminRole]:
        if not role_ids:
            row = session.execute(
                text(
                    """
                    SELECT id::text AS role_id
                    FROM roles
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND code = 'employee'
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).one_or_none()
            if row is None:
                raise AdminServiceError(
                    "ADMIN_DEFAULT_ROLE_MISSING",
                    "default employee role is missing",
                    status_code=409,
                )
            role_ids = [row._mapping["role_id"]]
        roles = [
            self._load_role(session, role_id, enterprise_id=enterprise_id) for role_id in role_ids
        ]
        inactive_roles = [role.code for role in roles if role.status != "active"]
        if inactive_roles:
            raise AdminServiceError(
                "ADMIN_ROLE_INACTIVE",
                "inactive roles cannot be granted",
                status_code=409,
                details={"role_codes": inactive_roles},
            )
        return roles

    def _load_role(self, session: Session, role_id: str, *, enterprise_id: str) -> AdminRole:
        try:
            row = session.execute(
                text(
                    """
                    SELECT id::text AS role_id, code, name, scope_type, scopes, is_builtin, status
                    FROM roles
                    WHERE id = CAST(:role_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"role_id": role_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error("ADMIN_ROLE_UNAVAILABLE", "role cannot be read", exc) from exc
        if row is None:
            raise AdminServiceError("ADMIN_ROLE_NOT_FOUND", "role does not exist", status_code=404)
        return _role_from_mapping(row._mapping)

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

    def _ensure_actor_can_access_user(
        self,
        session: Session,
        actor_context: AdminActorContext | None,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> None:
        if actor_context is None or _actor_can_access_all_users(actor_context):
            return
        row = session.execute(
            text(
                """
                SELECT 1
                FROM user_department_memberships actor_udm
                JOIN user_department_memberships target_udm
                  ON target_udm.department_id = actor_udm.department_id
                WHERE actor_udm.user_id = CAST(:actor_user_id AS uuid)
                  AND actor_udm.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND actor_udm.status = 'active'
                  AND target_udm.user_id = CAST(:target_user_id AS uuid)
                  AND target_udm.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND target_udm.status = 'active'
                LIMIT 1
                """
            ),
            {
                "actor_user_id": actor_context.user_id,
                "target_user_id": user_id,
                "enterprise_id": enterprise_id,
            },
        ).one_or_none()
        if row is None:
            raise AdminServiceError(
                "ADMIN_RESOURCE_FORBIDDEN",
                "target user is outside actor management scope",
                status_code=403,
            )

    def _ensure_actor_can_manage_user(
        self,
        session: Session,
        actor_context: AdminActorContext | None,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> None:
        if actor_context is None:
            return
        if not _has_scope(actor_context.scopes, "user:manage"):
            raise AdminServiceError(
                "ADMIN_SCOPE_REQUIRED",
                "user management requires user:manage",
                status_code=403,
                details={"required_scope": "user:manage"},
            )
        self._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def _ensure_actor_can_manage_departments(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        if actor_context is None:
            return
        if not _has_scope(actor_context.scopes, "org:manage"):
            raise AdminServiceError(
                "ADMIN_SCOPE_REQUIRED",
                "department management requires org:manage",
                status_code=403,
                details={"required_scope": "org:manage"},
            )

    def _ensure_actor_can_manage_role_target_user(
        self,
        session: Session,
        actor_context: AdminActorContext | None,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> None:
        if actor_context is None:
            return
        missing = [
            scope
            for scope in ("role:manage", "user:manage")
            if not _has_scope(actor_context.scopes, scope)
        ]
        if missing:
            raise AdminServiceError(
                "ADMIN_SCOPE_REQUIRED",
                "role binding management requires role:manage and user:manage",
                status_code=403,
                details={"required_scopes": missing},
            )
        self._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def _ensure_actor_can_grant_roles(
        self,
        actor_context: AdminActorContext | None,
        roles: list[AdminRole],
    ) -> None:
        if actor_context is None:
            return
        if not roles:
            return
        if not _has_scope(actor_context.scopes, "role:manage"):
            raise AdminServiceError(
                "ADMIN_SCOPE_REQUIRED",
                "explicit role grants require role:manage",
                status_code=403,
                details={"required_scope": "role:manage"},
            )

    def _ensure_actor_can_manage_role_scope(
        self,
        actor_context: AdminActorContext | None,
        *,
        role: AdminRole,
        scope_type: str,
        scope_id: str | None,
    ) -> None:
        if actor_context is None or _actor_can_manage_all_role_scopes(actor_context):
            return
        if scope_type == "department" and scope_id in actor_context.department_ids:
            return
        raise AdminServiceError(
            "ADMIN_RESOURCE_FORBIDDEN",
            "role binding scope is outside actor management scope",
            status_code=403,
            details={"role_code": role.code, "scope_type": scope_type, "scope_id": scope_id},
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

    def _load_role_bindings(
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

    def _load_role_binding(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        binding_id: str,
    ) -> AdminRoleBinding:
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
                WHERE rb.id = CAST(:binding_id AS uuid)
                  AND rb.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND rb.user_id = CAST(:user_id AS uuid)
                  AND rb.status = 'active'
                LIMIT 1
                """
            ),
            {"binding_id": binding_id, "enterprise_id": enterprise_id, "user_id": user_id},
        ).one_or_none()
        if rows is None:
            raise AdminServiceError(
                "ADMIN_ROLE_BINDING_NOT_FOUND",
                "role binding does not exist",
                status_code=404,
            )
        return _role_binding_from_mapping(rows._mapping)

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
        has_admin = _user_has_role(
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
        resource_id: str,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, enterprise_id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level, summary_json, error_code
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id, :trace_id,
                    :event_name, 'user', :actor_id, :resource_type, :resource_id,
                    :action, :result, :risk_level, CAST(:summary_json AS jsonb), :error_code
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "enterprise_id": enterprise_id,
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "result": result,
                "risk_level": risk_level,
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
                "error_code": error_code,
            },
        )


def _role_from_mapping(row: Any) -> AdminRole:
    return AdminRole(
        id=row["role_id"],
        code=row["code"],
        name=row["name"],
        scope_type=row["scope_type"],
        is_builtin=bool(row["is_builtin"]),
        status=row["status"],
        scopes=tuple(str(item) for item in row["scopes"] or []),
    )


def _department_from_mapping(row: Any) -> AdminDepartment:
    return AdminDepartment(
        id=row["department_id"],
        code=row["code"],
        name=row["name"],
        status=row["status"],
        is_default=bool(row["is_default"]),
    )


def _role_binding_from_mapping(row: Any) -> AdminRoleBinding:
    return AdminRoleBinding(
        id=row["binding_id"],
        role_id=row["role_id"],
        subject_type="user",
        subject_id=row["user_id"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        role_code=row["role_code"],
        role_name=row["role_name"],
    )


def _merge_scopes(roles: tuple[AdminRole, ...]) -> tuple[str, ...]:
    scopes = {"auth:session", "auth:password:update:self"}
    for role in roles:
        scopes.update(role.scopes)
    return tuple(sorted(scopes))


def _is_high_risk_role(role: AdminRole) -> bool:
    if role.code in HIGH_RISK_ROLE_CODES or "*" in role.scopes:
        return True
    return any(_is_high_risk_scope(scope) for scope in role.scopes)


def _is_high_risk_scope(scope: str) -> bool:
    if scope in HIGH_RISK_SCOPE_EXACT:
        return True
    if scope.endswith(":*") and scope.removesuffix(":*") in {
        "config",
        "user",
        "role",
        "permission",
    }:
        return True
    return any(
        scope.startswith(prefix) and scope.endswith(":manage")
        for prefix in HIGH_RISK_SCOPE_PREFIXES
    )


def _has_system_admin(user: AdminUser) -> bool:
    return any(role.code == "system_admin" for role in user.roles)


def _user_has_role(
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


def _has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes


def _actor_can_access_all_users(actor_context: AdminActorContext) -> bool:
    return (
        "*" in actor_context.scopes
        or "user:*" in actor_context.scopes
        or "user:manage" in actor_context.scopes
    )


def _actor_can_manage_all_role_scopes(actor_context: AdminActorContext) -> bool:
    return (
        "*" in actor_context.scopes
        or "role:*" in actor_context.scopes
        or "role:manage" in actor_context.scopes
    )


def _mask_username(username: str) -> str:
    if len(username) <= 2:
        return "***"
    return f"{username[0]}***{username[-1]}"


def _database_error(error_code: str, message: str, exc: SQLAlchemyError) -> AdminServiceError:
    return AdminServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
