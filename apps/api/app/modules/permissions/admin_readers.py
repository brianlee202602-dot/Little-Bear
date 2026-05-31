"""Permission admin resource readers."""

# ruff: noqa: F401

from __future__ import annotations

import json
from typing import Any

from app.modules.audit import AuditWriter
from app.modules.permissions.admin_policy import (
    actor_can_manage_all_knowledge_bases,
    actor_has_kb_access_rule,
    actor_has_knowledge_base_scope,
    department_can_query_knowledge_base,
    document_permission_event,
    document_permission_tightens,
    has_scope,
    kb_access_rule_key,
    kb_visibility_policy_visibility,
    kb_visibility_tightens,
    normalize_kb_access_rules,
    rules_include_query_for_department,
    validate_kb_visibility,
    validate_visibility,
    visibility_expands,
)
from app.modules.permissions.admin_schemas import (
    PermissionAdminActorContext,
    PermissionDepartment,
    PermissionDocument,
    PermissionKnowledgeBase,
    PermissionKnowledgeBaseAccessRule,
    PermissionKnowledgeBaseAccessRuleInput,
    PermissionKnowledgeBasePolicy,
    PermissionPolicy,
)
from app.modules.permissions.admin_writers import (
    PermissionRefreshJobWriter,
    PermissionResourceWriter,
)
from app.modules.permissions.errors import PermissionServiceError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class PermissionAdminResourceReaderMixin:
    def _load_knowledge_base(
        self,
        session: Session,
        kb_id: str,
        *,
        enterprise_id: str,
    ) -> PermissionKnowledgeBase:
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        knowledge_bases.id::text AS kb_id,
                        knowledge_bases.name,
                        knowledge_bases.status,
                        knowledge_bases.owner_department_id::text AS owner_department_id,
                        owner_department.code AS owner_department_code,
                        owner_department.name AS owner_department_name,
                        owner_department.status AS owner_department_status,
                        owner_department.is_default AS owner_department_is_default,
                        knowledge_bases.kb_visibility,
                        knowledge_bases.default_document_visibility,
                        knowledge_bases.default_document_owner_department_id::text
                            AS default_document_owner_department_id,
                        default_document_owner_department.code
                            AS default_document_owner_department_code,
                        default_document_owner_department.name
                            AS default_document_owner_department_name,
                        default_document_owner_department.status
                            AS default_document_owner_department_status,
                        default_document_owner_department.is_default
                            AS default_document_owner_department_is_default,
                        {_knowledge_base_access_rules_sql("knowledge_bases.id")},
                        knowledge_bases.config_scope_id,
                        knowledge_bases.policy_version
                    FROM knowledge_bases
                    LEFT JOIN departments owner_department
                      ON owner_department.id = knowledge_bases.owner_department_id
                     AND owner_department.enterprise_id = knowledge_bases.enterprise_id
                     AND owner_department.deleted_at IS NULL
                    LEFT JOIN departments default_document_owner_department
                      ON default_document_owner_department.id =
                         knowledge_bases.default_document_owner_department_id
                     AND default_document_owner_department.enterprise_id =
                         knowledge_bases.enterprise_id
                     AND default_document_owner_department.deleted_at IS NULL
                    WHERE knowledge_bases.id = CAST(:kb_id AS uuid)
                      AND knowledge_bases.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND knowledge_bases.deleted_at IS NULL
                      AND knowledge_bases.status != 'deleted'
                    LIMIT 1
                    """
                ),
                {"kb_id": kb_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASE_UNAVAILABLE",
                "knowledge base cannot be read",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "ADMIN_KNOWLEDGE_BASE_NOT_FOUND",
                "knowledge base does not exist",
                status_code=404,
            )
        return _knowledge_base_from_mapping(row._mapping)

    def _load_document(
        self,
        session: Session,
        doc_id: str,
        *,
        enterprise_id: str,
    ) -> PermissionDocument:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS doc_id,
                        d.kb_id::text AS kb_id,
                        d.folder_id::text AS folder_id,
                        d.title,
                        d.lifecycle_status,
                        d.index_status,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.current_version_id::text AS current_version_id,
                        dv.version_no AS current_version_no,
                        d.permission_snapshot_id::text AS permission_snapshot_id,
                        d.content_hash,
                        COALESCE(ps.policy_version, 1) AS policy_version
                    FROM documents d
                    LEFT JOIN permission_snapshots ps ON ps.id = d.permission_snapshot_id
                    LEFT JOIN document_versions dv ON dv.id = d.current_version_id
                    WHERE d.id = CAST(:doc_id AS uuid)
                      AND d.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND d.deleted_at IS NULL
                      AND d.lifecycle_status != 'deleted'
                    LIMIT 1
                    """
                ),
                {"doc_id": doc_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_UNAVAILABLE",
                "document cannot be read",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "ADMIN_DOCUMENT_NOT_FOUND",
                "document does not exist",
                status_code=404,
            )
        return _document_from_mapping(row._mapping)

    def _resolve_department(
        self,
        session: Session,
        *,
        enterprise_id: str,
        department_id: str,
    ) -> PermissionDepartment:
        normalized_department_id = department_id.strip()
        if not normalized_department_id:
            raise PermissionServiceError(
                "ADMIN_DEPARTMENT_INVALID",
                "department id is required",
                status_code=400,
            )
        try:
            row = session.execute(
                text(
                    """
                    SELECT id::text AS department_id, code, name, status, is_default
                    FROM departments
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND id = CAST(:department_id AS uuid)
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "department_id": normalized_department_id,
                },
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DEPARTMENT_UNAVAILABLE",
                "department cannot be read",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "ADMIN_DEPARTMENT_NOT_FOUND",
                "department does not exist",
                status_code=404,
            )
        return PermissionDepartment(
            id=row._mapping["department_id"],
            code=row._mapping["code"],
            name=row._mapping["name"],
            status=row._mapping["status"],
            is_default=bool(row._mapping["is_default"]),
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


def _knowledge_base_from_mapping(row: Any) -> PermissionKnowledgeBase:
    return PermissionKnowledgeBase(
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


def _knowledge_base_department_from_mapping(
    row: Any,
    *,
    prefix: str,
    department_id_key: str,
) -> PermissionDepartment | None:
    code_key = f"{prefix}_code"
    if code_key not in row or row[code_key] is None:
        return None
    return PermissionDepartment(
        id=row[department_id_key],
        code=row[code_key],
        name=row[f"{prefix}_name"],
        status=row[f"{prefix}_status"],
        is_default=bool(row[f"{prefix}_is_default"]),
    )


def _kb_access_rules_from_value(
    value: Any,
) -> tuple[PermissionKnowledgeBaseAccessRule, ...]:
    if value is None:
        return ()
    items = json.loads(value) if isinstance(value, str) else value
    if not isinstance(items, list):
        return ()
    rules: list[PermissionKnowledgeBaseAccessRule] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject_type = str(item.get("subject_type") or "").strip()
        subject_id = str(item.get("subject_id") or "").strip()
        permission = str(item.get("permission") or "").strip()
        if subject_type and subject_id and permission:
            rules.append(
                PermissionKnowledgeBaseAccessRule(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    permission=permission,
                )
            )
    return tuple(rules)


def _document_from_mapping(row: Any) -> PermissionDocument:
    return PermissionDocument(
        id=row["doc_id"],
        kb_id=row["kb_id"],
        folder_id=row["folder_id"],
        title=row["title"],
        lifecycle_status=row["lifecycle_status"],
        index_status=row["index_status"],
        owner_department_id=row["owner_department_id"],
        visibility=row["visibility"],
        current_version_id=row["current_version_id"],
        current_version_no=(
            int(row["current_version_no"])
            if "current_version_no" in row and row["current_version_no"] is not None
            else None
        ),
        permission_snapshot_id=row["permission_snapshot_id"],
        content_hash=row["content_hash"],
        policy_version=int(row["policy_version"]) if "policy_version" in row else 1,
    )


def _database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> PermissionServiceError:
    return PermissionServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
