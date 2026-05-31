"""User department administration service."""

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


class AdminUserDepartmentService:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_user_departments(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        page: int,
        page_size: int,
        actor_context: AdminActorContext | None = None,
    ) -> AdminUserDepartmentList:
        """读取用户当前有效部门归属。"""

        self._core_service._load_user_row(session, user_id, enterprise_id=enterprise_id)
        self._core_service._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
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
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "user_id": user_id,
                    "enterprise_id": enterprise_id,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM user_department_memberships udm
                    WHERE udm.user_id = CAST(:user_id AS uuid)
                      AND udm.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND udm.status = 'active'
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_DEPARTMENTS_UNAVAILABLE",
                "user departments cannot be read",
                exc,
            ) from exc
        return AdminUserDepartmentList(
            items=[_department_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def replace_user_departments(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        user_id: str,
        department_ids: list[str],
        confirmed_remove_primary: bool,
        actor_context: AdminActorContext | None = None,
    ) -> list[AdminDepartment]:
        """整体替换用户部门归属；第一个部门固定为主部门。"""

        self._core_service._ensure_actor_can_manage_departments(actor_context)
        normalized_department_ids = _normalize_id_list(department_ids)
        if not normalized_department_ids or len(normalized_department_ids) != len(department_ids):
            raise AdminServiceError(
                "ADMIN_USER_DEPARTMENTS_INVALID",
                "at least one unique department is required",
                status_code=400,
            )
        self._core_service._load_user_row(session, user_id, enterprise_id=enterprise_id)
        self._core_service._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

        departments = self._core_service._resolve_departments(
            session,
            enterprise_id=enterprise_id,
            department_ids=normalized_department_ids,
        )
        before = list(
            self._core_service._load_user_departments(
                session,
                user_id,
                enterprise_id=enterprise_id,
            )
        )
        before_primary_id = next(
            (department.id for department in before if department.is_primary),
            None,
        )
        next_primary_id = departments[0].id
        primary_changed_without_confirmation = (
            before_primary_id
            and before_primary_id != next_primary_id
            and not confirmed_remove_primary
        )
        if primary_changed_without_confirmation:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "replacing primary department requires confirmation",
                status_code=428,
                details={
                    "previous_primary_department_id": before_primary_id,
                    "next_primary_department_id": next_primary_id,
                },
            )

        before_ids = {department.id for department in before}
        next_ids = {department.id for department in departments}
        if before_primary_id == next_primary_id and before_ids == next_ids:
            return before

        try:
            org_version = self._core_service._bump_org_version(session, enterprise_id)
            session.execute(
                text(
                    """
                    UPDATE user_department_memberships
                    SET status = 'deleted',
                        deleted_at = now()
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {"enterprise_id": enterprise_id, "user_id": user_id},
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
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_DEPARTMENTS_REPLACE_FAILED",
                "user departments cannot be replaced",
                exc,
            ) from exc

        permission_version = self._core_service._bump_permission_version(session, enterprise_id)
        after = list(
            self._core_service._load_user_departments(
                session,
                user_id,
                enterprise_id=enterprise_id,
            )
        )
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="membership.replaced",
            resource_type="user",
            resource_id=user_id,
            action="replace_membership",
            result="success",
            risk_level="high",
            summary={
                "user_id": user_id,
                "before": [
                    {
                        "department_id": department.id,
                        "department_code": department.code,
                        "is_primary": department.is_primary,
                    }
                    for department in before
                ],
                "after": [
                    {
                        "department_id": department.id,
                        "department_code": department.code,
                        "is_primary": department.is_primary,
                    }
                    for department in after
                ],
                "org_version": org_version,
                "permission_version": permission_version,
            },
        )
        return after

