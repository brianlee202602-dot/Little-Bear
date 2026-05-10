"""Permission Service 结构化错误。"""

from __future__ import annotations

from typing import Any


class PermissionServiceError(Exception):
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
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}
