"""导入任务 API。"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, Query, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse

from app.api.schemas.config import PaginationData
from app.api.schemas.import_pipeline import (
    DocumentImportRequest,
    ImportJobData,
    ImportJobListResponse,
    ImportJobPatchRequest,
    ImportJobResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import (
    DocumentImportItem,
    ImportActorContext,
    ImportJob,
)
from app.modules.import_pipeline.service import ImportService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["import"])
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


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
    service = ImportService()
    try:
        upload_items = await _upload_items(files)
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:import")
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
    service = ImportService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="document:import")
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


@router.get("/admin/import-jobs", response_model=ImportJobListResponse)
async def admin_list_import_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    stage: str | None = Query(default=None),
    kb_id: str | None = Query(default=None),
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
        data=[_job_data(job) for job in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
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


def _authenticate(session: object, token: str | None, *, required_scope: str) -> AuthContext:
    return AuthService().authenticate_access_token(
        session,
        access_token=token or "",
        required_scope=required_scope,
    )


def _actor_context(auth_context: AuthContext) -> ImportActorContext:
    knowledge_base_ids = tuple(
        role.scope_id
        for role in auth_context.user.roles
        if role.scope_type == "knowledge_base" and role.scope_id
    )
    can_import_all_knowledge_bases = any(
        role.scope_type == "enterprise"
        and any(
            scope in {"*", "knowledge_base:*", "document:*", "document:import"}
            for scope in role.scopes
        )
        for role in auth_context.user.roles
    )
    return ImportActorContext(
        user_id=auth_context.user.id,
        scopes=auth_context.user.scopes,
        department_ids=tuple(department.id for department in auth_context.user.departments),
        knowledge_base_ids=knowledge_base_ids,
        can_import_all_knowledge_bases=can_import_all_knowledge_bases,
    )


def _job_data(job: ImportJob) -> ImportJobData:
    return ImportJobData(
        id=job.id,
        kb_id=job.kb_id,
        status=job.status,
        stage=job.stage,
        document_ids=list(job.document_ids),
        error_summary=job.error_summary,
    )


async def _upload_items(files: list[UploadFile]) -> list[DocumentImportItem]:
    if not files:
        raise ImportServiceError(
            "IMPORT_FILES_REQUIRED",
            "upload import requires at least one file",
            status_code=400,
        )
    items: list[DocumentImportItem] = []
    for index, upload in enumerate(files):
        content = await upload.read()
        if not content:
            raise ImportServiceError(
                "IMPORT_FILE_EMPTY",
                "uploaded file is empty",
                status_code=400,
                details={"file_index": index, "filename": upload.filename},
            )
        if len(content) > MAX_UPLOAD_BYTES:
            raise ImportServiceError(
                "IMPORT_FILE_TOO_LARGE",
                "uploaded file is too large for P0 inline import",
                status_code=413,
                details={
                    "file_index": index,
                    "filename": upload.filename,
                    "max_bytes": MAX_UPLOAD_BYTES,
                    "size_bytes": len(content),
                },
            )
        filename = upload.filename or f"document-{index + 1}.txt"
        text_content = content.decode("utf-8", errors="replace")
        items.append(
            DocumentImportItem(
                title=filename,
                metadata={
                    "filename": filename,
                    "content_type": upload.content_type,
                    "size_bytes": len(content),
                    "content": text_content,
                },
            )
        )
    return items


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _request_id() -> str:
    request_context = get_request_context()
    return request_context.request_id if request_context else "req_unknown"


def _auth_error_response(exc: AuthServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _import_error_response(exc: ImportServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _database_error_response(exc: SQLAlchemyError, *, stage: str) -> JSONResponse:
    original = getattr(exc, "orig", None) or exc.__cause__
    return JSONResponse(
        status_code=500,
        content={
            "request_id": _request_id(),
            "error_code": "IMPORT_DATABASE_ERROR",
            "message": "import database operation failed",
            "stage": stage,
            "retryable": True,
            "details": {
                "database_error": {
                    "type": exc.__class__.__name__,
                    "driver": original.__class__.__name__ if original is not None else None,
                }
            },
        },
    )
