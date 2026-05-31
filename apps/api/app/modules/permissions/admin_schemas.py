"""权限管理写模型的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PermissionAdminActorContext:
    """管理后台权限操作者的最小上下文。"""

    user_id: str
    scopes: tuple[str, ...]
    department_ids: tuple[str, ...] = ()
    role_ids: tuple[str, ...] = ()
    knowledge_base_ids: tuple[str, ...] = ()
    can_manage_all_knowledge_bases: bool = False


@dataclass(frozen=True)
class PermissionDepartment:
    id: str
    code: str
    name: str
    status: str
    is_primary: bool = False
    is_default: bool = False


@dataclass(frozen=True)
class PermissionKnowledgeBaseAccessRule:
    subject_type: str
    subject_id: str
    permission: str


@dataclass(frozen=True)
class PermissionKnowledgeBaseAccessRuleInput:
    subject_type: str
    subject_id: str
    permission: str


@dataclass(frozen=True)
class PermissionKnowledgeBase:
    id: str
    name: str
    status: str
    owner_department_id: str
    kb_visibility: str
    default_document_visibility: str
    default_document_owner_department_id: str
    owner_department: PermissionDepartment | None = None
    default_document_owner_department: PermissionDepartment | None = None
    config_scope_id: str | None = None
    policy_version: int = 1
    access_rules: tuple[PermissionKnowledgeBaseAccessRule, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class PermissionDocument:
    id: str
    kb_id: str
    title: str
    lifecycle_status: str
    index_status: str
    owner_department_id: str
    visibility: str
    folder_id: str | None = None
    current_version_id: str | None = None
    current_version_no: int | None = None
    permission_snapshot_id: str | None = None
    content_hash: str | None = None
    policy_version: int = 1


@dataclass(frozen=True)
class PermissionPolicy:
    resource_type: str
    resource_id: str
    visibility: str
    permission_version: int


@dataclass(frozen=True)
class PermissionKnowledgeBasePolicy:
    resource_type: str
    resource_id: str
    kb_visibility: str
    default_document_visibility: str
    default_document_owner_department_id: str
    access_rules: tuple[PermissionKnowledgeBaseAccessRule, ...]
    permission_version: int
