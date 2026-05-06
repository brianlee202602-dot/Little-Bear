"""Auth API。

这些接口只在系统初始化完成且 ServiceBootstrap 就绪后开放。setup JWT 不能访问这些
接口；普通管理后台必须先通过本地账号登录获取 access/refresh token。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse, Response

from app.api.schemas.auth import (
    CurrentUserData,
    CurrentUserResponse,
    LoginRequest,
    PasswordChangeRequest,
    TokenResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.service import AuthService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["auth"])


@router.post("/sessions", response_model=TokenResponse)
async def create_session(request: Request, payload: LoginRequest) -> TokenResponse | JSONResponse:
    service = AuthService()
    try:
        with session_scope() as session:
            token_pair = service.create_session(
                session,
                username=payload.username,
                password=payload.password,
                enterprise_code=payload.enterprise_code,
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="auth_login")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="auth_login")

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in,
    )


@router.post("/token-refreshes", response_model=TokenResponse)
async def create_token_refresh(
    request: Request,
    authorization: str | None = Header(default=None),
) -> TokenResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuthService()
    try:
        with session_scope() as session:
            token_pair = service.refresh_session(
                session,
                refresh_token=token or "",
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="auth_refresh")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="auth_refresh")

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in,
    )


@router.delete(
    "/sessions/current",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_current_session(
    authorization: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuthService()
    try:
        with session_scope() as session:
            service.revoke_current_session(session, access_token=token or "")
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="auth_logout")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="auth_logout")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me", response_model=CurrentUserResponse)
async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUserResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuthService()
    try:
        with session_scope() as session:
            auth_context = service.authenticate_access_token(
                session,
                access_token=token or "",
                required_scope="auth:session",
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="auth_current_user")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="auth_current_user")

    return CurrentUserResponse(
        request_id=_request_id(),
        data=CurrentUserData.model_validate(auth_context.user.to_response()),
    )


@router.put(
    "/users/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def put_current_user_password(
    payload: PasswordChangeRequest,
    authorization: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = AuthService()
    try:
        with session_scope() as session:
            service.change_current_password(
                session,
                access_token=token or "",
                old_password=payload.old_password,
                new_password=payload.new_password,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="auth_password_change")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="auth_password_change")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


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


def _database_error_response(exc: SQLAlchemyError, *, stage: str) -> JSONResponse:
    original = getattr(exc, "orig", None) or exc.__cause__
    return JSONResponse(
        status_code=500,
        content={
            "request_id": _request_id(),
            "error_code": "AUTH_DATABASE_ERROR",
            "message": "auth database operation failed",
            "stage": stage,
            "retryable": True,
            "details": {
                "database_error": {
                    "type": exc.__class__.__name__,
                    "driver": _name(original),
                }
            },
        },
    )


def _name(value: object) -> str | None:
    return value.__class__.__name__ if value is not None else None
