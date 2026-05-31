"""Config active snapshot reader."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from app.modules.config.config_read_repository import ConfigReadRepository
from app.modules.config.config_state_repository import ConfigStateRepository
from app.modules.config.errors import ConfigServiceError
from app.modules.config.schemas import ActiveConfigSnapshot
from app.modules.config.utils import datetime_or_none, parse_config_value
from app.modules.config.validator import ConfigSchemaValidator
from app.shared.json_utils import stable_json_hash
from sqlalchemy.orm import Session


class ConfigReader:
    """Loads and validates active_config snapshots."""

    def __init__(
        self,
        *,
        read_repository: ConfigReadRepository | None = None,
        state_repository: ConfigStateRepository | None = None,
    ) -> None:
        self.read_repository = read_repository or ConfigReadRepository()
        self.state_repository = state_repository or ConfigStateRepository()

    def load_active_config(
        self,
        session: Session,
        *,
        active_config_version: int | None = None,
        validate_schema: bool = True,
    ) -> ActiveConfigSnapshot:
        version = active_config_version
        if version is None:
            version = self.state_repository.load_active_config_version(session)
        else:
            self.state_repository.assert_initialized(session)
        if version is None:
            raise ConfigServiceError(
                "CONFIG_ACTIVE_VERSION_MISSING",
                "system_state.active_config_version is missing",
                retryable=True,
            )

        row = self.read_repository.load_active_config_row(session, version)
        config = parse_config_value(row["value_json"], version=version)
        self.validate_metadata(row, config, version)
        if validate_schema:
            self.validate_active_config(config)

        return ActiveConfigSnapshot(
            version=version,
            schema_version=int(row["schema_version"]),
            scope_type=str(row["scope_type"]),
            scope_id=str(row["scope_id"]),
            config_hash=str(row["config_hash"]),
            value_hash=str(row["value_hash"]),
            config_version_id=str(row["config_version_id"]),
            loaded_at=datetime.now(UTC),
            activated_at=datetime_or_none(row.get("activated_at")),
            _config=copy.deepcopy(config),
        )

    def validate_active_config(self, config: dict[str, Any]) -> None:
        issues = ConfigSchemaValidator().validate_active_config(config)
        if issues:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_INVALID",
                "active config does not match ActiveConfigV1 schema",
                retryable=False,
                details={
                    "errors": [
                        {
                            "path": issue.path,
                            "message": issue.message,
                            "validator": issue.validator,
                        }
                        for issue in issues[:10]
                    ],
                    "error_count": len(issues),
                },
            )

    def validate_metadata(
        self,
        row: dict[str, Any],
        config: dict[str, Any],
        version: int,
    ) -> None:
        config_version = config.get("config_version")
        if config_version != version or row["config_version"] != version:
            raise ConfigServiceError(
                "CONFIG_VERSION_MISMATCH",
                "active config version does not match database version",
                details={
                    "expected_version": version,
                    "config_version": config_version,
                    "database_version": row["config_version"],
                },
            )

        schema_version = config.get("schema_version")
        if schema_version != row["schema_version"]:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_VERSION_MISMATCH",
                "active config schema version does not match database metadata",
                details={
                    "config_schema_version": schema_version,
                    "database_schema_version": row["schema_version"],
                },
            )

        scope = config.get("scope")
        scope_mismatched = (
            not isinstance(scope, dict)
            or scope.get("type") != row["scope_type"]
            or scope.get("id") != row["scope_id"]
        )
        if scope_mismatched:
            raise ConfigServiceError(
                "CONFIG_SCOPE_MISMATCH",
                "active config scope does not match database metadata",
                details={
                    "config_scope": scope,
                    "database_scope": {"type": row["scope_type"], "id": row["scope_id"]},
                },
            )

        config_hash = stable_json_hash(config)
        if config_hash != row["value_hash"] or config_hash != row["config_hash"]:
            raise ConfigServiceError(
                "CONFIG_HASH_MISMATCH",
                "active config hash does not match database metadata",
                retryable=True,
                details={
                    "computed_hash": config_hash,
                    "value_hash": row["value_hash"],
                    "config_hash": row["config_hash"],
                },
            )
