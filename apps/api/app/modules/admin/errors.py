"""Admin Service 结构化错误。"""

from __future__ import annotations

from typing import Any

from app.shared.errors import ServiceError


class AdminServiceError(ServiceError):
    """管理后台用户、角色或绑定操作失败。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 400,
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
