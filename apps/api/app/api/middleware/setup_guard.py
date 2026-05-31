"""系统初始化和服务 bootstrap 门禁中间件。"""

from __future__ import annotations

import uuid

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db.session import session_scope
from app.modules.setup.bootstrap_service import ServiceBootstrapStateService
from app.modules.setup.service import SetupService, SetupStatus

SETUP_GUARD_EXEMPT_PATHS = {
    "/health/live",
    "/health/ready",
    "/internal/v1/setup-state",
    "/internal/v1/setup-config-validations",
    "/internal/v1/setup-initialization",
}


class SetupGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if _is_setup_guard_exempt(request):
            return await call_next(request)

        # 每个业务请求都重新读取 setup 状态，保证初始化完成、恢复初始化等状态能及时生效。
        state = SetupService().load_state()
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
        trace_id = request.headers.get("x-trace-id") or f"trace_{uuid.uuid4().hex}"
        if state.setup_status == SetupStatus.MIGRATION_REQUIRED:
            return _setup_guard_error(
                request_id,
                trace_id,
                "SETUP_MIGRATION_REQUIRED",
                "database migration is required before serving business APIs",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
                details={"setup_status": state.setup_status.value},
            )
        if state.setup_status == SetupStatus.DATABASE_UNAVAILABLE:
            return _setup_guard_error(
                request_id,
                trace_id,
                "SETUP_DATABASE_UNAVAILABLE",
                "database is unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
                details={"setup_status": state.setup_status.value},
            )
        if not state.initialized:
            return _setup_guard_error(
                request_id,
                trace_id,
                "SETUP_REQUIRED",
                "system is not initialized",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                details={"setup_status": state.setup_status.value},
            )
        if not state.active_config_present:
            return _setup_guard_error(
                request_id,
                trace_id,
                "SERVICE_BOOTSTRAP_UNAVAILABLE",
                "active config is not available",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
                details={
                    "setup_status": state.setup_status.value,
                    "active_config_present": state.active_config_present,
                    "service_bootstrap_ready": state.service_bootstrap_ready,
                },
            )
        if not state.service_bootstrap_ready:
            # service_bootstrap 可能是进程启动时未完成或状态丢失，这里做一次受控刷新。
            refreshed = _refresh_service_bootstrap(state.active_config_version)
            if not refreshed:
                return _setup_guard_error(
                    request_id,
                    trace_id,
                    "SERVICE_BOOTSTRAP_UNAVAILABLE",
                    "service bootstrap is not ready",
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    retryable=True,
                    details={
                        "setup_status": state.setup_status.value,
                        "active_config_present": state.active_config_present,
                        "service_bootstrap_ready": False,
                    },
                )

        return await call_next(request)


def _is_setup_guard_exempt(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    return request.url.path in SETUP_GUARD_EXEMPT_PATHS


def _setup_guard_error(
    request_id: str,
    trace_id: str,
    error_code: str,
    message: str,
    status_code: int,
    *,
    retryable: bool = False,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={
            "request_id": request_id,
            "error_code": error_code,
            "message": message,
            "stage": "setup_guard",
            "retryable": retryable,
            "details": details or {},
        },
    )
    response.headers["x-request-id"] = request_id
    response.headers["x-trace-id"] = trace_id
    return response


def _refresh_service_bootstrap(active_config_version: int | None) -> bool:
    if active_config_version is None:
        return False
    try:
        with session_scope() as session:
            result = ServiceBootstrapStateService().ensure_ready(
                session,
                active_config_version=active_config_version,
            )
            return result.ready
    except Exception:
        return False
