"""Permission Service 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PermissionDepartment:
    id: str
    code: str
    name: str
    is_primary: bool = False


@dataclass(frozen=True)
class PermissionRole:
    id: str
    code: str
    name: str
    scope_type: str
    scope_id: str | None
    scopes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PermissionContext:
    enterprise_id: str
    user_id: str
    username: str
    status: str
    department_ids: tuple[str, ...]
    departments: tuple[PermissionDepartment, ...]
    roles: tuple[PermissionRole, ...]
    scopes: tuple[str, ...]
    permission_version: int
    org_version: int
    permission_filter_hash: str
    request_id: str | None = None

    def has_scope(self, required_scope: str) -> bool:
        if "*" in self.scopes or required_scope in self.scopes:
            return True
        prefix = required_scope.split(":", maxsplit=1)[0]
        return f"{prefix}:*" in self.scopes


@dataclass(frozen=True)
class PermissionFilter:
    enterprise_id: str
    department_ids: tuple[str, ...]
    kb_ids: tuple[str, ...]
    active_index_version_ids: tuple[str, ...]
    permission_version: int
    permission_filter_hash: str
    qdrant_filter: dict[str, Any]
    keyword_where_sql: str
    metadata_where_sql: str
    params: dict[str, Any]


@dataclass(frozen=True)
class CandidateMetadata:
    enterprise_id: str
    kb_id: str | None
    document_id: str
    chunk_id: str | None
    owner_department_id: str
    visibility: str
    document_lifecycle_status: str = "active"
    document_index_status: str = "indexed"
    chunk_status: str = "active"
    visibility_state: str = "active"
    index_version_id: str | None = None
    indexed_permission_version: int | None = None
    access_blocked: bool = False


@dataclass(frozen=True)
class CandidateGateResult:
    allowed: bool
    reason: str
    error_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
