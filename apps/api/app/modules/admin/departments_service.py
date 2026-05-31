"""Department administration service."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.admin.access_control import AdminActorContext
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.mappers import (
    _department_from_mapping,
    _department_list_item_from_mapping,
    _department_option_from_mapping,
)
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminDepartmentList,
    AdminDepartmentOptionList,
)
from app.modules.admin.utils import _database_error
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


class AdminDepartmentsService:
    """部门管理写模型。"""

    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

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
        """读取当前企业部门列表摘要。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "departments.enterprise_id = CAST(:enterprise_id AS uuid)",
            "departments.deleted_at IS NULL",
            "departments.status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("departments.name ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("departments.status = :status")
            params["status"] = status
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT id::text AS department_id, name, status, is_default
                    FROM departments
                    WHERE {where_sql}
                    ORDER BY is_default DESC, name, id
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
            items=[_department_list_item_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_department_options(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
    ) -> AdminDepartmentOptionList:
        """读取部门下拉选项，避免 selector 复用完整部门详情 DTO。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "departments.enterprise_id = CAST(:enterprise_id AS uuid)",
            "departments.deleted_at IS NULL",
            "departments.status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("departments.name ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("departments.status = :status")
            params["status"] = status
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT id::text AS department_id, name, status, is_default
                    FROM departments
                    WHERE {where_sql}
                    ORDER BY is_default DESC, name, id
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
                "ADMIN_DEPARTMENT_OPTIONS_UNAVAILABLE",
                "department options cannot be read",
                exc,
            ) from exc
        return AdminDepartmentOptionList(
            items=[_department_option_from_mapping(row._mapping) for row in rows],
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

        self._core_service._ensure_actor_can_manage_departments(actor_context)
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
            department_org_version = self._core_service._bump_org_version(
                session,
                enterprise_id,
            )
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
            permission_version = self._core_service._bump_permission_version(
                session,
                enterprise_id,
            )
            self._core_service._insert_audit_log(
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

        self._core_service._ensure_actor_can_manage_departments(actor_context)
        current = self._core_service.get_department(
            session,
            department_id,
            enterprise_id=enterprise_id,
        )
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
            org_version = self._core_service._bump_org_version(session, enterprise_id)
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

        permission_version = self._core_service._bump_permission_version(
            session,
            enterprise_id,
        )
        after = self._core_service.get_department(
            session,
            department_id,
            enterprise_id=enterprise_id,
        )
        self._core_service._insert_audit_log(
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
                "changed_fields": [
                    field.split(" = ", 1)[0]
                    for field in updates
                    if field != "org_version = :org_version"
                ],
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
        self._core_service._ensure_actor_can_manage_departments(actor_context)
        current = self._core_service.get_department(
            session,
            department_id,
            enterprise_id=enterprise_id,
        )
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
            org_version = self._core_service._bump_org_version(session, enterprise_id)
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

        permission_version = self._core_service._bump_permission_version(
            session,
            enterprise_id,
        )
        self._core_service._insert_audit_log(
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
