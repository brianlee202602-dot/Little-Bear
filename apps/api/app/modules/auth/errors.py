"""Auth Service 结构化错误。"""

from __future__ import annotations

from app.shared.errors import ServiceError


class AuthServiceError(ServiceError):
    """认证失败或 token 校验失败时抛出，路由层转换为统一错误响应。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 401,
        retryable: bool = False,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            error_code,
            message,
            status_code=status_code,
            retryable=retryable,
            details=details,
        )
