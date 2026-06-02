"""导入任务 API 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import import_admin, import_user

router = APIRouter()
router.include_router(import_user.router)
router.include_router(import_admin.router)
