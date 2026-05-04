from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modules.setup.service import SetupStatus
from app.modules.setup.token_service import SetupTokenContext, SetupTokenService
from app.shared.context import get_request_context
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from argon2 import PasswordHasher
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺依赖时由业务错误返回。
    PasswordHasher = None  # type: ignore[assignment]

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺依赖时由业务错误返回。
    Draft202012Validator = None  # type: ignore[assignment]


CONFIG_SCHEMA_PATH = Path("docs/contracts/config.schema.json")
BUILTIN_ROLE_NAMES = {
    "system_admin",
    "security_admin",
    "audit_admin",
    "department_admin",
    "knowledge_base_admin",
    "employee",
}


class SetupInitializationError(Exception):
    """初始化执行失败，带结构化错误码。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


@dataclass(frozen=True)
class SetupValidationResult:
    valid: bool
    errors: list[dict[str, object]]
    warnings: list[dict[str, object]]


@dataclass(frozen=True)
class SetupInitializationResult:
    initialized: bool
    active_config_version: int
    enterprise_id: str
    admin_user_id: str


class SetupInitializationService:
    """执行首次初始化实体和 active_config v1 发布。"""

    def validate_payload(self, payload: dict[str, Any]) -> SetupValidationResult:
        errors: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []

        self._validate_schema(payload, errors)
        setup = _as_dict(payload.get("setup"))
        config = _as_dict(payload.get("config"))

        self._validate_setup_rules(setup, config, errors)
        self._validate_secret_refs(config, errors)
        self._validate_cache_policy(config, errors)
        self._validate_keyword_search(config, warnings)

        return SetupValidationResult(valid=not errors, errors=errors, warnings=warnings)

    def initialize(
        self,
        session: Session,
        payload: dict[str, Any],
        *,
        setup_token: SetupTokenContext | None = None,
    ) -> SetupInitializationResult:
        self.ensure_setup_open(session)
        recovery_mode = self._is_recovery_setup_allowed(session)
        validation = self.validate_payload(payload)
        if not validation.valid:
            raise SetupInitializationError(
                "SETUP_CONFIG_INVALID",
                "setup payload is invalid",
                details={"errors": validation.errors, "warnings": validation.warnings},
            )
        if recovery_mode:
            return self._recover_active_config(session, payload, setup_token=setup_token)

        if PasswordHasher is None:
            raise SetupInitializationError(
                "SETUP_DEPENDENCY_MISSING",
                "argon2-cffi is required to hash initial admin password",
                status_code=500,
            )

        setup = payload["setup"]
        config = payload["config"]
        enterprise_payload = setup["organization"]["enterprise"]
        departments_payload = setup["organization"]["departments"]
        admin_payload = setup["admin"]
        roles_payload = setup["roles"]

        enterprise_id = uuid.uuid4()
        admin_user_id = uuid.uuid4()
        default_department_id = uuid.uuid4()
        config_version_id = uuid.uuid4()
        config_version = int(config["config_version"])
        config_hash = _stable_hash(config)

        self._insert_audit_log(
            session,
            event_name="setup.initialization_started",
            action="initialize",
            result="success",
            summary={
                "config_hash": config_hash,
                "config_version": config_version,
                "admin_username": admin_payload.get("username"),
                "setup_token_id": setup_token.setup_token_id if setup_token else None,
            },
            config_version=config_version,
        )
        self._mark_status(session, SetupStatus.CREATING_ADMIN)
        self._insert_enterprise(session, enterprise_id, enterprise_payload)
        self._insert_admin_user(session, admin_user_id, enterprise_id, admin_payload)
        self._insert_admin_credentials(session, admin_user_id, admin_payload["initial_password"])
        self._insert_departments(
            session,
            enterprise_id,
            admin_user_id,
            default_department_id,
            departments_payload,
        )
        self._insert_admin_membership(session, enterprise_id, admin_user_id, default_department_id)

        role_ids = self._insert_builtin_roles(session, enterprise_id, admin_user_id, roles_payload)
        self._bind_admin_role(
            session,
            enterprise_id,
            admin_user_id,
            role_ids[roles_payload["admin_role"]],
        )

        self._mark_status(session, SetupStatus.PUBLISHING_CONFIG)
        self._insert_active_config_version(
            session,
            config_version_id,
            config_version,
            config_hash,
            int(config["schema_version"]),
        )
        self._insert_system_configs(
            session,
            config_version_id,
            config_version,
            config,
            config_hash,
        )
        self._mark_initialized(session, config_version)
        self._mark_service_bootstrap_ready(session, config_version)
        if setup_token is not None:
            SetupTokenService().consume(session, setup_token)
            self._insert_audit_log(
                session,
                event_name="setup_token.used",
                action="consume_setup_token",
                result="success",
                summary={
                    "setup_token_id": setup_token.setup_token_id,
                    "jwt_jti": setup_token.jwt_jti,
                    "scopes": list(setup_token.scopes),
                },
                config_version=config_version,
            )
        self._insert_audit_log(
            session,
            event_name="setup.initialized",
            action="initialize",
            result="success",
            resource_id=str(enterprise_id),
            summary={
                "enterprise_id": str(enterprise_id),
                "admin_user_id": str(admin_user_id),
                "active_config_version": config_version,
                "config_hash": config_hash,
            },
            config_version=config_version,
        )

        return SetupInitializationResult(
            initialized=True,
            active_config_version=config_version,
            enterprise_id=str(enterprise_id),
            admin_user_id=str(admin_user_id),
        )

    def ensure_setup_open(self, session: Session) -> None:
        if self._is_initialized(session) and not self._is_recovery_setup_allowed(session):
            raise SetupInitializationError(
                "SETUP_CLOSED",
                "setup endpoints are closed after initialization",
                status_code=409,
            )

    def audit_validation(
        self,
        session: Session,
        validation: SetupValidationResult,
        payload: dict[str, Any],
        *,
        setup_token: SetupTokenContext | None = None,
    ) -> None:
        config = _as_dict(payload.get("config"))
        config_version = config.get("config_version")
        self._insert_audit_log(
            session,
            event_name=(
                "setup.config_validation_succeeded"
                if validation.valid
                else "setup.config_validation_failed"
            ),
            action="validate_config",
            result="success" if validation.valid else "failure",
            error_code=None if validation.valid else "SETUP_CONFIG_INVALID",
            summary={
                "valid": validation.valid,
                "error_count": len(validation.errors),
                "warning_count": len(validation.warnings),
                "config_hash": _stable_hash(config) if config else None,
                "setup_token_id": setup_token.setup_token_id if setup_token else None,
            },
            config_version=config_version if isinstance(config_version, int) else None,
        )

    def _validate_schema(self, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
        if Draft202012Validator is None:
            errors.append(
                _issue("SETUP_DEPENDENCY_MISSING", "$", "jsonschema is required", retryable=False)
            )
            return
        try:
            schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        except OSError as exc:
            errors.append(
                _issue(
                    "SETUP_SCHEMA_UNAVAILABLE",
                    "$",
                    f"config schema is unavailable: {exc.__class__.__name__}",
                    retryable=True,
                )
            )
            return

        validator = Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
            path = "$" + "".join(f".{part}" for part in error.path)
            errors.append(_issue("SETUP_CONFIG_INVALID", path, error.message, retryable=False))

    def _validate_setup_rules(
        self,
        setup: dict[str, Any],
        config: dict[str, Any],
        errors: list[dict[str, object]],
    ) -> None:
        admin = _as_dict(setup.get("admin"))
        organization = _as_dict(setup.get("organization"))
        roles = _as_dict(setup.get("roles"))
        departments = organization.get("departments")

        if not isinstance(departments, list) or not departments:
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.organization.departments",
                    "at least one department is required",
                )
            )
        else:
            default_count = sum(
                1
                for item in departments
                if isinstance(item, dict) and item.get("is_default") is True
            )
            if default_count != 1:
                errors.append(
                    _issue(
                        "SETUP_CONFIG_INVALID",
                        "$.setup.organization.departments",
                        "exactly one default department is required",
                    )
                )

        builtin_roles = roles.get("builtin_roles")
        if not isinstance(builtin_roles, list) or set(builtin_roles) != BUILTIN_ROLE_NAMES:
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.roles.builtin_roles",
                    "builtin roles must match P0 role set",
                )
            )
        if roles.get("admin_role") != "system_admin":
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.roles.admin_role",
                    "admin_role must be system_admin",
                )
            )
        if roles.get("default_user_role") != "employee":
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.roles.default_user_role",
                    "default_user_role must be employee",
                )
            )

        password = admin.get("initial_password")
        auth_config = _as_dict(config.get("auth"))
        min_length = auth_config.get("password_min_length", 12)
        if not isinstance(min_length, int):
            min_length = 12
        if not isinstance(password, str) or len(password) < min_length:
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password does not meet length policy",
                )
            )
        if auth_config.get("password_require_uppercase") and not any(
            char.isupper() for char in password or ""
        ):
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password requires uppercase letter",
                )
            )
        if auth_config.get("password_require_lowercase") and not any(
            char.islower() for char in password or ""
        ):
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password requires lowercase letter",
                )
            )
        if auth_config.get("password_require_digit") and not any(
            char.isdigit() for char in password or ""
        ):
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password requires digit",
                )
            )

    def _validate_secret_refs(
        self, config: dict[str, Any], errors: list[dict[str, object]]
    ) -> None:
        storage = _as_dict(config.get("storage"))
        auth = _as_dict(config.get("auth"))
        secret_refs = [
            ("$.config.storage.access_key_ref", storage.get("access_key_ref")),
            ("$.config.storage.secret_key_ref", storage.get("secret_key_ref")),
            ("$.config.auth.jwt_signing_key_ref", auth.get("jwt_signing_key_ref")),
        ]
        for path, value in secret_refs:
            if not isinstance(value, str) or not value.startswith("secret://rag/"):
                errors.append(
                    _issue("SETUP_CONFIG_INVALID", path, "secret ref must start with secret://rag/")
                )

    def _validate_cache_policy(
        self, config: dict[str, Any], errors: list[dict[str, object]]
    ) -> None:
        cache = _as_dict(config.get("cache"))
        if cache.get("cross_user_final_answer_allowed") is True:
            errors.append(
                _issue(
                    "SETUP_CONFIG_INVALID",
                    "$.config.cache.cross_user_final_answer_allowed",
                    "cross-user final answer cache is not allowed in P0",
                )
            )

    def _validate_keyword_search(
        self, config: dict[str, Any], warnings: list[dict[str, object]]
    ) -> None:
        keyword_search = _as_dict(config.get("keyword_search"))
        if keyword_search.get("keyword_analyzer") != "zhparser":
            warnings.append(
                _issue(
                    "SETUP_KEYWORD_ANALYZER_WARNING",
                    "$.config.keyword_search.keyword_analyzer",
                    "P0 Chinese keyword search expects zhparser",
                    retryable=False,
                )
            )

    def _mark_status(self, session: Session, status: SetupStatus) -> None:
        session.execute(
            text(
                """
                UPDATE system_state
                SET value_json = jsonb_build_object('status', :status), updated_at = now()
                WHERE key = 'setup_status'
                """
            ),
            {"status": status.value},
        )

    def _is_initialized(self, session: Session) -> bool:
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

    def _is_recovery_setup_allowed(self, session: Session) -> bool:
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

    def _recover_active_config(
        self,
        session: Session,
        payload: dict[str, Any],
        *,
        setup_token: SetupTokenContext | None,
    ) -> SetupInitializationResult:
        config = dict(payload["config"])
        config_version_id = uuid.uuid4()
        config_version = self._next_config_version(session)
        config["config_version"] = config_version
        config_hash = _stable_hash(config)
        enterprise_id, admin_user_id = self._load_recovery_subjects(session)

        self._insert_audit_log(
            session,
            event_name="setup.recovery_started",
            action="recover_active_config",
            result="success",
            summary={
                "config_hash": config_hash,
                "config_version": config_version,
                "setup_token_id": setup_token.setup_token_id if setup_token else None,
            },
            config_version=config_version,
        )
        self._mark_status(session, SetupStatus.RECOVERY_PUBLISHING_CONFIG)
        self._archive_active_config(session)
        self._insert_active_config_version(
            session,
            config_version_id,
            config_version,
            config_hash,
            int(config["schema_version"]),
        )
        self._insert_system_configs(
            session,
            config_version_id,
            config_version,
            config,
            config_hash,
        )
        self._mark_initialized(session, config_version)
        self._clear_recovery_setup(session)
        self._mark_service_bootstrap_ready(session, config_version)
        if setup_token is not None:
            SetupTokenService().consume(session, setup_token)
            self._insert_audit_log(
                session,
                event_name="setup_token.used",
                action="consume_setup_token",
                result="success",
                summary={
                    "setup_token_id": setup_token.setup_token_id,
                    "jwt_jti": setup_token.jwt_jti,
                    "scopes": list(setup_token.scopes),
                },
                config_version=config_version,
            )
        self._insert_audit_log(
            session,
            event_name="setup.recovered",
            action="recover_active_config",
            result="success",
            resource_id=enterprise_id,
            summary={
                "enterprise_id": enterprise_id,
                "admin_user_id": admin_user_id,
                "active_config_version": config_version,
                "config_hash": config_hash,
            },
            config_version=config_version,
        )

        return SetupInitializationResult(
            initialized=True,
            active_config_version=config_version,
            enterprise_id=enterprise_id,
            admin_user_id=admin_user_id,
        )

    def _next_config_version(self, session: Session) -> int:
        row = session.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM config_versions")
        ).one()
        return int(row._mapping["version"])

    def _load_recovery_subjects(self, session: Session) -> tuple[str, str]:
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

    def _archive_active_config(self, session: Session) -> None:
        session.execute(
            text("UPDATE system_configs SET status = 'archived' WHERE status = 'active'")
        )
        session.execute(
            text("UPDATE config_versions SET status = 'archived' WHERE status = 'active'")
        )

    def _insert_enterprise(
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

    def _insert_admin_user(
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

    def _insert_admin_credentials(
        self, session: Session, admin_user_id: uuid.UUID, initial_password: str
    ) -> None:
        password_hash = PasswordHasher().hash(initial_password)  # type: ignore[operator]
        session.execute(
            text(
                """
                INSERT INTO user_credentials(user_id, password_hash, password_alg)
                VALUES (:user_id, :password_hash, 'argon2id')
                """
            ),
            {"user_id": admin_user_id, "password_hash": password_hash},
        )

    def _insert_departments(
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

    def _insert_admin_membership(
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

    def _insert_builtin_roles(
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

    def _bind_admin_role(
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

    def _insert_active_config_version(
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
                    :schema_version, '{"valid":true}'::jsonb, 'critical', now()
                )
                """
            ),
            {
                "id": config_version_id,
                "version": config_version,
                "config_hash": config_hash,
                "schema_version": schema_version,
            },
        )

    def _insert_system_configs(
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

    def _mark_initialized(self, session: Session, config_version: int) -> None:
        state_values = {
            "setup_status": {"status": SetupStatus.INITIALIZED.value},
            "initialized": {"value": True},
            "active_config_version": {"version": config_version},
            "setup_attempt_count": {"count": 0},
            "setup_locked_until": {"until": None},
        }
        for key, value_json in state_values.items():
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

    def _clear_recovery_setup(self, session: Session) -> None:
        state_values = {
            "recovery_setup_allowed": {"value": False},
            "recovery_reason": {"reason": None},
        }
        for key, value_json in state_values.items():
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

    def _mark_service_bootstrap_ready(self, session: Session, config_version: int) -> None:
        value_json = {
            "ready": True,
            "mode": "p0_minimal",
            "targets": ["database", "active_config"],
            "config_version": config_version,
        }
        session.execute(
            text(
                """
                INSERT INTO system_state(key, value_json)
                VALUES ('service_bootstrap', CAST(:value_json AS jsonb))
                ON CONFLICT (key) DO UPDATE
                SET value_json = EXCLUDED.value_json, updated_at = now()
                """
            ),
            {"value_json": json.dumps(value_json, ensure_ascii=False)},
        )

    def _insert_audit_log(
        self,
        session: Session,
        *,
        event_name: str,
        action: str,
        result: str,
        summary: dict[str, Any],
        risk_level: str = "critical",
        resource_id: str | None = None,
        error_code: str | None = None,
        config_version: int | None = None,
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level,
                    config_version, summary_json, error_code
                )
                VALUES (
                    :id, :request_id, :trace_id, :event_name, 'setup', :actor_id,
                    'setup', :resource_id, :action, :result, :risk_level,
                    :config_version, CAST(:summary_json AS jsonb), :error_code
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "actor_id": summary.get("setup_token_id"),
                "resource_id": resource_id,
                "action": action,
                "result": result,
                "risk_level": risk_level,
                "config_version": config_version,
                "summary_json": json.dumps(
                    {key: value for key, value in summary.items() if value is not None},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "error_code": error_code,
            },
        )


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _issue(
    error_code: str,
    path: str,
    message: str,
    *,
    retryable: bool = False,
) -> dict[str, object]:
    return {
        "error_code": error_code,
        "path": path,
        "message": message,
        "retryable": retryable,
    }


def _role_scope_type(role_code: str) -> str:
    if role_code == "department_admin":
        return "department"
    if role_code == "knowledge_base_admin":
        return "knowledge_base"
    return "enterprise"


def _role_scopes(role_code: str) -> list[str]:
    scopes_by_role = {
        "system_admin": ["*"],
        "security_admin": ["security:*", "permission:*"],
        "audit_admin": ["audit:read", "query_log:read", "model_call:read"],
        "department_admin": ["department:*", "user:read"],
        "knowledge_base_admin": ["knowledge_base:*", "document:*", "import:*"],
        "employee": ["rag:query", "document:read"],
    }
    return scopes_by_role.get(role_code, [])
