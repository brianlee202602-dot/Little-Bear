from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    request_id: str
    error_code: str
    message: str
    stage: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
