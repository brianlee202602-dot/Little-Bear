"""普通用户导入任务路由。"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse

from app.api.routes.import_shared import (
    _actor_context,
    _auth_error_response,
    _authenticate,
    _database_error_response,
    _extract_bearer_token,
    _import_error_response,
    _job_data,
    _request_id,
    _upload_items,
)
from app.api.schemas.import_pipeline import (
    DocumentImportRequest,
    ImportJobPatchRequest,
    ImportJobResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.runtime import build_import_service
from app.modules.import_pipeline.schemas import DocumentImportItem
from app.modules.import_pipeline.service import ImportService

router = APIRouter(prefix="/internal/v1", tags=["import"])


@router.post(
    "/knowledge-bases/{kb_id}/documents",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportJobResponse,
)
async def create_upload_document_import(
    kb_id: str,
    files: Annotated[list[UploadFile], File(...)],
    owner_department_id: Annotated[str | None, Form()] = None,
    visibility: Annotated[Literal["department", "enterprise"] | None, Form()] = None,
    folder_id: Annotated[str | None, Form()] = None,
    idempotency_key: Annotated[str | None, Form()] = None,
    authorization: str | None = Header(default=None),
) -> ImportJobResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:import")
            service = build_import_service(session)
        upload_items = await _upload_items(files, service=service)
        with session_scope() as session:
            job = service.create_document_import(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                actor_user_id=auth_context.user.id,
                job_type="upload",
                items=upload_items,
                owner_department_id=owner_department_id,
                visibility=visibility,
                folder_id=folder_id,
                idempotency_key=idempotency_key,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="upload_import_create")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="upload_import_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="upload_import_create")
    return ImportJobResponse(request_id=_request_id(), data=_job_data(job))


@router.post(
    "/knowledge-bases/{kb_id}/document-imports",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportJobResponse,
)
async def create_document_import(
    kb_id: str,
    payload: DocumentImportRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> ImportJobResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:import")
            service = build_import_service(session)
            job = service.create_document_import(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                kb_id=kb_id,
                actor_user_id=auth_context.user.id,
                job_type=payload.job_type,
                items=[
                    DocumentImportItem(
                        title=item.title,
                        url=item.url,
                        metadata=item.metadata,
                    )
                    for item in payload.items
                ],
                owner_department_id=payload.owner_department_id,
                visibility=payload.visibility,
                folder_id=payload.folder_id,
                idempotency_key=payload.idempotency_key or idempotency_key,
                actor_context=_actor_context(auth_context),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="import_create")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="import_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="import_create")
    return ImportJobResponse(request_id=_request_id(), data=_job_data(job))


@router.get("/import-jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: str,
    authorization: str | None = Header(default=None),
) -> ImportJobResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ImportService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="import_job:read:self")
            job = service.get_import_job(
                session,
                job_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                owner_only=True,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="import_job_get")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="import_job_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="import_job_get")
    return ImportJobResponse(request_id=_request_id(), data=_job_data(job))


@router.patch("/import-jobs/{job_id}", response_model=ImportJobResponse)
async def patch_import_job(
    job_id: str,
    payload: ImportJobPatchRequest,
    authorization: str | None = Header(default=None),
) -> ImportJobResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ImportService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="import_job:manage:self")
            if payload.status != "cancelled":
                raise ImportServiceError(
                    "IMPORT_PATCH_UNSUPPORTED",
                    "only cancellation is supported for import job patch",
                    status_code=400,
                )
            job = service.request_cancel(
                session,
                job_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                owner_only=True,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="import_job_patch")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="import_job_patch")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="import_job_patch")
    return ImportJobResponse(request_id=_request_id(), data=_job_data(job))


@router.post(
    "/import-jobs/{job_id}/retries",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportJobResponse,
)
async def create_import_job_retry(
    job_id: str,
    authorization: str | None = Header(default=None),
) -> ImportJobResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ImportService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="import_job:manage:self")
            job = service.create_retry(
                session,
                job_id,
                enterprise_id=auth_context.user.enterprise_id,
                actor_user_id=auth_context.user.id,
                owner_only=True,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="import_job_retry")
    except ImportServiceError as exc:
        return _import_error_response(exc, stage="import_job_retry")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="import_job_retry")
    return ImportJobResponse(request_id=_request_id(), data=_job_data(job))

