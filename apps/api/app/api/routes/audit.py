"""Audit Admin API。

审计日志属于只读事实源，接口只返回已经脱敏的 `audit_logs.summary_json`，不读取
Secret Store，也不拼接业务对象明细。
"""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.dependencies.auth import (
    authenticate_required_scope as _authenticate,
)
from app.api.dependencies.auth import (
    current_request_id as _request_id,
)
from app.api.dependencies.auth import (
    extract_bearer_token as _extract_bearer_token,
)
from app.api.errors import database_error_response, service_error_response
from app.api.presenters.audit import (
    audit_log_data as _audit_log_data,
)
from app.api.presenters.audit import (
    audit_log_list_item_data as _audit_log_list_item_data,
)
from app.api.presenters.audit import (
    model_call_log_data as _model_call_log_data,
)
from app.api.presenters.audit import (
    model_call_log_list_item_data as _model_call_log_list_item_data,
)
from app.api.presenters.audit import (
    query_log_data as _query_log_data,
)
from app.api.presenters.audit import (
    query_log_list_item_data as _query_log_list_item_data,
)
from app.api.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    ModelCallLogListResponse,
    ModelCallLogResponse,
    QueryLogListResponse,
    QueryLogResponse,
)
from app.api.schemas.common import PaginationData
from app.db.session import session_scope
from app.modules.audit.errors import AuditServiceError
from app.modules.audit.service import AuditService
from app.modules.auth.errors import AuthServiceError

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-audit"])

_auth_error_response = service_error_response
_audit_error_response = service_error_response
_database_error_response = partial(
    database_error_response,
    error_code="AUDIT_DATABASE_ERROR",
    message="audit database operation failed",
)


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    result: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> AuditLogListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuditService()
    try:
        with session_scope() as session:
            _authenticate(session, token, required_scope="audit:read")
            log_list = service.list_audit_logs(
                session,
                page=page,
                page_size=page_size,
                filters={
                    "actor_id": actor_id,
                    "action": action,
                    "resource_type": resource_type,
                    "result": result,
                    "risk_level": risk_level,
                },
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="audit_log_list")
    except AuditServiceError as exc:
        return _audit_error_response(exc, stage="audit_log_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="audit_log_list")

    return AuditLogListResponse(
        request_id=_request_id(),
        data=[_audit_log_list_item_data(log) for log in log_list.items],
        pagination=PaginationData(page=page, page_size=page_size, total=log_list.total),
    )


@router.get("/audit-logs/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: str,
    authorization: str | None = Header(default=None),
) -> AuditLogResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuditService()
    try:
        with session_scope() as session:
            _authenticate(session, token, required_scope="audit:read")
            log = service.get_audit_log(session, audit_id)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="audit_log_get")
    except AuditServiceError as exc:
        return _audit_error_response(exc, stage="audit_log_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="audit_log_get")

    return AuditLogResponse(request_id=_request_id(), data=_audit_log_data(log))


@router.get("/query-logs", response_model=QueryLogListResponse)
async def list_query_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: str | None = Query(default=None),
    kb_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    query_scope_mode: str | None = Query(default=None),
    degraded: bool | None = Query(default=None),
    degrade_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    error_code: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> QueryLogListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuditService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="audit:read")
            log_list = service.list_query_logs(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                filters={
                    "user_id": user_id,
                    "kb_id": kb_id,
                    "status": status,
                    "query_scope_mode": query_scope_mode,
                    "degraded": degraded,
                    "degrade_reason": degrade_reason,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "error_code": error_code,
                },
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_log_list")
    except AuditServiceError as exc:
        return _audit_error_response(exc, stage="query_log_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_log_list")

    return QueryLogListResponse(
        request_id=_request_id(),
        data=[_query_log_list_item_data(log) for log in log_list.items],
        pagination=PaginationData(page=page, page_size=page_size, total=log_list.total),
    )


@router.get("/query-logs/{query_log_id}", response_model=QueryLogResponse)
async def get_query_log(
    query_log_id: str,
    authorization: str | None = Header(default=None),
) -> QueryLogResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuditService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="audit:read")
            log = service.get_query_log(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                query_log_id=query_log_id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_log_get")
    except AuditServiceError as exc:
        return _audit_error_response(exc, stage="query_log_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_log_get")

    return QueryLogResponse(request_id=_request_id(), data=_query_log_data(log))


@router.get("/model-call-logs", response_model=ModelCallLogListResponse)
async def list_model_call_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    model: str | None = Query(default=None),
    model_type: str | None = Query(default=None),
    caller: str | None = Query(default=None),
    status: str | None = Query(default=None),
    degraded: bool | None = Query(default=None),
    request_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    error_code: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> ModelCallLogListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuditService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="audit:read")
            log_list = service.list_model_call_logs(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                filters={
                    "model": model,
                    "model_type": model_type,
                    "caller": caller,
                    "status": status,
                    "degraded": degraded,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "error_code": error_code,
                },
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="model_call_log_list")
    except AuditServiceError as exc:
        return _audit_error_response(exc, stage="model_call_log_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="model_call_log_list")

    return ModelCallLogListResponse(
        request_id=_request_id(),
        data=[_model_call_log_list_item_data(log) for log in log_list.items],
        pagination=PaginationData(page=page, page_size=page_size, total=log_list.total),
    )


@router.get("/model-call-logs/{model_call_log_id}", response_model=ModelCallLogResponse)
async def get_model_call_log(
    model_call_log_id: str,
    authorization: str | None = Header(default=None),
) -> ModelCallLogResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuditService()
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="audit:read")
            log = service.get_model_call_log(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                model_call_log_id=model_call_log_id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="model_call_log_get")
    except AuditServiceError as exc:
        return _audit_error_response(exc, stage="model_call_log_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="model_call_log_get")

    return ModelCallLogResponse(request_id=_request_id(), data=_model_call_log_data(log))
