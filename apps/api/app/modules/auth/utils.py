"""Auth service shared helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthRole

BASE_USER_SCOPES = ("auth:session", "auth:password:update:self")


def merge_scopes(roles: tuple[AuthRole, ...]) -> tuple[str, ...]:
    scopes: set[str] = set(BASE_USER_SCOPES)
    for role in roles:
        scopes.update(role.scopes)
    return tuple(sorted(scopes))


def has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes


def effective_scopes(
    token_scopes: tuple[str, ...],
    current_scopes: tuple[str, ...],
) -> tuple[str, ...]:
    if "*" in token_scopes and "*" in current_scopes:
        return ("*",)
    if "*" in token_scopes:
        return tuple(sorted(set(current_scopes)))
    if "*" in current_scopes:
        return tuple(sorted(set(token_scopes)))

    effective: set[str] = set()
    for scope in current_scopes:
        if has_scope(token_scopes, scope):
            effective.add(scope)
    for scope in token_scopes:
        if has_scope(current_scopes, scope):
            effective.add(scope)
    return tuple(sorted(effective))


def normalize_scopes(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def required_str_claim(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise AuthServiceError("AUTH_TOKEN_INVALID", f"token claim is missing: {name}")
    return value


def status_error(status: str) -> AuthServiceError:
    if status == "locked":
        return AuthServiceError("AUTH_ACCOUNT_LOCKED", "account is locked", status_code=423)
    if status == "disabled":
        return AuthServiceError("AUTH_USER_DISABLED", "user is disabled", status_code=403)
    return AuthServiceError("AUTH_USER_DISABLED", "user is not active", status_code=403)


def as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def truncate_user_agent(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:256]


def json_metadata(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def auth_code_for_jwt_error(error_code: str) -> str:
    if error_code == "JWT_EXPIRED":
        return "AUTH_TOKEN_EXPIRED"
    return "AUTH_TOKEN_INVALID"
