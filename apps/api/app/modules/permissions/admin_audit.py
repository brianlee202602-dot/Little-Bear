"""Permission admin audit writer mixin."""

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


class PermissionAdminAuditMixin:
    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
        resource_type: str,
        resource_id: str | None,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        AuditWriter().write(
            session,
            enterprise_id=enterprise_id,
            actor_type="user",
            actor_id=actor_id,
            event_name=event_name,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            risk_level=risk_level,
            summary=summary,
            error_code=error_code,
        )
