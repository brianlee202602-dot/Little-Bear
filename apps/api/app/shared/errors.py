from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ServiceError(Exception):
    """Base class for structured service-layer errors."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


class ErrorResponse(BaseModel):
    request_id: str
    error_code: str
    message: str
    stage: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
