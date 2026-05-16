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
    is_default: bool = False
    org_version: int = 0


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
class AdminDepartmentList:
    items: list[AdminDepartment]
    total: int


@dataclass(frozen=True)
class AdminKnowledgeBase:
    id: str
    name: str
    status: str
    owner_department_id: str
    default_visibility: str
    config_scope_id: str | None = None
    policy_version: int = 1


@dataclass(frozen=True)
class AdminKnowledgeBaseList:
    items: list[AdminKnowledgeBase]
    total: int


@dataclass(frozen=True)
class AdminAcceptedResult:
    accepted: bool
    job_id: str | None = None


@dataclass(frozen=True)
class AdminFolder:
    id: str
    kb_id: str
    name: str
    status: str
    parent_id: str | None = None
    path: str = ""


@dataclass(frozen=True)
class AdminFolderList:
    items: list[AdminFolder]
    total: int


@dataclass(frozen=True)
class AdminDocument:
    id: str
    kb_id: str
    title: str
    lifecycle_status: str
    index_status: str
    owner_department_id: str
    visibility: str
    folder_id: str | None = None
    current_version_id: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    permission_snapshot_id: str | None = None
    content_hash: str | None = None
    policy_version: int = 1


@dataclass(frozen=True)
class AdminDocumentList:
    items: list[AdminDocument]
    total: int


@dataclass(frozen=True)
class AdminDocumentVersion:
    id: str
    document_id: str
    version_no: int
    status: str


@dataclass(frozen=True)
class AdminChunk:
    id: str
    document_id: str
    document_version_id: str
    text_preview: str
    page_start: int | None
    page_end: int | None
    status: str


@dataclass(frozen=True)
class AdminPermissionPolicy:
    resource_type: str
    resource_id: str
    visibility: str
    permission_version: int


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
