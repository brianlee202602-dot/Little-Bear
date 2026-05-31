"""管理后台权限策略与作用域判断。"""

from __future__ import annotations

from typing import Any

from app.modules.permissions.admin_schemas import (
    PermissionAdminActorContext,
    PermissionKnowledgeBase,
    PermissionKnowledgeBaseAccessRule,
    PermissionKnowledgeBaseAccessRuleInput,
)
from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.service import PermissionService

SUPPORTED_KB_VISIBILITIES = {"enterprise", "department_acl", "private"}
SUPPORTED_KB_ACCESS_SUBJECT_TYPES = {"department", "user", "role"}
SUPPORTED_KB_ACCESS_PERMISSIONS = {"discover", "query", "manage"}


def has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes


def validate_visibility(visibility: str) -> None:
    PermissionService().validate_visibility_policy(
        {"owner_department_id": "00000000-0000-0000-0000-000000000000", "visibility": visibility}
    )


def validate_kb_visibility(kb_visibility: str) -> None:
    if kb_visibility not in SUPPORTED_KB_VISIBILITIES:
        raise PermissionServiceError(
            "ADMIN_KB_VISIBILITY_INVALID",
            "knowledge base visibility is invalid",
            status_code=400,
            details={
                "kb_visibility": kb_visibility,
                "supported": sorted(SUPPORTED_KB_VISIBILITIES),
            },
        )


def normalize_kb_access_rules(
    access_rules: list[PermissionKnowledgeBaseAccessRuleInput],
    *,
    kb_visibility: str,
    owner_department_id: str,
) -> tuple[PermissionKnowledgeBaseAccessRuleInput, ...]:
    normalized: dict[
        tuple[str, str, str],
        PermissionKnowledgeBaseAccessRuleInput,
    ] = {}
    for rule in access_rules:
        subject_type = rule.subject_type.strip()
        subject_id = rule.subject_id.strip()
        permission = rule.permission.strip()
        if subject_type not in SUPPORTED_KB_ACCESS_SUBJECT_TYPES:
            raise PermissionServiceError(
                "ADMIN_KB_ACCESS_SUBJECT_INVALID",
                "knowledge base access subject type is invalid",
                status_code=400,
                details={"subject_type": subject_type},
            )
        if permission not in SUPPORTED_KB_ACCESS_PERMISSIONS:
            raise PermissionServiceError(
                "ADMIN_KB_ACCESS_PERMISSION_INVALID",
                "knowledge base access permission is invalid",
                status_code=400,
                details={"permission": permission},
            )
        if not subject_id:
            raise PermissionServiceError(
                "ADMIN_KB_ACCESS_SUBJECT_INVALID",
                "knowledge base access subject id is required",
                status_code=400,
            )
        normalized[(subject_type, subject_id, permission)] = (
            PermissionKnowledgeBaseAccessRuleInput(
                subject_type=subject_type,
                subject_id=subject_id,
                permission=permission,
            )
        )
    if kb_visibility != "enterprise" and not rules_include_query_for_department(
        normalized.values(),
        owner_department_id,
    ):
        for permission in ("discover", "query", "manage"):
            normalized[("department", owner_department_id, permission)] = (
                PermissionKnowledgeBaseAccessRuleInput(
                    subject_type="department",
                    subject_id=owner_department_id,
                    permission=permission,
                )
            )
    return tuple(normalized[key] for key in sorted(normalized))


def rules_include_query_for_department(access_rules: Any, department_id: str) -> bool:
    return any(
        rule.subject_type == "department"
        and rule.subject_id == department_id
        and rule.permission in {"query", "manage"}
        for rule in access_rules
    )


def kb_access_rule_key(access_rules: Any) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted((rule.subject_type, rule.subject_id, rule.permission) for rule in access_rules)
    )


def kb_visibility_policy_visibility(kb_visibility: str) -> str:
    return "enterprise" if kb_visibility == "enterprise" else "department"


def kb_visibility_rank(kb_visibility: str) -> int:
    return {"private": 0, "department_acl": 1, "enterprise": 2}[kb_visibility]


def kb_visibility_tightens(previous: str, next_visibility: str) -> bool:
    return kb_visibility_rank(next_visibility) < kb_visibility_rank(previous)


def department_can_query_knowledge_base(
    knowledge_base: PermissionKnowledgeBase,
    department_id: str,
) -> bool:
    if knowledge_base.kb_visibility == "enterprise":
        return True
    return rules_include_query_for_department(knowledge_base.access_rules, department_id)


def visibility_expands(previous: str, next_visibility: str) -> bool:
    return previous == "department" and next_visibility == "enterprise"


def visibility_tightens(previous: str, next_visibility: str) -> bool:
    return previous == "enterprise" and next_visibility == "department"


def document_permission_tightens(
    *,
    previous_visibility: str,
    next_visibility: str,
    previous_owner_department_id: str,
    next_owner_department_id: str,
) -> bool:
    return visibility_tightens(previous_visibility, next_visibility) or (
        next_visibility == "department"
        and next_owner_department_id != previous_owner_department_id
    )


def document_permission_event(
    *,
    visibility_expanded: bool,
    permission_tightened: bool,
) -> tuple[str, str, str]:
    if permission_tightened:
        return "document.permission_tightened", "tighten_permission", "critical"
    if visibility_expanded:
        return "document.visibility_expanded", "expand_visibility", "high"
    return "document.updated", "update", "medium"


def actor_can_manage_all_knowledge_bases(
    actor_context: PermissionAdminActorContext,
) -> bool:
    return bool(actor_context.can_manage_all_knowledge_bases)


def actor_has_knowledge_base_scope(
    actor_context: PermissionAdminActorContext,
    kb_id: str | None,
) -> bool:
    if kb_id is None:
        return False
    return kb_id in actor_context.knowledge_base_ids


def actor_has_kb_access_rule(
    actor_context: PermissionAdminActorContext,
    access_rules: tuple[PermissionKnowledgeBaseAccessRule, ...],
    permission: str,
) -> bool:
    implied_permissions = {permission}
    if permission in {"discover", "query"}:
        implied_permissions.add("manage")
    for rule in access_rules:
        if rule.permission not in implied_permissions:
            continue
        if rule.subject_type == "user" and rule.subject_id == actor_context.user_id:
            return True
        if rule.subject_type == "department" and rule.subject_id in actor_context.department_ids:
            return True
        if rule.subject_type == "role" and rule.subject_id in actor_context.role_ids:
            return True
    return False
