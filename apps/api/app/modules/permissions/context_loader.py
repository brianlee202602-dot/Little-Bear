"""权限上下文加载。"""

from __future__ import annotations

import json
from typing import Any

from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.schemas import (
    PermissionContext,
    PermissionDepartment,
    PermissionRole,
)
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

BASE_USER_SCOPES = ("auth:session", "auth:password:update:self")


class PermissionContextLoader:
    """从用户、部门、角色和企业版本构建权限上下文。"""

    def build_context(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str | None = None,
        request_id: str | None = None,
    ) -> PermissionContext:
        user = self._load_user(session, user_id=user_id, enterprise_id=enterprise_id)
        if user["status"] != "active":
            raise PermissionServiceError(
                "PERM_DENIED",
                "user is not active",
                details={"user_id": user_id, "status": user["status"]},
            )

        versions = self._load_enterprise_versions(session, enterprise_id=user["enterprise_id"])
        departments = self._load_departments(
            session,
            user_id=user_id,
            enterprise_id=user["enterprise_id"],
        )
        roles = self._load_roles(session, user_id=user_id, enterprise_id=user["enterprise_id"])
        scopes = merge_scopes(roles)
        department_ids = tuple(department.id for department in departments)
        role_ids = tuple(role.id for role in roles)
        filter_hash = permission_filter_hash(
            enterprise_id=user["enterprise_id"],
            user_id=user_id,
            department_ids=department_ids,
            role_ids=role_ids,
            scopes=scopes,
            permission_version=versions["permission_version"],
            org_version=versions["org_version"],
        )
        return PermissionContext(
            enterprise_id=user["enterprise_id"],
            user_id=user_id,
            username=user["username"],
            status=user["status"],
            department_ids=department_ids,
            departments=departments,
            roles=roles,
            role_ids=role_ids,
            scopes=scopes,
            permission_version=versions["permission_version"],
            org_version=versions["org_version"],
            permission_filter_hash=filter_hash,
            request_id=request_id,
        )

    def _load_user(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str | None,
    ) -> dict[str, Any]:
        conditions = ["id = CAST(:user_id AS uuid)", "deleted_at IS NULL"]
        params = {"user_id": user_id}
        if enterprise_id is not None:
            conditions.append("enterprise_id = CAST(:enterprise_id AS uuid)")
            params["enterprise_id"] = enterprise_id
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS user_id,
                        enterprise_id::text AS enterprise_id,
                        username,
                        status
                    FROM users
                    WHERE {" AND ".join(conditions)}
                    LIMIT 1
                    """
                ),
                params,
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise permission_database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission user context cannot be loaded",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "PERM_DENIED",
                "user is not found",
                details={"user_id": user_id},
            )
        return dict(row._mapping)

    def _load_enterprise_versions(self, session: Session, *, enterprise_id: str) -> dict[str, int]:
        try:
            row = session.execute(
                text(
                    """
                    SELECT org_version, permission_version
                    FROM enterprises
                    WHERE id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise permission_database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission versions cannot be loaded",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "PERM_DENIED",
                "enterprise is not active",
                details={"enterprise_id": enterprise_id},
            )
        return {
            "org_version": int(row._mapping["org_version"]),
            "permission_version": int(row._mapping["permission_version"]),
        }

    def _load_departments(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
    ) -> tuple[PermissionDepartment, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS department_id,
                        d.code,
                        d.name,
                        udm.is_primary
                    FROM user_department_memberships udm
                    JOIN departments d ON d.id = udm.department_id
                    WHERE udm.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND udm.user_id = CAST(:user_id AS uuid)
                      AND udm.status = 'active'
                      AND d.status = 'active'
                      AND d.deleted_at IS NULL
                    ORDER BY udm.is_primary DESC, d.code
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise permission_database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission departments cannot be loaded",
                exc,
            ) from exc
        return tuple(
            PermissionDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                is_primary=bool(row._mapping["is_primary"]),
            )
            for row in rows
        )

    def _load_roles(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
    ) -> tuple[PermissionRole, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        r.id::text AS role_id,
                        r.code,
                        r.name,
                        rb.scope_type,
                        rb.scope_id::text AS scope_id,
                        r.scopes
                    FROM role_bindings rb
                    JOIN roles r ON r.id = rb.role_id
                    WHERE rb.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND rb.user_id = CAST(:user_id AS uuid)
                      AND rb.status = 'active'
                      AND r.status = 'active'
                    ORDER BY r.code, rb.scope_type, rb.scope_id
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise permission_database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission roles cannot be loaded",
                exc,
            ) from exc
        return tuple(
            PermissionRole(
                id=row._mapping["role_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                scope_type=row._mapping["scope_type"],
                scope_id=row._mapping["scope_id"],
                scopes=normalize_scopes(row._mapping["scopes"]),
            )
            for row in rows
        )


def merge_scopes(roles: tuple[PermissionRole, ...]) -> tuple[str, ...]:
    scopes = set(BASE_USER_SCOPES)
    for role in roles:
        scopes.update(role.scopes)
    return tuple(sorted(scopes))


def permission_filter_hash(
    *,
    enterprise_id: str,
    user_id: str,
    department_ids: tuple[str, ...],
    role_ids: tuple[str, ...],
    scopes: tuple[str, ...],
    permission_version: int,
    org_version: int,
) -> str:
    return stable_json_hash(
        {
            "enterprise_id": enterprise_id,
            "user_id": user_id,
            "department_ids": sorted(department_ids),
            "role_ids": sorted(role_ids),
            "scopes": sorted(scopes),
            "permission_version": permission_version,
            "org_version": org_version,
        }
    )


def normalize_scopes(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return (value,)
        return normalize_scopes(parsed)
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted({str(item) for item in value if str(item)}))
    return ()


def permission_database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> PermissionServiceError:
    return PermissionServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
