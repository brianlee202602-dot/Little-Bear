"""SQL repository for setup initialization."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.modules.setup.contracts import (
    SetupInitializationError,
    _role_scope_type,
    _role_scopes,
)
from app.modules.setup.service import SetupStatus
from sqlalchemy import text
from sqlalchemy.orm import Session


class SetupInitializationRepository:
    """Centralized persistence operations for first-time and recovery setup."""

    def mark_status(self, session: Session, status: SetupStatus) -> None:
        session.execute(
            text(
                """
                UPDATE system_state
                SET value_json = CAST(:value_json AS jsonb), updated_at = now()
                WHERE key = 'setup_status'
                """
            ),
            {"value_json": json.dumps({"status": status.value}, ensure_ascii=False)},
        )

    def is_initialized(self, session: Session) -> bool:
        row = session.execute(
            text(
                """
                SELECT value_json
                FROM system_state
                WHERE key = 'initialized'
                """
            )
        ).one_or_none()
        if row is None:
            raise SetupInitializationError(
                "SETUP_MIGRATION_REQUIRED",
                "system_state is missing; run database migrations first",
                status_code=409,
            )
        value_json = row._mapping["value_json"]
        return isinstance(value_json, dict) and value_json.get("value") is True

    def is_recovery_setup_allowed(self, session: Session) -> bool:
        row = session.execute(
            text(
                """
                SELECT value_json
                FROM system_state
                WHERE key = 'recovery_setup_allowed'
                """
            )
        ).one_or_none()
        if row is None:
            return False
        value_json = row._mapping["value_json"]
        return isinstance(value_json, dict) and value_json.get("value") is True

    def next_config_version(self, session: Session) -> int:
        row = session.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM config_versions")
        ).one()
        return int(row._mapping["version"])

    def load_recovery_subjects(self, session: Session) -> tuple[str, str]:
        enterprise = session.execute(
            text(
                """
                SELECT id::text AS id
                FROM enterprises
                WHERE status = 'active'
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
        ).one_or_none()
        admin_user = session.execute(
            text(
                """
                SELECT u.id::text AS id
                FROM users u
                JOIN role_bindings rb ON rb.user_id = u.id
                JOIN roles r ON r.id = rb.role_id
                WHERE u.status = 'active'
                  AND rb.status = 'active'
                  AND r.code = 'system_admin'
                ORDER BY u.created_at ASC
                LIMIT 1
                """
            )
        ).one_or_none()
        if enterprise is None or admin_user is None:
            raise SetupInitializationError(
                "SETUP_RECOVERY_UNAVAILABLE",
                "recovery setup requires an active enterprise and system_admin user",
                status_code=409,
            )
        return enterprise._mapping["id"], admin_user._mapping["id"]

    def archive_active_config(self, session: Session) -> None:
        session.execute(
            text("UPDATE system_configs SET status = 'archived' WHERE status = 'active'")
        )
        session.execute(
            text("UPDATE config_versions SET status = 'archived' WHERE status = 'active'")
        )

    def insert_enterprise(
        self, session: Session, enterprise_id: uuid.UUID, enterprise_payload: dict[str, Any]
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO enterprises(id, code, name, status)
                VALUES (:id, :code, :name, 'active')
                """
            ),
            {
                "id": enterprise_id,
                "code": enterprise_payload["code"],
                "name": enterprise_payload["name"],
            },
        )

    def insert_admin_user(
        self,
        session: Session,
        admin_user_id: uuid.UUID,
        enterprise_id: uuid.UUID,
        admin_payload: dict[str, Any],
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO users(
                    id, enterprise_id, username, display_name, email, phone, status
                )
                VALUES (
                    :id, :enterprise_id, :username, :display_name, :email, :phone, 'active'
                )
                """
            ),
            {
                "id": admin_user_id,
                "enterprise_id": enterprise_id,
                "username": admin_payload["username"],
                "display_name": admin_payload["display_name"],
                "email": admin_payload.get("email"),
                "phone": admin_payload.get("phone"),
            },
        )

    def insert_admin_credentials_hash(
        self, session: Session, admin_user_id: uuid.UUID, password_hash: str
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO user_credentials(user_id, password_hash, password_alg)
                VALUES (:user_id, :password_hash, 'argon2id')
                """
            ),
            {"user_id": admin_user_id, "password_hash": password_hash},
        )

    def insert_departments(
        self,
        session: Session,
        enterprise_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        default_department_id: uuid.UUID,
        departments_payload: list[dict[str, Any]],
    ) -> dict[str, uuid.UUID]:
        department_ids: dict[str, uuid.UUID] = {}
        for department in departments_payload:
            department_id = default_department_id if department["is_default"] else uuid.uuid4()
            department_ids[department["code"]] = department_id
            session.execute(
                text(
                    """
                    INSERT INTO departments(
                        id, enterprise_id, code, name, status, is_default, created_by, updated_by
                    )
                    VALUES (
                        :id, :enterprise_id, :code, :name, 'active', :is_default,
                        :admin_user_id, :admin_user_id
                    )
                    """
                ),
                {
                    "id": department_id,
                    "enterprise_id": enterprise_id,
                    "code": department["code"],
                    "name": department["name"],
                    "is_default": department["is_default"],
                    "admin_user_id": admin_user_id,
                },
            )
        return department_ids

    def insert_admin_membership(
        self,
        session: Session,
        enterprise_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        default_department_id: uuid.UUID,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO user_department_memberships(
                    id, enterprise_id, user_id, department_id, is_primary, status, created_by
                )
                VALUES (
                    :id, :enterprise_id, :user_id, :department_id, true, 'active', :created_by
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "enterprise_id": enterprise_id,
                "user_id": admin_user_id,
                "department_id": default_department_id,
                "created_by": admin_user_id,
            },
        )

    def insert_builtin_roles(
        self,
        session: Session,
        enterprise_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        roles_payload: dict[str, Any],
    ) -> dict[str, uuid.UUID]:
        role_ids: dict[str, uuid.UUID] = {}
        for role_code in roles_payload["builtin_roles"]:
            role_id = uuid.uuid4()
            role_ids[role_code] = role_id
            session.execute(
                text(
                    """
                    INSERT INTO roles(
                        id, enterprise_id, code, name, scope_type, scopes, is_builtin,
                        status, created_by, updated_by
                    )
                    VALUES (
                        :id, :enterprise_id, :code, :name, :scope_type, :scopes, true,
                        'active', :admin_user_id, :admin_user_id
                    )
                    """
                ),
                {
                    "id": role_id,
                    "enterprise_id": enterprise_id,
                    "code": role_code,
                    "name": role_code.replace("_", " ").title(),
                    "scope_type": _role_scope_type(role_code),
                    "scopes": _role_scopes(role_code),
                    "admin_user_id": admin_user_id,
                },
            )
        return role_ids

    def bind_admin_role(
        self,
        session: Session,
        enterprise_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO role_bindings(
                    id, enterprise_id, user_id, role_id, scope_type, scope_id, status, created_by
                )
                VALUES (
                    :id, :enterprise_id, :user_id, :role_id,
                    'enterprise', null, 'active', :created_by
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "enterprise_id": enterprise_id,
                "user_id": admin_user_id,
                "role_id": role_id,
                "created_by": admin_user_id,
            },
        )

    def insert_active_config_version(
        self,
        session: Session,
        config_version_id: uuid.UUID,
        config_version: int,
        config_hash: str,
        schema_version: int,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO config_versions(
                    id, version, scope_type, scope_id, status, config_hash,
                    schema_version, validation_result_json, risk_level, activated_at
                )
                VALUES (
                    :id, :version, 'global', 'global', 'active', :config_hash,
                    :schema_version, CAST(:validation_result_json AS jsonb), 'critical', now()
                )
                """
            ),
            {
                "id": config_version_id,
                "version": config_version,
                "config_hash": config_hash,
                "schema_version": schema_version,
                "validation_result_json": json.dumps({"valid": True}, ensure_ascii=False),
            },
        )

    def insert_system_configs(
        self,
        session: Session,
        config_version_id: uuid.UUID,
        config_version: int,
        config: dict[str, Any],
        config_hash: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO system_configs(
                    id, config_version_id, version, scope_type, scope_id, key,
                    value_json, value_hash, status
                )
                VALUES (
                    :id, :config_version_id, :version, 'global', 'global',
                    'active_config', CAST(:value_json AS jsonb), :value_hash, 'active'
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "config_version_id": config_version_id,
                "version": config_version,
                "value_json": json.dumps(config, ensure_ascii=False, sort_keys=True),
                "value_hash": config_hash,
            },
        )

    def mark_initialized(self, session: Session, config_version: int) -> None:
        state_values = {
            "setup_status": {"status": SetupStatus.INITIALIZED.value},
            "initialized": {"value": True},
            "active_config_version": {"version": config_version},
            "setup_attempt_count": {"count": 0},
            "setup_locked_until": {"until": None},
        }
        self._update_state_values(session, state_values)

    def clear_recovery_setup(self, session: Session) -> None:
        state_values = {
            "recovery_setup_allowed": {"value": False},
            "recovery_reason": {"reason": None},
        }
        self._update_state_values(session, state_values)

    def _update_state_values(self, session: Session, values: dict[str, dict[str, Any]]) -> None:
        for key, value_json in values.items():
            session.execute(
                text(
                    """
                    UPDATE system_state
                    SET value_json = CAST(:value_json AS jsonb), updated_at = now()
                    WHERE key = :key
                    """
                ),
                {"key": key, "value_json": json.dumps(value_json, ensure_ascii=False)},
            )
