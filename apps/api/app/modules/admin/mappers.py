"""Database row mappers for admin DTOs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.modules.admin.role_policy import _is_high_risk_role
from app.modules.admin.schemas import (
    AdminAssignableRoleOption,
    AdminChunk,
    AdminDepartment,
    AdminDepartmentListItem,
    AdminDepartmentOption,
    AdminDocument,
    AdminDocumentVersion,
    AdminFolder,
    AdminFolderOption,
    AdminIndexVersion,
    AdminKnowledgeBase,
    AdminKnowledgeBaseAccessRule,
    AdminKnowledgeBaseListItem,
    AdminKnowledgeBaseOption,
    AdminRole,
    AdminRoleBinding,
    AdminRoleListItem,
    AdminUserListItem,
)


@dataclass(frozen=True)
class _IndexRebuildTarget:
    document_id: str
    kb_id: str
    document_version_id: str


@dataclass(frozen=True)
class _IndexCleanupTarget:
    index_version_id: str
    document_id: str
    kb_id: str
    document_version_id: str
    collection_name: str
    status: str


def _role_from_mapping(row: Any) -> AdminRole:
    return AdminRole(
        id=row["role_id"],
        code=row["code"],
        name=row["name"],
        scope_type=row["scope_type"],
        is_builtin=bool(row["is_builtin"]),
        status=row["status"],
        scopes=tuple(str(item) for item in row["scopes"] or []),
    )


def _role_list_item_from_mapping(row: Any) -> AdminRoleListItem:
    return AdminRoleListItem(
        id=row["role_id"],
        code=row["code"],
        name=row["name"],
        scope_type=row["scope_type"],
        is_builtin=bool(row["is_builtin"]),
        status=row["status"],
    )


def _assignable_role_option_from_mapping(row: Any) -> AdminAssignableRoleOption:
    role = _role_from_mapping(row)
    return AdminAssignableRoleOption(
        id=role.id,
        code=role.code,
        name=role.name,
        scope_type=role.scope_type,
        status=role.status,
        risk_level="high" if _is_high_risk_role(role) else "low",
    )


def _user_list_item_from_mapping(row: Any) -> AdminUserListItem:
    return AdminUserListItem(
        id=row["user_id"],
        username=row["username"],
        name=row["display_name"],
        status=row["status"],
        department_names=tuple(str(item) for item in row["department_names"] or []),
        role_names=tuple(str(item) for item in row["role_names"] or []),
    )


def _department_from_mapping(row: Any) -> AdminDepartment:
    return AdminDepartment(
        id=row["department_id"],
        code=row["code"],
        name=row["name"],
        status=row["status"],
        is_primary=bool(row["is_primary"]) if "is_primary" in row else False,
        is_default=bool(row["is_default"]),
        org_version=int(row["org_version"]) if "org_version" in row else 0,
    )


def _department_list_item_from_mapping(row: Any) -> AdminDepartmentListItem:
    return AdminDepartmentListItem(
        id=row["department_id"],
        name=row["name"],
        status=row["status"],
        is_default=bool(row["is_default"]),
    )


def _department_option_from_mapping(row: Any) -> AdminDepartmentOption:
    return AdminDepartmentOption(
        id=row["department_id"],
        name=row["name"],
        status=row["status"],
        is_default=bool(row["is_default"]),
    )


def _knowledge_base_access_rules_sql(kb_id_expr: str) -> str:
    return f"""
                        COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'subject_type', kba.subject_type,
                                        'subject_id', kba.subject_id::text,
                                        'permission', kba.permission
                                    )
                                    ORDER BY kba.subject_type, kba.subject_id::text, kba.permission
                                )
                                FROM knowledge_base_accesses kba
                                WHERE kba.enterprise_id = knowledge_bases.enterprise_id
                                  AND kba.kb_id = {kb_id_expr}
                                  AND kba.status = 'active'
                            ),
                            '[]'::jsonb
                        ) AS access_rules
