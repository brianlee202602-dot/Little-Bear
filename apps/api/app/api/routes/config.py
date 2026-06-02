"""配置管理 API 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import config_items, config_validations, config_versions

router = APIRouter()
router.include_router(config_items.router)
router.include_router(config_versions.router)
router.include_router(config_validations.router)
