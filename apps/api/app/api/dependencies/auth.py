"""Shared authentication and request context helpers for route modules."""

from __future__ import annotations

from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.shared.context import get_request_context


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def authenticate_required_scope(
    session: object,
    token: str | None,
    *,
    required_scope: str,
) -> AuthContext:
    return AuthService().authenticate_access_token(
        session,
        access_token=token or "",
        required_scope=required_scope,
    )


def current_request_id() -> str:
    request_context = get_request_context()
    return request_context.request_id if request_context else "req_unknown"


def current_trace_id() -> str:
    request_context = get_request_context()
    return request_context.trace_id if request_context else "trace_unknown"
