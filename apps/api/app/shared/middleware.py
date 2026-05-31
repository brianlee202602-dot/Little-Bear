"""跨请求上下文中间件。

RequestContextMiddleware 负责把 request_id/trace_id 放入 contextvar，后续日志、
错误响应和审计都可以复用。
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.context import RequestContext, request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # 优先信任上游传入的追踪 ID，缺失时本服务生成，方便本地和单测排查。
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
        trace_id = request.headers.get("x-trace-id") or f"trace_{uuid.uuid4().hex}"
        token = request_context.set(RequestContext(request_id=request_id, trace_id=trace_id))
        try:
            response = await call_next(request)
        finally:
            request_context.reset(token)
        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = trace_id
        return response

