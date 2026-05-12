"""Auth Service 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuthDepartment:
    id: str
    code: str
    name: str
    status: str
    is_primary: bool = False

    def to_response(self) -> dict[str, object]:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "status": self.status,
            "is_primary": self.is_primary,
        }


@dataclass(frozen=True)
class AuthRole:
    id: str
    code: str
    name: str
    scope_type: str
    is_builtin: bool
    status: str
    scope_id: str | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def to_response(self) -> dict[str, object]:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "scope_type": self.scope_type,
            "is_builtin": self.is_builtin,
            "status": self.status,
        }


@dataclass(frozen=True)
class AuthUser:
    id: str
    enterprise_id: str
    username: str
    display_name: str
    status: str
    email: str | None = None
    phone: str | None = None
    roles: tuple[AuthRole, ...] = field(default_factory=tuple)
    departments: tuple[AuthDepartment, ...] = field(default_factory=tuple)
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def to_response(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.display_name,
            "status": self.status,
            "departments": [department.to_response() for department in self.departments],
            "roles": [role.to_response() for role in self.roles],
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True)
class CredentialRecord:
    password_hash: str
    password_alg: str
    failed_login_count: int
    locked_until: datetime | None
    force_change_password: bool


@dataclass(frozen=True)
class LoginRecord:
    user: AuthUser
    credential: CredentialRecord


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int
    access_jti: str
    refresh_jti: str
    access_expires_at: datetime
    refresh_expires_at: datetime


@dataclass(frozen=True)
class AuthContext:
    user: AuthUser
    token_jti: str
    token_type: str
    scopes: tuple[str, ...]
    claims: dict[str, Any]
