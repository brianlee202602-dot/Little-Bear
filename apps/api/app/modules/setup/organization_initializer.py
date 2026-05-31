"""Organization, admin user, and role initialization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.modules.setup.contracts import SetupInitializationError
from app.modules.setup.repository import SetupInitializationRepository
from sqlalchemy.orm import Session


class SetupOrganizationInitializer:
    """Create enterprise, departments, admin credentials, and builtin roles."""

    def __init__(
        self,
        *,
        repository: SetupInitializationRepository | None = None,
        password_hasher_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._repository = repository or SetupInitializationRepository()
        self._password_hasher_factory = password_hasher_factory

    def insert_enterprise(
        self, session: Session, enterprise_id: UUID, enterprise_payload: dict[str, Any]
    ) -> None:
        self._repository.insert_enterprise(session, enterprise_id, enterprise_payload)

    def insert_admin_user(
        self,
        session: Session,
        admin_user_id: UUID,
        enterprise_id: UUID,
        admin_payload: dict[str, Any],
    ) -> None:
        self._repository.insert_admin_user(
            session,
            admin_user_id,
            enterprise_id,
            admin_payload,
        )

    def insert_admin_credentials(
        self, session: Session, admin_user_id: UUID, initial_password: str
    ) -> None:
        if self._password_hasher_factory is None:
            raise SetupInitializationError(
                "SETUP_DEPENDENCY_MISSING",
                "argon2-cffi is required to hash initial admin password",
                status_code=500,
            )
        password_hash = self._password_hasher_factory().hash(initial_password)
        self._repository.insert_admin_credentials_hash(session, admin_user_id, password_hash)

    def insert_departments(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        default_department_id: UUID,
        departments_payload: list[dict[str, Any]],
    ) -> dict[str, UUID]:
        return self._repository.insert_departments(
            session,
            enterprise_id,
            admin_user_id,
            default_department_id,
            departments_payload,
        )

    def insert_admin_membership(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        default_department_id: UUID,
    ) -> None:
        self._repository.insert_admin_membership(
            session,
            enterprise_id,
            admin_user_id,
            default_department_id,
        )

    def insert_builtin_roles(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        roles_payload: dict[str, Any],
    ) -> dict[str, UUID]:
        return self._repository.insert_builtin_roles(
            session,
            enterprise_id,
            admin_user_id,
            roles_payload,
        )

    def bind_admin_role(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        role_id: UUID,
    ) -> None:
        self._repository.bind_admin_role(session, enterprise_id, admin_user_id, role_id)
