"""Admin Service 对外返回的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdminDepartment:
    id: str
    code: str
    name: str
    status: str
    is_primary: bool = False


@dataclass(frozen=True)
class AdminRole:
    id: str
    code: str
    name: str
    scope_type: str
    is_builtin: bool
    status: str
    scopes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdminUser:
    id: str
    username: str
    name: str
    status: str
    enterprise_id: str
    email: str | None = None
    phone: str | None = None
    departments: tuple[AdminDepartment, ...] = field(default_factory=tuple)
    roles: tuple[AdminRole, ...] = field(default_factory=tuple)
    scopes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdminUserList:
    items: list[AdminUser]
    total: int


@dataclass(frozen=True)
class AdminRoleBinding:
    id: str
    role_id: str
    subject_type: str
    subject_id: str
    scope_type: str
    scope_id: str | None
    role_code: str | None = None
    role_name: str | None = None
