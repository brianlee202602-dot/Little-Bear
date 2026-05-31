"""Setup 恢复初始化编排。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from app.modules.setup.config_publisher import SetupConfigPublisher
from app.modules.setup.contracts import SetupInitializationError, SetupInitializationResult
from app.modules.setup.initialization_audit import SetupInitializationAuditWriter
from app.modules.setup.repository import SetupInitializationRepository
from app.modules.setup.service import SetupStatus
from app.modules.setup.token_service import SetupTokenContext
from app.shared.json_utils import stable_json_hash
from sqlalchemy.orm import Session


class SetupRecoveryService:
    """恢复初始化只重发 active_config，不重建首个管理员、组织或角色。"""

    def __init__(
        self,
        *,
        repository: SetupInitializationRepository | None = None,
        config_publisher: SetupConfigPublisher | None = None,
        audit_writer: SetupInitializationAuditWriter,
        bootstrap_service_factory: Callable[[], Any],
        setup_token_service_factory: Callable[[], Any],
    ) -> None:
        self._repository = repository or SetupInitializationRepository()
        self._config_publisher = config_publisher or SetupConfigPublisher(
            repository=self._repository
        )
        self._audit_writer = audit_writer
        self._bootstrap_service_factory = bootstrap_service_factory
        self._setup_token_service_factory = setup_token_service_factory

    def recover(
        self,
        session: Session,
        payload: dict[str, Any],
        *,
        setup_token: SetupTokenContext | None,
    ) -> SetupInitializationResult:
        config = dict(payload["config"])
        config_version_id = uuid.uuid4()
        config_version = self._repository.next_config_version(session)
        config["config_version"] = config_version
        config_hash = stable_json_hash(config)
        enterprise_id, admin_user_id = self._repository.load_recovery_subjects(session)
        bootstrap_result = self._bootstrap_service_factory().bootstrap(session, config=config)
        if not bootstrap_result.ready:
            raise SetupInitializationError(
                "SETUP_BOOTSTRAP_FAILED",
                "service bootstrap checks failed",
                status_code=503,
                details={"checks": [check.to_dict() for check in bootstrap_result.checks]},
            )

        self._audit_writer.write(
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
        self._repository.mark_status(session, SetupStatus.RECOVERY_PUBLISHING_CONFIG)
        self._config_publisher.archive_active_config(session)
        self._config_publisher.insert_active_config_version(
            session,
            config_version_id,
            config_version,
            config_hash,
            int(config["schema_version"]),
        )
        self._config_publisher.insert_system_configs(
            session,
            config_version_id,
            config_version,
            config,
            config_hash,
        )
        self._config_publisher.mark_initialized(session, config_version)
        self._config_publisher.clear_recovery_setup(session)
        self._bootstrap_service_factory().persist_result(session, bootstrap_result)
        if setup_token is not None:
            self._setup_token_service_factory().consume(session, setup_token)
            self._audit_writer.write(
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
        self._audit_writer.write(
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
