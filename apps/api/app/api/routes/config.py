"""配置管理 API 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import config_items, config_validations, config_versions
from app.api.routes.config_items import get_config, list_configs, put_config
from app.api.routes.config_shared import (
    _authenticate_system_admin_config_manager,
    _item_data,
    _item_list_item_data,
    _validation_data,
    _version_data,
    _version_list_item_data,
)
from app.api.routes.config_validations import create_config_validation
from app.api.routes.config_versions import (
    create_config_version,
    delete_config_version,
    get_config_version,
    list_config_versions,
    patch_config_version,
    put_config_version,
)
from app.modules.auth.runtime import GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER
from app.modules.config.service import HIGH_RISK_CONFIG_KEYS, ConfigService

router = APIRouter()
router.include_router(config_items.router)
router.include_router(config_versions.router)
router.include_router(config_validations.router)

__all__ = [
    "ConfigService",
    "GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER",
    "HIGH_RISK_CONFIG_KEYS",
    "_authenticate_system_admin_config_manager",
    "_item_data",
    "_item_list_item_data",
    "_validation_data",
    "_version_data",
    "_version_list_item_data",
    "create_config_validation",
    "create_config_version",
    "delete_config_version",
    "get_config",
    "get_config_version",
    "list_config_versions",
    "list_configs",
    "patch_config_version",
    "put_config",
    "put_config_version",
    "router",
]

