"""Config repository compatibility facade."""

from __future__ import annotations

from app.modules.config.config_read_repository import ConfigReadRepository
from app.modules.config.config_state_repository import ConfigStateRepository
from app.modules.config.config_version_repository import ConfigVersionRepository
from app.modules.config.config_write_repository import ConfigWriteRepository


class ConfigRepository(
    ConfigStateRepository,
    ConfigReadRepository,
    ConfigVersionRepository,
    ConfigWriteRepository,
):
    """Backward-compatible aggregate repository.

    New code should depend on the narrower repositories directly.
    """
