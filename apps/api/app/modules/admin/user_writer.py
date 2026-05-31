"""User administration write service."""

# ruff: noqa: F401

from __future__ import annotations

import uuid
from typing import Any

from app.modules.admin.access_control import AdminActorContext, actor_can_access_all_users
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.mappers import (
    _department_from_mapping,
    _user_list_item_from_mapping,
)
from app.modules.admin.role_policy import _has_system_admin, _is_high_risk_role, _merge_scopes
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminUser,
    AdminUserDepartmentList,
    AdminUserList,
)
from app.modules.admin.utils import _database_error, _mask_username, _normalize_id_list
from app.modules.auth.password_service import PasswordPolicy
from app.modules.config.service import ConfigService
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


class AdminUserWriter:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

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
        self._core_service.password_service.validate_policy(
            initial_password,
            PasswordPolicy.from_auth_config(auth_config),
        )
        departments = self._core_service._resolve_departments(
            session,
            enterprise_id=enterprise_id,
            department_ids=department_ids,
        )
        self._core_service._ensure_actor_can_create_user_departments(actor_context, departments)
        roles = self._core_service._resolve_roles(
            session,
            enterprise_id=enterprise_id,
            role_ids=role_ids,
        )
        if role_ids:
            self._core_service._ensure_actor_can_grant_roles(actor_context, roles)
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
        password_hash = self._core_service.password_service.hash(initial_password)
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
                self._core_service._insert_department_membership(
                    session,
                    enterprise_id=enterprise_id,
                    user_id=user_id,
                    department_id=department.id,
                    actor_user_id=actor_user_id,
                    is_primary=index == 0,
                )
            for role in roles:
                self._core_service._insert_role_binding(
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

        permission_version = self._core_service._bump_permission_version(session, enterprise_id)
        self._core_service._insert_audit_log(
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
        return self._core_service.get_user(
            session,
            user_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
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
        self._core_service._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        current = self._core_service.get_user(session, user_id, enterprise_id=enterprise_id)
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
                self._core_service._ensure_not_last_system_admin(
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
                revoked = self._core_service._revoke_user_tokens(
                    session,
                    user_id,
                    reason="user_disabled",
                )
                permission_version = self._core_service._bump_permission_version(
                    session,
                    enterprise_id,
                )
                self._core_service._insert_audit_log(
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
                permission_version = self._core_service._bump_permission_version(
                    session,
                    enterprise_id,
                )
                self._core_service._insert_audit_log(
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
                self._core_service._bump_permission_version(session, enterprise_id)
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_UPDATE_FAILED", "user cannot be updated", exc
            ) from exc
        return self._core_service.get_user(
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
        self._core_service._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        current = self._core_service.get_user(session, user_id, enterprise_id=enterprise_id)
        if _has_system_admin(current):
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
            revoked = self._core_service._revoke_user_tokens(
                session,
                user_id,
                reason="user_deleted",
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_DELETE_FAILED", "user cannot be deleted", exc
            ) from exc

        permission_version = self._core_service._bump_permission_version(session, enterprise_id)
        self._core_service._insert_audit_log(
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

