from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.context import RequestContext, request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
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
