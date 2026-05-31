"""Shared API error response builders."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse

from app.api.dependencies.auth import current_request_id
from app.shared.errors import ServiceError


def structured_error_response(
    request_id: str | None,
    error_code: str,
    message: str,
    *,
    stage: str,
    status_code: int,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": request_id or current_request_id(),
            "error_code": error_code,
            "message": message,
            "stage": stage,
            "retryable": retryable,
            "details": details or {},
        },
    )


def service_error_response(exc: ServiceError, *, stage: str) -> JSONResponse:
    return structured_error_response(
        current_request_id(),
        exc.error_code,
        exc.message,
        stage=stage,
        status_code=exc.status_code,
        retryable=exc.retryable,
        details=exc.details,
    )


def database_error_response(
    exc: SQLAlchemyError,
    *,
    stage: str,
    error_code: str,
    message: str,
    retryable: bool = True,
) -> JSONResponse:
    original = getattr(exc, "orig", None) or exc.__cause__
    return structured_error_response(
        current_request_id(),
        error_code,
        message,
        stage=stage,
        status_code=500,
        retryable=retryable,
        details={
            "database_error": {
                "type": exc.__class__.__name__,
                "driver": original.__class__.__name__ if original is not None else None,
            }
        },
    )


def confirmation_required_response(
    *,
    stage: str,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return structured_error_response(
        current_request_id(),
        error_code,
        message,
        stage=stage,
        status_code=status.HTTP_428_PRECONDITION_REQUIRED,
        retryable=False,
        details=details,
    )
