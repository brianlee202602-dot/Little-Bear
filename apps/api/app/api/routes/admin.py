"""管理后台 API 聚合路由。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    admin_departments,
    admin_documents,
    admin_index_ops,
    admin_knowledge,
    admin_roles,
    admin_users,
)
from app.api.routes.admin_shared import (
    AdminService,
    _object_storage_or_none,
    build_index_ops_service,
    session_scope,
)

router = APIRouter()
router.include_router(admin_users.router)
router.include_router(admin_departments.router)
router.include_router(admin_knowledge.router)
router.include_router(admin_documents.router)
router.include_router(admin_index_ops.router)
router.include_router(admin_roles.router)

__all__ = [
    "AdminService",
    "_object_storage_or_none",
    "build_index_ops_service",
    "router",
    "session_scope",
]
