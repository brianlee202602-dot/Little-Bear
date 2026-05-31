"""Permission admin policy guards."""

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


class PermissionAdminGuardMixin:
    def _ensure_actor_can_manage_permissions(
        self,
        actor_context: PermissionAdminActorContext | None,
    ) -> None:
        if actor_context is None or has_scope(actor_context.scopes, "permission:manage"):
            return
        raise PermissionServiceError(
            "ADMIN_SCOPE_REQUIRED",
            "permission management requires permission:manage",
            status_code=403,
            details={"required_scope": "permission:manage"},
        )

    def _ensure_actor_can_access_knowledge_base(
        self,
        actor_context: PermissionAdminActorContext | None,
        knowledge_base: PermissionKnowledgeBase,
    ) -> None:
        if actor_context is None or actor_can_manage_all_knowledge_bases(actor_context):
            return
        if actor_has_knowledge_base_scope(actor_context, knowledge_base.id):
            return
        if knowledge_base.owner_department_id in actor_context.department_ids:
            return
        if actor_has_kb_access_rule(actor_context, knowledge_base.access_rules, "manage"):
            return
        raise PermissionServiceError(
            "ADMIN_RESOURCE_FORBIDDEN",
            "knowledge base is outside actor management scope",
            status_code=403,
            details={"kb_id": knowledge_base.id},
        )

    def _ensure_default_document_permission_within_kb_access(
        self,
        *,
        kb_visibility: str,
        access_rules: tuple[PermissionKnowledgeBaseAccessRuleInput, ...]
        | tuple[PermissionKnowledgeBaseAccessRule, ...],
        default_document_visibility: str,
        default_document_owner_department_id: str,
    ) -> None:
        if default_document_visibility == "enterprise" or kb_visibility == "enterprise":
            return
        if rules_include_query_for_department(
            access_rules,
            default_document_owner_department_id,
        ):
            return
        raise PermissionServiceError(
            "ADMIN_DEFAULT_DOCUMENT_PERMISSION_OUTSIDE_KB_SCOPE",
            "default document owner department must be able to query parent knowledge base",
            status_code=409,
            details={
                "kb_visibility": kb_visibility,
                "default_document_visibility": default_document_visibility,
                "default_document_owner_department_id": default_document_owner_department_id,
            },
        )

    def _ensure_document_permission_within_parent_knowledge_base(
        self,
        *,
        knowledge_base: PermissionKnowledgeBase,
        document: PermissionDocument,
        next_visibility: str,
        next_owner_department_id: str,
    ) -> None:
        if next_visibility == "enterprise":
            return
        if department_can_query_knowledge_base(knowledge_base, next_owner_department_id):
            return
        raise PermissionServiceError(
            "ADMIN_DOCUMENT_PERMISSION_OUTSIDE_KB_SCOPE",
            "document owner department must be able to access parent knowledge base",
            status_code=409,
            details={
                "kb_id": knowledge_base.id,
                "kb_visibility": knowledge_base.kb_visibility,
                "kb_owner_department_id": knowledge_base.owner_department_id,
                "document_id": document.id,
                "document_visibility": next_visibility,
                "document_owner_department_id": next_owner_department_id,
            },
        )
