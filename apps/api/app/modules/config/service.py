"""Config Service facade.

业务模块仍通过 ConfigService 访问配置能力；具体职责已拆分到：
reader、repository、dependency_validator、version_service、publisher。
"""

from __future__ import annotations

from typing import Any

from app.db.session import session_scope
from app.modules.config.cache import ConfigCache
from app.modules.config.config_read_repository import ConfigReadRepository
from app.modules.config.config_state_repository import ConfigStateRepository
from app.modules.config.config_version_repository import ConfigVersionRepository
from app.modules.config.config_write_repository import ConfigWriteRepository
from app.modules.config.constants import (
    CONFIG_METADATA_KEYS,
    GLOBAL_CONFIG_CACHE,
    HIGH_RISK_CONFIG_KEYS,
    MEDIUM_RISK_CONFIG_KEYS,
)
from app.modules.config.dependency_validator import ConfigDependencyValidator
from app.modules.config.publisher import ConfigPublisher
from app.modules.config.reader import ConfigReader
from app.modules.config.schemas import (
    ActiveConfigSnapshot,
    ConfigItem,
    ConfigItemList,
    ConfigValidationResult,
    ConfigVersion,
    ConfigVersionList,
)
from app.modules.config.version_service import ConfigVersionService
from sqlalchemy.orm import Session


class ConfigService:
    """Config facade preserving the public service API."""

    def __init__(self, *, cache: ConfigCache | None = None) -> None:
        self.cache = cache or GLOBAL_CONFIG_CACHE
        self.read_repository = ConfigReadRepository()
        self.state_repository = ConfigStateRepository()
        self.version_repository = ConfigVersionRepository()
        self.write_repository = ConfigWriteRepository()
        self.reader = ConfigReader(
            read_repository=self.read_repository,
            state_repository=self.state_repository,
        )
        self.dependency_validator = ConfigDependencyValidator()
        self.version_service = ConfigVersionService(
            read_repository=self.read_repository,
            version_repository=self.version_repository,
            write_repository=self.write_repository,
            reader=self.reader,
            dependency_validator=self.dependency_validator,
            validate_config_and_dependencies=(
                lambda session, **kwargs: self._validate_config_and_dependencies(
                    session,
                    **kwargs,
                )
            ),
            invalidate_cache=self.invalidate_cache,
        )
        self.publisher = ConfigPublisher(
            state_repository=self.state_repository,
            version_repository=self.version_repository,
            write_repository=self.write_repository,
            reader=self.reader,
            dependency_validator=self.dependency_validator,
            validate_config_and_dependencies=(
                lambda session, **kwargs: self._validate_config_and_dependencies(
                    session,
                    **kwargs,
                )
            ),
            get_config_version=lambda session, version: self.get_config_version(session, version),
            invalidate_cache=self.invalidate_cache,
        )

    def get_active_config(self, *, force_refresh: bool = False) -> ActiveConfigSnapshot:
        if not force_refresh:
            cached = self.cache.get()
            if cached is not None:
                return cached

        with session_scope() as session:
            snapshot = self.load_active_config(session)
        self.cache.set(snapshot)
        return snapshot

    def refresh_active_config(self) -> ActiveConfigSnapshot:
        return self.get_active_config(force_refresh=True)

    def invalidate_cache(self) -> None:
        self.cache.invalidate()

    def get_section(self, name: str, *, force_refresh: bool = False) -> dict[str, Any]:
        return self.get_active_config(force_refresh=force_refresh).section(name)

    def load_active_config(
        self,
        session: Session,
        *,
        active_config_version: int | None = None,
        validate_schema: bool = True,
    ) -> ActiveConfigSnapshot:
        return self.reader.load_active_config(
            session,
            active_config_version=active_config_version,
            validate_schema=validate_schema,
        )

    def validate_active_config(self, config: dict[str, Any]) -> None:
        self.reader.validate_active_config(config)

    def list_config_items(self, session: Session, *, page: int, page_size: int) -> ConfigItemList:
        return self.version_service.list_config_items(session, page=page, page_size=page_size)

    def get_config_item(self, session: Session, key: str) -> ConfigItem:
        return self.version_service.get_config_item(session, key)

    def save_config_draft(
        self,
        session: Session,
        *,
        key: str,
        value_json: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigItem:
        return self.version_service.save_config_draft(
            session,
            key=key,
            value_json=value_json,
            actor_user_id=actor_user_id,
        )

    def list_config_versions(
        self,
        session: Session,
        *,
        page: int,
        page_size: int,
    ) -> ConfigVersionList:
        return self.version_service.list_config_versions(
            session,
            page=page,
            page_size=page_size,
        )

    def get_config_version(self, session: Session, version: int) -> ConfigVersion:
        return self.version_service.get_config_version(session, version)

    def create_config_version(
        self,
        session: Session,
        *,
        config: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigVersion:
        return self.version_service.create_config_version(
            session,
            config=config,
            actor_user_id=actor_user_id,
        )

    def update_config_version(
        self,
        session: Session,
        *,
        version: int,
        config: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigVersion:
        return self.version_service.update_config_version(
            session,
            version=version,
            config=config,
            actor_user_id=actor_user_id,
        )

    def validate_config_payload(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> ConfigValidationResult:
        validation, _bootstrap_result = self._validate_config_and_dependencies(
            session,
            config=config,
        )
        return validation

    def _validate_config_and_dependencies(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> tuple[ConfigValidationResult, Any | None]:
        return self.dependency_validator.validate_config_and_dependencies(
            session,
            config=config,
        )

    def publish_config_version(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        return self.publisher.publish_config_version(
            session,
            version=version,
            actor_user_id=actor_user_id,
        )

    def archive_config_version(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        return self.version_service.archive_config_version(
            session,
            version=version,
            actor_user_id=actor_user_id,
        )

    def discard_config_draft(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        return self.version_service.discard_config_draft(
            session,
            version=version,
            actor_user_id=actor_user_id,
        )


__all__ = [
    "CONFIG_METADATA_KEYS",
    "GLOBAL_CONFIG_CACHE",
    "HIGH_RISK_CONFIG_KEYS",
    "MEDIUM_RISK_CONFIG_KEYS",
    "ConfigService",
]
