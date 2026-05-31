"""Config version and draft management."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from typing import Any

from app.modules.config.config_read_repository import ConfigReadRepository
from app.modules.config.config_version_repository import ConfigVersionRepository
from app.modules.config.config_write_repository import ConfigWriteRepository
from app.modules.config.dependency_validator import ConfigDependencyValidator
from app.modules.config.errors import ConfigServiceError
from app.modules.config.reader import ConfigReader
from app.modules.config.schemas import (
    ConfigItem,
    ConfigItemList,
    ConfigValidationResult,
    ConfigVersion,
    ConfigVersionList,
)
from app.modules.config.utils import (
    changed_config_keys,
    config_version_from_mapping,
    is_editable_config_section,
    normalized_config_for_version,
    parse_config_value,
    risk_level_for_config_change,
    risk_level_for_key,
    status_after_config_update,
    write_config_audit,
)
from app.shared.json_utils import stable_json_hash
from sqlalchemy.orm import Session


class ConfigVersionService:
    """Handles editable config sections and config version records."""

    def __init__(
        self,
        *,
        read_repository: ConfigReadRepository,
        version_repository: ConfigVersionRepository,
        write_repository: ConfigWriteRepository,
        reader: ConfigReader,
        dependency_validator: ConfigDependencyValidator,
        validate_config_and_dependencies: Callable[..., tuple[ConfigValidationResult, Any | None]],
        invalidate_cache: Callable[[], None],
    ) -> None:
        self.read_repository = read_repository
        self.version_repository = version_repository
        self.write_repository = write_repository
        self.reader = reader
        self.dependency_validator = dependency_validator
        self._validate_config_and_dependencies = validate_config_and_dependencies
        self._invalidate_cache = invalidate_cache

    def list_config_items(self, session: Session, *, page: int, page_size: int) -> ConfigItemList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        snapshot = self.reader.load_active_config(session)
        active_items = [
            ConfigItem(
                key=key,
                value_json=copy.deepcopy(value),
                scope_type=snapshot.scope_type,
                status="active",
                version=snapshot.version,
            )
            for key, value in sorted(snapshot.config.items())
            if is_editable_config_section(key, value)
        ]
        draft_items: list[ConfigItem] = []
        for draft in self.read_repository.list_draft_config_payloads(session):
            draft_config = parse_config_value(draft["value_json"], version=int(draft["version"]))
            for key, value in sorted(draft_config.items()):
                if not is_editable_config_section(key, value):
                    continue
                if snapshot.config.get(key) == value:
                    continue
                draft_items.append(
                    ConfigItem(
                        key=key,
                        value_json=copy.deepcopy(value),
                        scope_type=str(draft["scope_type"]),
                        status=str(draft["status"]),
                        version=int(draft["version"]),
                    )
                )
        items = active_items + draft_items
        return ConfigItemList(
            items=items[(page - 1) * page_size : page * page_size],
            total=len(items),
        )

    def get_config_item(self, session: Session, key: str) -> ConfigItem:
        snapshot = self.reader.load_active_config(session)
        value = snapshot.config.get(key)
        if not is_editable_config_section(key, value):
            raise ConfigServiceError(
                "CONFIG_KEY_NOT_FOUND",
                "config key is not an editable active_config section",
                details={"key": key},
            )
        return ConfigItem(
            key=key,
            value_json=copy.deepcopy(value),
            scope_type=snapshot.scope_type,
            status="active",
            version=snapshot.version,
        )

    def save_config_draft(
        self,
        session: Session,
        *,
        key: str,
        value_json: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigItem:
        snapshot = self.reader.load_active_config(session)
        active_config = snapshot.config
        current_value = active_config.get(key)
        if not is_editable_config_section(key, current_value):
            raise ConfigServiceError(
                "CONFIG_KEY_NOT_FOUND",
                "config key is not an editable active_config section",
                details={"key": key},
            )
        if current_value == value_json:
            return ConfigItem(
                key=key,
                value_json=copy.deepcopy(current_value),
                scope_type=snapshot.scope_type,
                status="active",
                version=snapshot.version,
            )

        existing_draft = self.read_repository.load_draft_by_section(session, key, value_json)
        if existing_draft is not None:
            return existing_draft

        config = copy.deepcopy(active_config)
        version = self.version_repository.next_config_version(session)
        config["config_version"] = version
        config[key] = copy.deepcopy(value_json)
        self.reader.validate_active_config(config)

        config_hash = stable_json_hash(config)
        existing = self.read_repository.load_config_by_hash(session, config_hash)
        if existing is not None:
            return ConfigItem(
                key=key,
                value_json=copy.deepcopy(existing["config"][key]),
                scope_type=str(existing["scope_type"]),
                status=str(existing["status"]),
                version=int(existing["version"]),
            )

        risk_level = risk_level_for_key(key)
        config_version_id = uuid.uuid4()
        self.write_repository.insert_config_version(
            session,
            config_version_id=config_version_id,
            version=version,
            status="draft",
            config_hash=config_hash,
            schema_version=int(config["schema_version"]),
            risk_level=risk_level,
            created_by=actor_user_id,
            validation_result={"valid": True, "stage": "schema"},
        )
        self.write_repository.insert_system_config(
            session,
            config_version_id=config_version_id,
            version=version,
            status="draft",
            config=config,
            config_hash=config_hash,
        )
        write_config_audit(
            session,
            event_name="config.draft_saved",
            action="save_draft",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level=risk_level,
            config_version=version,
            summary={"key": key, "config_hash": config_hash, "risk_level": risk_level},
        )
        return ConfigItem(
            key=key,
            value_json=copy.deepcopy(value_json),
            scope_type=snapshot.scope_type,
            status="draft",
            version=version,
        )

    def list_config_versions(
        self,
        session: Session,
        *,
        page: int,
        page_size: int,
    ) -> ConfigVersionList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        total = self.version_repository.count_config_versions(session)
        rows = self.version_repository.list_config_version_rows(
            session,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return ConfigVersionList(
            items=[config_version_from_mapping(row) for row in rows],
            total=total,
        )

    def get_config_version(self, session: Session, version: int) -> ConfigVersion:
        row = self.version_repository.load_config_version_payload_row(session, version)
        return config_version_from_mapping(row)

    def create_config_version(
        self,
        session: Session,
        *,
        config: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigVersion:
        snapshot = self.reader.load_active_config(session, validate_schema=False)
        version = self.version_repository.next_config_version(session)
        normalized = normalized_config_for_version(config, version=version)
        self.reader.validate_active_config(normalized)
        config_hash = stable_json_hash(normalized)
        existing = self.read_repository.load_config_by_hash(session, config_hash)
        if existing is not None:
            return self.get_config_version(session, int(existing["version"]))

        risk_level = risk_level_for_config_change(snapshot.config, normalized)
        config_version_id = uuid.uuid4()
        self.write_repository.insert_config_version(
            session,
            config_version_id=config_version_id,
            version=version,
            status="draft",
            config_hash=config_hash,
            schema_version=int(normalized["schema_version"]),
            risk_level=risk_level,
            created_by=actor_user_id,
            validation_result={"valid": True, "stage": "schema"},
        )
        self.write_repository.insert_system_config(
            session,
            config_version_id=config_version_id,
            version=version,
            status="draft",
            config=normalized,
            config_hash=config_hash,
        )
        write_config_audit(
            session,
            event_name="config.version_created",
            action="create_version",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level=risk_level,
            config_version=version,
            summary={
                "config_hash": config_hash,
                "risk_level": risk_level,
                "changed_keys": changed_config_keys(snapshot.config, normalized),
            },
        )
        return self.get_config_version(session, version)

    def update_config_version(
        self,
        session: Session,
        *,
        version: int,
        config: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigVersion:
        row = self.version_repository.load_config_version_payload_row(
            session,
            version,
            for_update=True,
        )
        status = str(row["status"])
        if status not in {"draft", "validating", "failed", "inactive", "active"}:
            raise ConfigServiceError(
                "CONFIG_VERSION_NOT_EDITABLE",
                "only non-archived config versions can be edited",
                details={"version": version, "status": status},
            )

        active_snapshot = self.reader.load_active_config(session, validate_schema=False)
        normalized = normalized_config_for_version(config, version=version)
        if status == "active":
            validation, bootstrap_result = self._validate_config_and_dependencies(
                session,
                config=normalized,
            )
            if not validation.valid:
                raise ConfigServiceError(
                    "CONFIG_DEPENDENCY_FAILED",
                    "active config dependency validation failed",
                    retryable=True,
                    details={
                        "valid": validation.valid,
                        "errors": validation.errors,
                        "warnings": validation.warnings,
                    },
                )
            validation_result: dict[str, object] = {
                "valid": validation.valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            }
        else:
            self.reader.validate_active_config(normalized)
            bootstrap_result = None
            validation_result = {"valid": True, "stage": "schema"}
        config_hash = stable_json_hash(normalized)
        existing = self.read_repository.load_config_by_hash(session, config_hash)
        if existing is not None and int(existing["version"]) != version:
            raise ConfigServiceError(
                "CONFIG_VERSION_DUPLICATED",
                "another config version already has the same content",
                details={"version": version, "existing_version": int(existing["version"])},
            )

        risk_level = risk_level_for_config_change(active_snapshot.config, normalized)
        next_status = status_after_config_update(status)
        self.write_repository.update_config_version_payload(
            session,
            version=version,
            status=next_status,
            config=normalized,
            config_hash=config_hash,
            schema_version=int(normalized["schema_version"]),
            risk_level=risk_level,
            validation_result=validation_result,
        )
        if status == "active":
            self.dependency_validator.persist_bootstrap_state(
                session,
                bootstrap_result=bootstrap_result,
            )
            self._invalidate_cache()
        write_config_audit(
            session,
            event_name="config.version_updated",
            action="update_version",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level=risk_level,
            config_version=version,
            summary={
                "config_hash": config_hash,
                "risk_level": risk_level,
                "changed_keys": changed_config_keys(active_snapshot.config, normalized),
            },
        )
        return self.get_config_version(session, version)

    def archive_config_version(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        row = self.version_repository.load_config_version_row(session, version, for_update=True)
        status = str(row["status"])
        if status not in {"draft", "validating", "failed", "inactive"}:
            raise ConfigServiceError(
                "CONFIG_VERSION_NOT_DISCARDABLE",
                "only inactive or non-active draft-like config versions can be archived",
                details={"version": version, "status": status},
            )

        self.write_repository.mark_version_status(session, version, "archived")
        self.write_repository.mark_system_config_status(session, version, "archived")
        write_config_audit(
            session,
            event_name="config.archived",
            action="archive",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level=str(row["risk_level"]),
            config_version=version,
            summary={
                "config_hash": row["config_hash"],
                "risk_level": row["risk_level"],
            },
        )
        return self.get_config_version(session, version)

    def discard_config_draft(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        return self.archive_config_version(
            session,
            version=version,
            actor_user_id=actor_user_id,
        )
