"""Audit Admin API。

审计日志属于只读事实源，接口只返回已经脱敏的 `audit_logs.summary_json`，不读取
Secret Store，也不拼接业务对象明细。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.schemas.audit import (
    AuditLogData,
    AuditLogListResponse,
    AuditLogResponse,
    ModelCallLogData,
    ModelCallLogListResponse,
    QueryLogData,
    QueryLogListResponse,
    QueryLogResponse,
)
from app.api.schemas.config import PaginationData
from app.db.session import session_scope
from app.modules.audit.errors import AuditServiceError
from app.modules.audit.schemas import AuditLog, ModelCallLog, QueryLog
from app.modules.audit.service import AuditService
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.service import AuthService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-audit"])


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
            AuthService().authenticate_access_token(
                session,
                access_token=token or "",
                required_scope="audit:read",
            )
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
        data=[_audit_log_data(log) for log in log_list.items],
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
            AuthService().authenticate_access_token(
                session,
                access_token=token or "",
                required_scope="audit:read",
            )
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
            auth_context = AuthService().authenticate_access_token(
                session,
                access_token=token or "",
                required_scope="audit:read",
            )
            log_list = service.list_query_logs(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                page=page,
                page_size=page_size,
                filters={
                    "user_id": user_id,
                    "kb_id": kb_id,
                    "status": status,
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
        data=[_query_log_data(log) for log in log_list.items],
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
            auth_context = AuthService().authenticate_access_token(
                session,
                access_token=token or "",
                required_scope="audit:read",
            )
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
            auth_context = AuthService().authenticate_access_token(
                session,
                access_token=token or "",
                required_scope="audit:read",
            )
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
        data=[_model_call_log_data(log) for log in log_list.items],
        pagination=PaginationData(page=page, page_size=page_size, total=log_list.total),
    )


def _audit_log_data(log: AuditLog) -> AuditLogData:
    return AuditLogData(
        id=log.id,
        request_id=log.request_id,
        trace_id=log.trace_id,
        event_name=log.event_name,
        actor_type=log.actor_type,
        actor_id=log.actor_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        result=log.result,
        risk_level=log.risk_level,
        config_version=log.config_version,
        permission_version=log.permission_version,
        index_version_hash=log.index_version_hash,
        summary_json=log.summary_json,
        error_code=log.error_code,
        created_at=log.created_at,
    )


def _query_log_data(log: QueryLog) -> QueryLogData:
    return QueryLogData(
        id=log.id,
        request_id=log.request_id,
        trace_id=log.trace_id,
        user_id=log.user_id,
        kb_ids=list(log.kb_ids),
        query_hash=log.query_hash,
        status=log.status,
        degraded=log.degraded,
        degrade_reason=log.degrade_reason,
        config_version=log.config_version,
        permission_version=log.permission_version,
        permission_filter_hash=log.permission_filter_hash,
        index_version_hash=log.index_version_hash,
        model_route_hash=log.model_route_hash,
        latency_ms=log.latency_ms,
        candidate_count=log.candidate_count,
        citation_count=log.citation_count,
        error_code=log.error_code,
        created_at=log.created_at,
    )


def _model_call_log_data(log: ModelCallLog) -> ModelCallLogData:
    return ModelCallLogData(
        id=log.id,
        request_id=log.request_id,
        trace_id=log.trace_id,
        caller=log.caller,
        model_type=log.model_type,
        model_name=log.model_name,
        model_version=log.model_version,
        model_route_hash=log.model_route_hash,
        status=log.status,
        latency_ms=log.latency_ms,
        token_usage_json=log.token_usage_json,
        degraded=log.degraded,
        config_version=log.config_version,
        prompt_hash=log.prompt_hash,
        input_hash=log.input_hash,
        output_hash=log.output_hash,
        error_code=log.error_code,
        created_at=log.created_at,
    )


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


def _audit_error_response(exc: AuditServiceError, *, stage: str) -> JSONResponse:
    not_found = {"AUDIT_LOG_NOT_FOUND", "QUERY_LOG_NOT_FOUND"}
    return JSONResponse(
        status_code=404 if exc.error_code in not_found else 503,
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
            "error_code": "AUDIT_DATABASE_ERROR",
            "message": "audit database operation failed",
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
