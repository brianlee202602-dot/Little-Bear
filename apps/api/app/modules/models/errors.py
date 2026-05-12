"""模型网关客户端错误。"""

from __future__ import annotations


class ModelClientError(Exception):
    """外部模型服务调用失败。"""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
