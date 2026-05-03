from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str


request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)


def get_request_context() -> RequestContext | None:
    return request_context.get()
