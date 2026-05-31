"""User administration read service."""

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


class AdminUsersReader:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

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
        conditions = [
            "users.enterprise_id = CAST(:enterprise_id AS uuid)",
            "users.deleted_at IS NULL",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append(
                "(users.username ILIKE :keyword OR users.display_name ILIKE :keyword)"
            )
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("users.status = :status")
            params["status"] = status
        if actor_context and not actor_can_access_all_users(actor_context):
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
                    SELECT
                        users.id::text AS user_id,
                        users.username,
                        users.display_name,
                        users.status,
                        COALESCE(
                            array_agg(DISTINCT departments.name)
                                FILTER (WHERE departments.id IS NOT NULL),
                            ARRAY[]::text[]
                        ) AS department_names,
                        COALESCE(
                            array_agg(DISTINCT roles.name)
                                FILTER (WHERE roles.id IS NOT NULL),
                            ARRAY[]::text[]
                        ) AS role_names
                    FROM users
                    LEFT JOIN user_department_memberships udm
                      ON udm.user_id = users.id
                     AND udm.enterprise_id = users.enterprise_id
                     AND udm.status = 'active'
                    LEFT JOIN departments
                      ON departments.id = udm.department_id
                     AND departments.enterprise_id = users.enterprise_id
                     AND departments.deleted_at IS NULL
                     AND departments.status != 'deleted'
                    LEFT JOIN role_bindings rb
                      ON rb.user_id = users.id
                     AND rb.enterprise_id = users.enterprise_id
                     AND rb.status = 'active'
                    LEFT JOIN roles
                      ON roles.id = rb.role_id
                     AND roles.enterprise_id = users.enterprise_id
                     AND roles.status = 'active'
                    WHERE {where_sql}
                    GROUP BY
                        users.id,
                        users.username,
                        users.display_name,
                        users.status,
                        users.created_at
                    ORDER BY users.created_at DESC
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
            items=[_user_list_item_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_user(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminUser:
        row = self._core_service._load_user_row(session, user_id, enterprise_id=enterprise_id)
        self._core_service._ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
        roles = self._core_service._load_user_roles(
            session,
            user_id,
            enterprise_id=enterprise_id,
        )
        departments = self._core_service._load_user_departments(
            session,
            user_id,
            enterprise_id=enterprise_id,
        )
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

