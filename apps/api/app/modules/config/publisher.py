"""Config version publisher."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.modules.config.config_state_repository import ConfigStateRepository
from app.modules.config.config_version_repository import ConfigVersionRepository
from app.modules.config.config_write_repository import ConfigWriteRepository
from app.modules.config.dependency_validator import ConfigDependencyValidator
from app.modules.config.errors import ConfigServiceError
from app.modules.config.reader import ConfigReader
from app.modules.config.schemas import ConfigValidationResult, ConfigVersion
from app.modules.config.utils import parse_config_value, write_config_audit
from sqlalchemy.orm import Session


class ConfigPublisher:
    """Validates dependencies and atomically switches active config version."""

    def __init__(
        self,
        *,
        state_repository: ConfigStateRepository,
        version_repository: ConfigVersionRepository,
        write_repository: ConfigWriteRepository,
        reader: ConfigReader,
        dependency_validator: ConfigDependencyValidator,
        validate_config_and_dependencies: Callable[..., tuple[ConfigValidationResult, Any | None]],
        get_config_version: Callable[[Session, int], ConfigVersion],
        invalidate_cache: Callable[[], None],
    ) -> None:
        self.state_repository = state_repository
        self.version_repository = version_repository
        self.write_repository = write_repository
        self.reader = reader
        self.dependency_validator = dependency_validator
        self._validate_config_and_dependencies = validate_config_and_dependencies
        self._get_config_version = get_config_version
        self._invalidate_cache = invalidate_cache

    def publish_config_version(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        row = self.version_repository.load_config_version_row(session, version, for_update=True)
        status = str(row["status"])
        if status == "active":
            return self._get_config_version(session, version)
        if status not in {"draft", "validating", "inactive", "failed"}:
            raise ConfigServiceError(
                "CONFIG_VERSION_NOT_PUBLISHABLE",
                "only draft, validating, failed or inactive config versions can be activated",
                details={"version": version, "status": status},
            )

        config_row = self.version_repository.load_config_payload_row(
            session,
            version,
            for_update=True,
        )
        config = parse_config_value(config_row["value_json"], version=version)
        self.reader.validate_metadata(
            {
                **row,
                "config_version": row["version"],
                "value_hash": config_row["value_hash"],
                "system_config_version": config_row["version"],
                "system_config_status": config_row["system_config_status"],
            },
            config,
            version,
        )

        self.write_repository.mark_version_status(session, version, "validating")
        validation, bootstrap_result = self._validate_config_and_dependencies(
            session,
            config=config,
        )
        validation_payload = {
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }
        if not validation.valid:
            self.write_repository.mark_version_status(
                session,
                version,
                "failed",
                validation_result=validation_payload,
            )
            write_config_audit(
                session,
                event_name="config.publish_failed",
                action="publish",
                result="failure",
                actor_id=actor_user_id,
                resource_id=str(version),
                risk_level="critical",
                config_version=version,
                summary={
                    "config_hash": row["config_hash"],
                    "previous_active_version": (
                        self.state_repository.load_active_config_version(session)
                    ),
                    "active_pointer_unchanged": True,
                },
                error_code="CONFIG_DEPENDENCY_FAILED",
            )
            raise ConfigServiceError(
                "CONFIG_DEPENDENCY_FAILED",
                "config dependency validation failed",
                retryable=True,
                details=validation_payload,
            )

        previous_active_version = self.state_repository.load_active_config_version(session)
        self.write_repository.deactivate_active_config(session)
        self.write_repository.mark_version_status(
            session,
            version,
            "active",
            validation_result=validation_payload,
            activated=True,
        )
        self.write_repository.mark_system_config_status(session, version, "active")
        self.state_repository.set_active_config_version(
            session,
            version,
            actor_user_id=actor_user_id,
        )
        self.dependency_validator.persist_bootstrap_state(
            session,
            bootstrap_result=bootstrap_result,
        )
        self._invalidate_cache()
        write_config_audit(
            session,
            event_name="config.published",
            action="publish",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level="critical",
            config_version=version,
            summary={
                "config_hash": row["config_hash"],
                "previous_active_version": previous_active_version,
                "risk_level": row["risk_level"],
            },
        )
        return self._get_config_version(session, version)
