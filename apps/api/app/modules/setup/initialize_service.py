"""Setup 初始化事务编排服务。"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from app.modules.audit import AuditWriter
from app.modules.config.validator import ConfigSchemaValidator
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.setup.bootstrap_service import ServiceBootstrapService
from app.modules.setup.config_publisher import SetupConfigPublisher
from app.modules.setup.contracts import (
    BUILTIN_ROLE_NAMES,
    MODEL_PROVIDER_SECRET_FIELDS,
    SetupInitializationError,
    SetupInitializationResult,
    SetupValidationResult,
    _issue,
    _role_scope_type,
    _role_scopes,
    _setup_schema_error_code,
)
from app.modules.setup.initialization_audit import SetupInitializationAuditWriter
from app.modules.setup.organization_initializer import SetupOrganizationInitializer
from app.modules.setup.payload_validator import SetupPayloadValidator
from app.modules.setup.recovery_service import SetupRecoveryService
from app.modules.setup.repository import SetupInitializationRepository
from app.modules.setup.secret_initializer import ModelProviderSecretInitializer
from app.modules.setup.service import SetupStatus
from app.modules.setup.token_service import SetupTokenContext, SetupTokenService
from app.shared.json_utils import as_dict, stable_json_hash
from sqlalchemy.orm import Session

try:
    from argon2 import PasswordHasher
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺依赖时由业务错误返回。
    PasswordHasher = None  # type: ignore[assignment]


class SetupInitializationService:
    """面向 route 的初始化入口，编排校验、组织写入、配置发布和恢复初始化。"""

    def __init__(
        self,
        *,
        repository: SetupInitializationRepository | None = None,
    ) -> None:
        self._repository = repository or SetupInitializationRepository()

    def validate_payload(self, payload: dict[str, Any]) -> SetupValidationResult:
        return SetupPayloadValidator(
            schema_validator_factory=ConfigSchemaValidator,
        ).validate(payload)

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

    def _prepare_model_provider_secrets(
        self,
        session: Session,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return ModelProviderSecretInitializer(
            secret_store_factory=SecretStoreService,
            secret_error_type=SecretStoreError,
        ).prepare(session, payload)

    def _mark_status(self, session: Session, status: SetupStatus) -> None:
        self._repository.mark_status(session, status)

    def _is_initialized(self, session: Session) -> bool:
        return self._repository.is_initialized(session)

    def _is_recovery_setup_allowed(self, session: Session) -> bool:
        return self._repository.is_recovery_setup_allowed(session)

    def _recover_active_config(
        self,
        session: Session,
        payload: dict[str, Any],
        *,
        setup_token: SetupTokenContext | None,
    ) -> SetupInitializationResult:
        return SetupRecoveryService(
            repository=self._repository,
            config_publisher=SetupConfigPublisher(repository=self._repository),
            audit_writer=self._audit_writer(),
            bootstrap_service_factory=ServiceBootstrapService,
            setup_token_service_factory=SetupTokenService,
        ).recover(session, payload, setup_token=setup_token)

    def _next_config_version(self, session: Session) -> int:
        return self._repository.next_config_version(session)

    def _load_recovery_subjects(self, session: Session) -> tuple[str, str]:
        return self._repository.load_recovery_subjects(session)

    def _archive_active_config(self, session: Session) -> None:
        SetupConfigPublisher(repository=self._repository).archive_active_config(session)

    def _insert_enterprise(
        self, session: Session, enterprise_id: UUID, enterprise_payload: dict[str, Any]
    ) -> None:
        self._organization_initializer().insert_enterprise(
            session,
            enterprise_id,
            enterprise_payload,
        )

    def _insert_admin_user(
        self,
        session: Session,
        admin_user_id: UUID,
        enterprise_id: UUID,
        admin_payload: dict[str, Any],
    ) -> None:
        self._organization_initializer().insert_admin_user(
            session,
            admin_user_id,
            enterprise_id,
            admin_payload,
        )

    def _insert_admin_credentials(
        self, session: Session, admin_user_id: UUID, initial_password: str
    ) -> None:
        self._organization_initializer().insert_admin_credentials(
            session,
            admin_user_id,
            initial_password,
        )

    def _insert_departments(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        default_department_id: UUID,
        departments_payload: list[dict[str, Any]],
    ) -> dict[str, UUID]:
        return self._organization_initializer().insert_departments(
            session,
            enterprise_id,
            admin_user_id,
            default_department_id,
            departments_payload,
        )

    def _insert_admin_membership(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        default_department_id: UUID,
    ) -> None:
        self._organization_initializer().insert_admin_membership(
            session,
            enterprise_id,
            admin_user_id,
            default_department_id,
        )

    def _insert_builtin_roles(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        roles_payload: dict[str, Any],
    ) -> dict[str, UUID]:
        return self._organization_initializer().insert_builtin_roles(
            session,
            enterprise_id,
            admin_user_id,
            roles_payload,
        )

    def _bind_admin_role(
        self,
        session: Session,
        enterprise_id: UUID,
        admin_user_id: UUID,
        role_id: UUID,
    ) -> None:
        self._organization_initializer().bind_admin_role(
            session,
            enterprise_id,
            admin_user_id,
            role_id,
        )

    def _insert_active_config_version(
        self,
        session: Session,
        config_version_id: UUID,
        config_version: int,
        config_hash: str,
        schema_version: int,
    ) -> None:
        SetupConfigPublisher(repository=self._repository).insert_active_config_version(
            session,
            config_version_id,
            config_version,
            config_hash,
            schema_version,
        )

    def _insert_system_configs(
        self,
        session: Session,
        config_version_id: UUID,
        config_version: int,
        config: dict[str, Any],
        config_hash: str,
    ) -> None:
        SetupConfigPublisher(repository=self._repository).insert_system_configs(
            session,
            config_version_id,
            config_version,
            config,
            config_hash,
        )

    def _mark_initialized(self, session: Session, config_version: int) -> None:
        SetupConfigPublisher(repository=self._repository).mark_initialized(session, config_version)

    def _clear_recovery_setup(self, session: Session) -> None:
        SetupConfigPublisher(repository=self._repository).clear_recovery_setup(session)

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
        self._audit_writer().write(
            session,
            event_name=event_name,
            action=action,
            result=result,
            summary=summary,
            risk_level=risk_level,
            resource_id=resource_id,
            error_code=error_code,
            config_version=config_version,
        )

    def _organization_initializer(self) -> SetupOrganizationInitializer:
        return SetupOrganizationInitializer(
            repository=self._repository,
            password_hasher_factory=PasswordHasher,
        )

    def _audit_writer(self) -> SetupInitializationAuditWriter:
        return SetupInitializationAuditWriter(audit_writer_factory=AuditWriter)


__all__ = [
    "BUILTIN_ROLE_NAMES",
    "MODEL_PROVIDER_SECRET_FIELDS",
    "ConfigSchemaValidator",
    "PasswordHasher",
    "SecretStoreError",
    "SecretStoreService",
    "ServiceBootstrapService",
    "SetupInitializationError",
    "SetupInitializationResult",
    "SetupInitializationService",
    "SetupStatus",
    "SetupTokenContext",
    "SetupTokenService",
    "SetupValidationResult",
    "_issue",
    "_role_scope_type",
    "_role_scopes",
    "_setup_schema_error_code",
]
