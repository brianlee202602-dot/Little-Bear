"""User security administration service."""

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


class AdminUserSecurityService:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

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
        self._core_service._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._core_service._load_user_row(session, user_id, enterprise_id=enterprise_id)
        auth_config = ConfigService().load_active_config(session).section("auth")
        self._core_service.password_service.validate_policy(
            new_password,
            PasswordPolicy.from_auth_config(auth_config),
        )
        password_hash = self._core_service.password_service.hash(new_password)
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
            revoked = self._core_service._revoke_user_tokens(
                session,
                user_id,
                reason="password_reset",
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_PASSWORD_RESET_FAILED",
                "password cannot be reset",
                exc,
            ) from exc
        self._core_service._insert_audit_log(
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
        self._core_service._ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        self._core_service._load_user_row(session, user_id, enterprise_id=enterprise_id)
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
        self._core_service._insert_audit_log(
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

