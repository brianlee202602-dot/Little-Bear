"""Admin Service 对外返回的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
class AdminRoleListItem:
    id: str
    code: str
    name: str
    scope_type: str
    is_builtin: bool
    status: str


@dataclass(frozen=True)
class AdminRoleList:
    items: list[AdminRoleListItem]
    total: int


@dataclass(frozen=True)
class AdminAssignableRoleOption:
    id: str
    code: str
    name: str
    scope_type: str
    status: str
    risk_level: str


@dataclass(frozen=True)
class AdminAssignableRoleOptionList:
    items: list[AdminAssignableRoleOption]
    total: int


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
class AdminUserListItem:
    id: str
    username: str
    name: str
    status: str
    department_names: tuple[str, ...] = field(default_factory=tuple)
    role_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdminUserList:
    items: list[AdminUserListItem]
    total: int


@dataclass(frozen=True)
class AdminDepartmentListItem:
    id: str
    name: str
    status: str
    is_default: bool = False


@dataclass(frozen=True)
class AdminDepartmentList:
    items: list[AdminDepartmentListItem]
    total: int


@dataclass(frozen=True)
class AdminUserDepartmentList:
    items: list[AdminDepartment]
    total: int


@dataclass(frozen=True)
class AdminDepartmentOption:
    id: str
    name: str
    status: str
    is_default: bool = False


@dataclass(frozen=True)
class AdminDepartmentOptionList:
    items: list[AdminDepartmentOption]
    total: int


@dataclass(frozen=True)
class AdminKnowledgeBaseAccessRule:
    subject_type: str
    subject_id: str
    permission: str


@dataclass(frozen=True)
class AdminKnowledgeBaseAccessRuleInput:
    subject_type: str
    subject_id: str
    permission: str


@dataclass(frozen=True)
class AdminKnowledgeBase:
    id: str
    name: str
    status: str
    owner_department_id: str
    kb_visibility: str
    default_document_visibility: str
    default_document_owner_department_id: str
    owner_department: AdminDepartment | None = None
    default_document_owner_department: AdminDepartment | None = None
    config_scope_id: str | None = None
    policy_version: int = 1
    access_rules: tuple[AdminKnowledgeBaseAccessRule, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdminKnowledgeBaseListItem:
    id: str
    name: str
    status: str
    owner_department_id: str
    kb_visibility: str
    default_document_visibility: str
    default_document_owner_department_id: str
    owner_department_name: str | None = None
    default_document_owner_department_name: str | None = None


@dataclass(frozen=True)
class AdminKnowledgeBaseList:
    items: list[AdminKnowledgeBaseListItem]
    total: int


@dataclass(frozen=True)
class AdminKnowledgeBaseOption:
    id: str
    name: str
    status: str


@dataclass(frozen=True)
class AdminKnowledgeBaseOptionList:
    items: list[AdminKnowledgeBaseOption]
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
class AdminFolderOption:
    id: str
    name: str
    status: str


@dataclass(frozen=True)
class AdminFolderOptionList:
    items: list[AdminFolderOption]
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
    folder_name: str | None = None
    owner_department_name: str | None = None
    current_version_id: str | None = None
    current_version_no: int | None = None
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
class AdminDocumentVersionList:
    items: list[AdminDocumentVersion]
    total: int


@dataclass(frozen=True)
class AdminIndexVersion:
    id: str
    document_id: str
    document_version_id: str
    embedding_model: str
    model_version: str
    dimension: int
    collection_name: str
    status: str
    chunk_count: int
    created_at: datetime | None = None
    activated_at: datetime | None = None


@dataclass(frozen=True)
class AdminIndexVersionList:
    items: list[AdminIndexVersion]
    total: int


@dataclass(frozen=True)
class AdminChunk:
    id: str
    document_id: str
    document_version_id: str
    text_preview: str
    page_start: int | None
    page_end: int | None
    status: str
    ordinal: int


@dataclass(frozen=True)
class AdminChunkList:
    items: list[AdminChunk]
    total: int


@dataclass(frozen=True)
class AdminDocumentPreviewChunk:
    id: str
    document_id: str
    document_version_id: str
    text: str
    text_preview: str
    page_start: int | None
    page_end: int | None
    status: str
    ordinal: int
    heading_path: str | None
    source_offsets: dict[str, Any] | None
    text_status: str


@dataclass(frozen=True)
class AdminDocumentPreview:
    doc_id: str
    title: str
    chunks: tuple[AdminDocumentPreviewChunk, ...]
    total: int = 0


@dataclass(frozen=True)
class AdminPermissionPolicy:
    resource_type: str
    resource_id: str
    visibility: str
    permission_version: int


@dataclass(frozen=True)
class AdminKnowledgeBasePermissionPolicy:
    resource_type: str
    resource_id: str
    kb_visibility: str
    default_document_visibility: str
    default_document_owner_department_id: str
    access_rules: tuple[AdminKnowledgeBaseAccessRule, ...]
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


@dataclass(frozen=True)
class AdminRoleBindingList:
    items: list[AdminRoleBinding]
    total: int
