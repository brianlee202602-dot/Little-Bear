"""Config Service 结构化错误。"""

from __future__ import annotations

from typing import Any


class ConfigServiceError(Exception):
    """active_config 无法安全加载时抛出的结构化异常。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
