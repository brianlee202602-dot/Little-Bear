"""Import Service 结构化错误。"""

from __future__ import annotations

from typing import Any


class ImportServiceError(Exception):
    """导入任务创建、查询和 Worker 阶段推进失败。"""

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
