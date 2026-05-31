"""Audit Service 结构化错误。"""

from __future__ import annotations

from typing import Any

from app.shared.errors import ServiceError


class AuditServiceError(ServiceError):
    """审计日志读取失败时抛出的结构化异常。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        resolved_status_code = (
            status_code if status_code is not None else _default_status_code(error_code)
        )
        super().__init__(
            error_code,
            message,
            status_code=resolved_status_code,
            retryable=retryable,
            details=details,
        )


def _default_status_code(error_code: str) -> int:
    if error_code in {"AUDIT_LOG_NOT_FOUND", "QUERY_LOG_NOT_FOUND", "MODEL_CALL_LOG_NOT_FOUND"}:
        return 404
    return 503
