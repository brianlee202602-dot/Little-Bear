"""导入任务 API 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import import_admin, import_user
from app.api.routes.import_admin import (
    admin_get_import_job,
    admin_list_import_jobs,
    admin_retry_index_jobs,
)
from app.api.routes.import_shared import (
    _actor_context,
    _job_data,
    _job_list_item_data,
    _upload_items,
)
from app.api.routes.import_user import (
    create_document_import,
    create_import_job_retry,
    create_upload_document_import,
    get_import_job,
    patch_import_job,
)
from app.modules.import_pipeline.runtime import build_import_service
from app.modules.import_pipeline.service import ImportService

router = APIRouter()
router.include_router(import_user.router)
router.include_router(import_admin.router)

__all__ = [
    "ImportService",
    "_actor_context",
    "_job_data",
    "_job_list_item_data",
    "_upload_items",
    "admin_get_import_job",
    "admin_list_import_jobs",
    "admin_retry_index_jobs",
    "build_import_service",
    "create_document_import",
    "create_import_job_retry",
    "create_upload_document_import",
    "get_import_job",
    "patch_import_job",
    "router",
]

