"""Auth Service 结构化错误。"""

from __future__ import annotations


class AuthServiceError(Exception):
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
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}
