"""Auth user, role, department context loading."""

from __future__ import annotations

from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthDepartment, AuthRole, AuthUser
from app.modules.auth.utils import merge_scopes, normalize_scopes
from sqlalchemy import text
from sqlalchemy.orm import Session


class UserContextLoader:
    """Loads current auth user context from database."""

    def load_user_context(self, session: Session, user_id: str) -> AuthUser:
        user_row = session.execute(
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
                WHERE id = :user_id AND deleted_at IS NULL
                """
            ),
            {"user_id": user_id},
        ).one_or_none()
        if user_row is None:
            raise AuthServiceError("AUTH_USER_NOT_FOUND", "user is not found", status_code=401)

        user_data = user_row._mapping
        roles = self.load_roles(session, user_id)
        departments = self.load_departments(session, user_id)
        scopes = merge_scopes(roles)
        return AuthUser(
            id=user_data["user_id"],
            enterprise_id=user_data["enterprise_id"],
            username=user_data["username"],
            display_name=user_data["display_name"],
            email=user_data["email"],
            phone=user_data["phone"],
            status=user_data["status"],
            roles=roles,
            departments=departments,
            scopes=scopes,
        )

    def load_roles(self, session: Session, user_id: str) -> tuple[AuthRole, ...]:
        rows = session.execute(
            text(
                """
                SELECT
                    r.id::text AS role_id,
                    r.code,
                    r.name,
                    r.scope_type,
                    rb.scope_id::text AS scope_id,
                    r.is_builtin,
                    r.status,
                    r.scopes
                FROM role_bindings rb
                JOIN roles r ON r.id = rb.role_id
                WHERE rb.user_id = :user_id
                  AND rb.status = 'active'
                  AND r.status = 'active'
                ORDER BY r.code
                """
            ),
            {"user_id": user_id},
        ).all()
        return tuple(
            AuthRole(
                id=row._mapping["role_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                scope_type=row._mapping["scope_type"],
                scope_id=row._mapping["scope_id"],
                is_builtin=bool(row._mapping["is_builtin"]),
                status=row._mapping["status"],
                scopes=normalize_scopes(row._mapping["scopes"]),
            )
            for row in rows
        )

    def load_departments(self, session: Session, user_id: str) -> tuple[AuthDepartment, ...]:
        rows = session.execute(
            text(
                """
                SELECT
                    d.id::text AS department_id,
                    d.code,
                    d.name,
                    d.status,
                    udm.is_primary
                FROM user_department_memberships udm
                JOIN departments d ON d.id = udm.department_id
                WHERE udm.user_id = :user_id
                  AND udm.status = 'active'
                ORDER BY udm.is_primary DESC, d.code
                """
            ),
            {"user_id": user_id},
        ).all()
        return tuple(
            AuthDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                status=row._mapping["status"],
                is_primary=bool(row._mapping["is_primary"]),
            )
            for row in rows
        )
