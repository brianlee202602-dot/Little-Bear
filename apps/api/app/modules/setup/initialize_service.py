"""首次初始化和恢复初始化的事务服务。

该服务把 setup payload 拆成两部分处理：setup 写入首个管理员、组织和内置角色；
config 写入 config_versions/system_configs 并发布为 active_config。整个过程必须在同一
数据库事务中完成，失败时整体回滚。
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.modules.config.validator import ConfigSchemaValidator
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.setup.bootstrap_service import ServiceBootstrapService
from app.modules.setup.service import SetupStatus
from app.modules.setup.token_service import SetupTokenContext, SetupTokenService
from app.shared.context import get_request_context
from app.shared.json_utils import as_dict, stable_json_hash
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from argon2 import PasswordHasher
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺依赖时由业务错误返回。
    PasswordHasher = None  # type: ignore[assignment]

BUILTIN_ROLE_NAMES = {
    "system_admin",
    "security_admin",
    "audit_admin",
    "department_admin",
    "knowledge_base_admin",
    "employee",
}

MODEL_PROVIDER_SECRET_FIELDS = {
    "embedding": ("embedding_auth_token", "secret://rag/model/embedding-api-key"),
    "rerank": ("rerank_auth_token", "secret://rag/model/rerank-api-key"),
    "llm": ("llm_auth_token", "secret://rag/model/llm-api-key"),
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
        """执行不会落库的配置校验，供页面“校验配置”按钮调用。"""

        errors: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []

        self._validate_schema(payload, errors)
        setup = as_dict(payload.get("setup"))
        config = as_dict(payload.get("config"))

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
        # provider 明文 token 只允许在初始化请求里短暂停留，随后立即写入 Secret Store。
        prepared_payload = self._prepare_model_provider_secrets(session, payload)
        if recovery_mode:
            return self._recover_active_config(session, prepared_payload, setup_token=setup_token)

        if PasswordHasher is None:
            raise SetupInitializationError(
                "SETUP_DEPENDENCY_MISSING",
                "argon2-cffi is required to hash initial admin password",
                status_code=500,
            )

        setup = prepared_payload["setup"]
        config = prepared_payload["config"]
        enterprise_payload = setup["organization"]["enterprise"]
        departments_payload = setup["organization"]["departments"]
        admin_payload = setup["admin"]
        roles_payload = setup["roles"]

        enterprise_id = uuid.uuid4()
        admin_user_id = uuid.uuid4()
        default_department_id = uuid.uuid4()
        config_version_id = uuid.uuid4()
        config_version = int(config["config_version"])
        config_hash = stable_json_hash(config)
        # 初始化提交前先做依赖检查；失败则不创建管理员和 active_config。
        bootstrap_result = ServiceBootstrapService().bootstrap(session, config=config)
        if not bootstrap_result.ready:
            raise SetupInitializationError(
                "SETUP_BOOTSTRAP_FAILED",
                "service bootstrap checks failed",
                status_code=503,
                details={"checks": [check.to_dict() for check in bootstrap_result.checks]},
            )

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
        # 以下写入共享同一事务，任一失败都会由 session_scope 回滚。
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
        ServiceBootstrapService().persist_result(session, bootstrap_result)
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
        config = as_dict(payload.get("config"))
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
                "config_hash": stable_json_hash(config) if config else None,
                "setup_token_id": setup_token.setup_token_id if setup_token else None,
            },
            config_version=config_version if isinstance(config_version, int) else None,
        )

    def _validate_schema(self, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
        try:
            issues = ConfigSchemaValidator().validate_setup_payload(payload)
        except ConfigServiceError as exc:
            errors.append(
                _issue(
                    _setup_schema_error_code(exc.error_code),
                    "$",
                    exc.message,
                    retryable=exc.retryable,
                )
            )
            return

        for issue in issues:
            errors.append(
                _issue("SETUP_CONFIG_INVALID", issue.path, issue.message, retryable=False)
            )

    def _prepare_model_provider_secrets(
        self,
        session: Session,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        prepared_payload = deepcopy(payload)
        setup = as_dict(prepared_payload.get("setup"))
        config = as_dict(prepared_payload.get("config"))
        model_provider_secrets = as_dict(setup.pop("model_provider_secrets", None))
        model_gateway = as_dict(config.get("model_gateway"))
        providers = as_dict(model_gateway.get("providers"))

        for provider_name, (secret_field, secret_ref) in MODEL_PROVIDER_SECRET_FIELDS.items():
            secret_value = model_provider_secrets.get(secret_field)
            if not isinstance(secret_value, str) or not secret_value.strip():
                continue

            provider = as_dict(providers.get(provider_name))
            try:
                SecretStoreService().put_secret(
                    session,
                    secret_ref=secret_ref,
                    secret_value=secret_value.strip(),
                )
            except SecretStoreError as exc:
                raise SetupInitializationError(
                    "SETUP_SECRET_WRITE_FAILED",
                    f"failed to store model provider secret for {provider_name}",
                    status_code=500,
                    details={
                        "provider": provider_name,
                        "secret_ref": secret_ref,
                        "reason": str(exc),
                    },
                ) from exc
            provider["auth_token_ref"] = secret_ref
            providers[provider_name] = provider

        model_gateway["providers"] = providers
        config["model_gateway"] = model_gateway
        prepared_payload["setup"] = setup
        prepared_payload["config"] = config
        return prepared_payload

    def _validate_setup_rules(
        self,
        setup: dict[str, Any],
        config: dict[str, Any],
        errors: list[dict[str, object]],
    ) -> None:
        admin = as_dict(setup.get("admin"))
        organization = as_dict(setup.get("organization"))
        roles = as_dict(setup.get("roles"))
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
        auth_config = as_dict(config.get("auth"))
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
        storage = as_dict(config.get("storage"))
        auth = as_dict(config.get("auth"))
        model_gateway = as_dict(config.get("model_gateway"))
        model_providers = as_dict(model_gateway.get("providers"))
        secret_refs = [
            ("$.config.storage.access_key_ref", storage.get("access_key_ref"), True),
            ("$.config.storage.secret_key_ref", storage.get("secret_key_ref"), True),
            ("$.config.auth.jwt_signing_key_ref", auth.get("jwt_signing_key_ref"), True),
            ("$.config.model_gateway.auth_token_ref", model_gateway.get("auth_token_ref"), False),
        ]
        for provider_name in ("embedding", "rerank", "llm"):
            provider = as_dict(model_providers.get(provider_name))
            secret_refs.append(
                (
                    f"$.config.model_gateway.providers.{provider_name}.auth_token_ref",
                    provider.get("auth_token_ref"),
                    False,
                )
            )

        for path, value, required in secret_refs:
            if not value and not required:
                continue
            if not isinstance(value, str) or not value.startswith("secret://rag/"):
                errors.append(
                    _issue("SETUP_CONFIG_INVALID", path, "secret ref must start with secret://rag/")
                )

    def _validate_cache_policy(
        self, config: dict[str, Any], errors: list[dict[str, object]]
    ) -> None:
        cache = as_dict(config.get("cache"))
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
        keyword_search = as_dict(config.get("keyword_search"))
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
                SET value_json = CAST(:value_json AS jsonb), updated_at = now()
                WHERE key = 'setup_status'
                """
            ),
            {"value_json": json.dumps({"status": status.value}, ensure_ascii=False)},
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
        """恢复初始化只重发 active_config，不重建首个管理员、组织或角色。"""

        config = dict(payload["config"])
        config_version_id = uuid.uuid4()
        config_version = self._next_config_version(session)
        config["config_version"] = config_version
        config_hash = stable_json_hash(config)
        enterprise_id, admin_user_id = self._load_recovery_subjects(session)
        bootstrap_result = ServiceBootstrapService().bootstrap(session, config=config)
        if not bootstrap_result.ready:
            raise SetupInitializationError(
                "SETUP_BOOTSTRAP_FAILED",
                "service bootstrap checks failed",
                status_code=503,
                details={"checks": [check.to_dict() for check in bootstrap_result.checks]},
            )

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
        ServiceBootstrapService().persist_result(session, bootstrap_result)
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
        # 恢复初始化先归档旧 active，再写入新 active，避免两个 active 版本并存。
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
        # 密码明文只在请求生命周期内存在，数据库保存 argon2id hash。
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
        # config_versions 保存版本元数据；真正配置 bundle 存在 system_configs。
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

    def _insert_system_configs(
        self,
        session: Session,
        config_version_id: uuid.UUID,
        config_version: int,
        config: dict[str, Any],
        config_hash: str,
    ) -> None:
        # P0 以单条 active_config bundle 存储，后续可拆成多 scope/多 key 配置。
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

    def record_initialization_failure(
        self,
        session: Session,
        *,
        error_code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self._mark_status(session, SetupStatus.INITIALIZATION_FAILED)
        self._insert_audit_log(
            session,
            event_name="setup.initialization_failed",
            action="initialize",
            result="failure",
            error_code=error_code,
            summary={
                "error_code": error_code,
                "message": message[:300],
                "detail_keys": sorted((details or {}).keys()),
            },
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


def _setup_schema_error_code(config_error_code: str) -> str:
    if config_error_code == "CONFIG_SCHEMA_VALIDATOR_UNAVAILABLE":
        return "SETUP_DEPENDENCY_MISSING"
    if config_error_code == "CONFIG_SCHEMA_UNAVAILABLE":
        return "SETUP_SCHEMA_UNAVAILABLE"
    if config_error_code == "CONFIG_SCHEMA_MALFORMED":
        return "SETUP_SCHEMA_MALFORMED"
    return "SETUP_CONFIG_INVALID"


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
        "department_admin": [
            "department:*",
            "user:read",
            "knowledge_base:read",
            "document:read",
            "rag:query",
        ],
        "knowledge_base_admin": [
            "knowledge_base:*",
            "folder:*",
            "document:*",
            "document:import",
            "import_job:read:self",
            "import_job:manage:self",
            "import_job:read",
            "import:*",
        ],
        "employee": ["knowledge_base:read", "rag:query", "document:read"],
    }
    return scopes_by_role.get(role_code, [])