""".strip()


def _knowledge_base_from_mapping(row: Any) -> AdminKnowledgeBase:
    return AdminKnowledgeBase(
        id=row["kb_id"],
        name=row["name"],
        status=row["status"],
        owner_department_id=row["owner_department_id"],
        kb_visibility=row["kb_visibility"],
        default_document_visibility=row["default_document_visibility"],
        default_document_owner_department_id=row["default_document_owner_department_id"],
        owner_department=_knowledge_base_department_from_mapping(
            row,
            prefix="owner_department",
            department_id_key="owner_department_id",
        ),
        default_document_owner_department=_knowledge_base_department_from_mapping(
            row,
            prefix="default_document_owner_department",
            department_id_key="default_document_owner_department_id",
        ),
        config_scope_id=row["config_scope_id"],
        policy_version=int(row["policy_version"]) if "policy_version" in row else 1,
        access_rules=_kb_access_rules_from_value(row.get("access_rules")),
    )


def _knowledge_base_list_item_from_mapping(row: Any) -> AdminKnowledgeBaseListItem:
    return AdminKnowledgeBaseListItem(
        id=row["kb_id"],
        name=row["name"],
        status=row["status"],
        owner_department_id=row["owner_department_id"],
        kb_visibility=row["kb_visibility"],
        default_document_visibility=row["default_document_visibility"],
        default_document_owner_department_id=row["default_document_owner_department_id"],
        owner_department_name=row["owner_department_name"],
        default_document_owner_department_name=row["default_document_owner_department_name"],
    )


def _knowledge_base_option_from_mapping(row: Any) -> AdminKnowledgeBaseOption:
    return AdminKnowledgeBaseOption(
        id=row["kb_id"],
        name=row["name"],
        status=row["status"],
    )


def _knowledge_base_department_from_mapping(
    row: Any,
    *,
    prefix: str,
    department_id_key: str,
) -> AdminDepartment | None:
    code_key = f"{prefix}_code"
    if code_key not in row or row[code_key] is None:
        return None
    return AdminDepartment(
        id=row[department_id_key],
        code=row[code_key],
        name=row[f"{prefix}_name"],
        status=row[f"{prefix}_status"],
        is_default=bool(row[f"{prefix}_is_default"]),
    )


def _kb_access_rules_from_value(value: Any) -> tuple[AdminKnowledgeBaseAccessRule, ...]:
    if value is None:
        return ()
    items = json.loads(value) if isinstance(value, str) else value
    if not isinstance(items, list):
        return ()
    rules: list[AdminKnowledgeBaseAccessRule] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject_type = str(item.get("subject_type") or "").strip()
        subject_id = str(item.get("subject_id") or "").strip()
        permission = str(item.get("permission") or "").strip()
        if subject_type and subject_id and permission:
            rules.append(
                AdminKnowledgeBaseAccessRule(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    permission=permission,
                )
            )
    return tuple(rules)


def _folder_from_mapping(row: Any) -> AdminFolder:
    return AdminFolder(
        id=row["folder_id"],
        kb_id=row["kb_id"],
        parent_id=row["parent_id"],
        name=row["name"],
        status=row["status"],
        path=row["path"],
    )


def _folder_option_from_mapping(row: Any) -> AdminFolderOption:
    return AdminFolderOption(
        id=row["folder_id"],
        name=row["name"],
        status=row["status"],
    )


def _document_from_mapping(row: Any) -> AdminDocument:
    return AdminDocument(
        id=row["doc_id"],
        kb_id=row["kb_id"],
        folder_id=row["folder_id"],
        folder_name=row["folder_name"] if "folder_name" in row else None,
        title=row["title"],
        lifecycle_status=row["lifecycle_status"],
        index_status=row["index_status"],
        owner_department_id=row["owner_department_id"],
        owner_department_name=(
            row["owner_department_name"] if "owner_department_name" in row else None
        ),
        visibility=row["visibility"],
        current_version_id=row["current_version_id"],
        current_version_no=(
            int(row["current_version_no"])
            if "current_version_no" in row and row["current_version_no"] is not None
            else None
        ),
        tags=tuple(str(item) for item in row["tags"] or []),
        permission_snapshot_id=row["permission_snapshot_id"],
        content_hash=row["content_hash"],
        policy_version=int(row["policy_version"]) if "policy_version" in row else 1,
    )


def _document_version_from_mapping(row: Any) -> AdminDocumentVersion:
    return AdminDocumentVersion(
        id=row["version_id"],
        document_id=row["document_id"],
        version_no=int(row["version_no"]),
        status=row["status"],
    )


def _admin_index_version_from_mapping(row: Any) -> AdminIndexVersion:
    return AdminIndexVersion(
        id=row["index_version_id"],
        document_id=row["document_id"],
        document_version_id=row["document_version_id"],
        embedding_model=row["embedding_model"],
        model_version=row["model_version"],
        dimension=int(row["dimension"]),
        collection_name=row["collection_name"],
        status=row["status"],
        chunk_count=int(row["chunk_count"]),
        created_at=row["created_at"],
        activated_at=row["activated_at"],
    )


def _index_rebuild_target_from_mapping(row: Any) -> _IndexRebuildTarget:
    return _IndexRebuildTarget(
        document_id=row["document_id"],
        kb_id=row["kb_id"],
        document_version_id=row["document_version_id"],
    )


def _index_cleanup_target_from_mapping(row: Any) -> _IndexCleanupTarget:
    return _IndexCleanupTarget(
        index_version_id=row["index_version_id"],
        document_id=row["document_id"],
        kb_id=row["kb_id"],
        document_version_id=row["document_version_id"],
        collection_name=row["collection_name"],
        status=row["status"],
    )


def _admin_chunk_from_mapping(row: Any) -> AdminChunk:
    return AdminChunk(
        id=row["chunk_id"],
        document_id=row["document_id"],
        document_version_id=row["document_version_id"],
        text_preview=row["text_preview"],
        page_start=_optional_int(row["page_start"]),
        page_end=_optional_int(row["page_end"]),
        status=row["status"],
        ordinal=int(row["ordinal"]),
    )


def _role_binding_from_mapping(row: Any) -> AdminRoleBinding:
    return AdminRoleBinding(
        id=row["binding_id"],
        role_id=row["role_id"],
        subject_type="user",
        subject_id=row["user_id"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        role_code=row["role_code"],
        role_name=row["role_name"],
    )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
