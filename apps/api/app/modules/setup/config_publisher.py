"""Setup active configuration publishing."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.modules.setup.repository import SetupInitializationRepository
from sqlalchemy.orm import Session


class SetupConfigPublisher:
    """Write and publish the active setup configuration bundle."""

    def __init__(self, *, repository: SetupInitializationRepository | None = None) -> None:
        self._repository = repository or SetupInitializationRepository()

    def archive_active_config(self, session: Session) -> None:
        self._repository.archive_active_config(session)

    def insert_active_config_version(
        self,
        session: Session,
        config_version_id: UUID,
        config_version: int,
        config_hash: str,
        schema_version: int,
    ) -> None:
        self._repository.insert_active_config_version(
            session,
            config_version_id,
            config_version,
            config_hash,
            schema_version,
        )

    def insert_system_configs(
        self,
        session: Session,
        config_version_id: UUID,
        config_version: int,
        config: dict[str, Any],
        config_hash: str,
    ) -> None:
        self._repository.insert_system_configs(
            session,
            config_version_id,
            config_version,
            config,
            config_hash,
        )

    def mark_initialized(self, session: Session, config_version: int) -> None:
        self._repository.mark_initialized(session, config_version)

    def clear_recovery_setup(self, session: Session) -> None:
        self._repository.clear_recovery_setup(session)
