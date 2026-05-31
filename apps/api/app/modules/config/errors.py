"""Config Service 结构化错误。"""

from __future__ import annotations

from typing import Any

from app.shared.errors import ServiceError


class ConfigServiceError(ServiceError):
    """active_config 无法安全加载时抛出的结构化异常。"""

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
    if error_code in {"CONFIG_KEY_NOT_FOUND", "CONFIG_VERSION_NOT_FOUND"}:
        return 404
    if error_code in {
        "CONFIG_VERSION_NOT_PUBLISHABLE",
        "CONFIG_VERSION_ARCHIVE_UNSUPPORTED",
        "CONFIG_VERSION_NOT_DISCARDABLE",
    }:
        return 409
    if error_code in {
        "CONFIG_ACTIVE_CONFIG_UNAVAILABLE",
        "CONFIG_ACTIVE_MISSING",
        "CONFIG_DEPENDENCY_FAILED",
        "CONFIG_STATE_UNAVAILABLE",
        "CONFIG_VERSION_PAYLOAD_MISSING",
        "CONFIG_VERSION_UNAVAILABLE",
    }:
        return 503
    return 400
