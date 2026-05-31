"""查询路由共享依赖与响应工具。"""

from __future__ import annotations

from functools import partial

from app.api.dependencies.auth import authenticate_required_scope as _authenticate
from app.api.dependencies.auth import current_request_id as _request_id
from app.api.dependencies.auth import current_trace_id as _trace_id
from app.api.dependencies.auth import extract_bearer_token as _extract_bearer_token
from app.api.errors import (
    database_error_response,
    service_error_response,
    structured_error_response,
)

DEFAULT_CONVERSATION_MESSAGE_PAGE_SIZE = 50

_auth_error_response = service_error_response
_query_error_response = service_error_response
_database_error_response = partial(
    database_error_response,
    error_code="QUERY_DATABASE_ERROR",
    message="query database operation failed",
)

__all__ = [
    "DEFAULT_CONVERSATION_MESSAGE_PAGE_SIZE",
    "_auth_error_response",
    "_authenticate",
    "_database_error_response",
    "_extract_bearer_token",
    "_query_error_response",
    "_request_id",
    "_trace_id",
    "structured_error_response",
]
