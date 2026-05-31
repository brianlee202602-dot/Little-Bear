"""管理端导入与索引任务路由。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse

from app.api.routes.import_shared import (
    _auth_error_response,
    _authenticate,
    _database_error_response,
    _extract_bearer_token,
    _import_error_response,
    _job_data,
    _job_list_item_data,
    _request_id,
)
from app.api.schemas.common import PaginationData
from app.api.schemas.import_pipeline import (
    ImportJobListResponse,
    ImportJobResponse,
    IndexJobRetryRequest,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.service import ImportService

router = APIRouter(prefix="/internal/v1", tags=["import"])


@router.get("/admin/import-jobs", response_model=ImportJobListResponse)
async def admin_list_import_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    stage: str | None = Query(default=None),
    kb_id: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> ImportJobListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ImportService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="import_job:read")
            result = service.list_import_jobs(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                status=status_filter,
                stage=stage,
                kb_id=kb_id,
                job_type=job_type,
                owner_only=False,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_import_job_list")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="admin_import_job_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_import_job_list")
    return ImportJobListResponse(
        request_id=_request_id(),
        data=[_job_list_item_data(job) for job in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
    )


@router.post(
    "/admin/index-jobs/retries",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportJobListResponse,
)
async def admin_retry_index_jobs(
    payload: IndexJobRetryRequest,
    authorization: str | None = Header(default=None),
    x_index_confirm: str | None = Header(default=None),
) -> ImportJobListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ImportService()
    try:
        if x_index_confirm != "retry":
            raise ImportServiceError(
                "IMPORT_CONFIRMATION_REQUIRED",
                "index job retry requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: retry"},
            )
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:index")
            result = service.create_index_job_retries(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                job_ids=payload.job_ids,
                owner_only=False,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_index_job_retry")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="admin_index_job_retry")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_index_job_retry")
    return ImportJobListResponse(
        request_id=_request_id(),
        data=[_job_list_item_data(job) for job in result.items],
        pagination=PaginationData(page=1, page_size=len(result.items), total=result.total),
    )


@router.get("/admin/import-jobs/{job_id}", response_model=ImportJobResponse)
async def admin_get_import_job(
    job_id: str,
    authorization: str | None = Header(default=None),
) -> ImportJobResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ImportService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="import_job:read")
            job = service.get_import_job(
                session,
                job_id,
                enterprise_id=auth_context.user.enterprise_id,
                owner_only=False,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="admin_import_job_get")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="admin_import_job_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="admin_import_job_get")
    return ImportJobResponse(request_id=_request_id(), data=_job_data(job))

