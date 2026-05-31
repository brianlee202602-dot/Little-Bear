"""Permission Service 结构化错误。"""

from __future__ import annotations

from typing import Any

from app.shared.errors import ServiceError


class PermissionServiceError(ServiceError):
    """权限上下文、过滤条件或资源准入校验失败。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 403,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code,
            message,
            status_code=status_code,
            retryable=retryable,
            details=details,
        )
