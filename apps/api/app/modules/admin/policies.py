"""Admin permission and visibility policy helpers."""

from __future__ import annotations

from typing import Any

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import (
    AdminKnowledgeBase,
    AdminKnowledgeBaseAccessRuleInput,
)
from app.modules.permissions.service import PermissionService

SUPPORTED_KB_VISIBILITIES = {"enterprise", "department_acl", "private"}
SUPPORTED_KB_ACCESS_SUBJECT_TYPES = {"department", "user", "role"}
SUPPORTED_KB_ACCESS_PERMISSIONS = {"discover", "query", "manage"}


def _validate_visibility(visibility: str) -> None:
    PermissionService().validate_visibility_policy(
        {"owner_department_id": "00000000-0000-0000-0000-000000000000", "visibility": visibility}
    )


def _validate_kb_visibility(kb_visibility: str) -> None:
    if kb_visibility not in SUPPORTED_KB_VISIBILITIES:
        raise AdminServiceError(
            "ADMIN_KB_VISIBILITY_INVALID",
            "knowledge base visibility is invalid",
            status_code=400,
            details={
                "kb_visibility": kb_visibility,
                "supported": sorted(SUPPORTED_KB_VISIBILITIES),
            },
        )


def _normalize_kb_access_rules(
    access_rules: list[AdminKnowledgeBaseAccessRuleInput],
    *,
    kb_visibility: str,
    owner_department_id: str,
) -> tuple[AdminKnowledgeBaseAccessRuleInput, ...]:
    normalized: dict[tuple[str, str, str], AdminKnowledgeBaseAccessRuleInput] = {}
    for rule in access_rules:
        subject_type = rule.subject_type.strip()
        subject_id = rule.subject_id.strip()
        permission = rule.permission.strip()
        if subject_type not in SUPPORTED_KB_ACCESS_SUBJECT_TYPES:
            raise AdminServiceError(
                "ADMIN_KB_ACCESS_SUBJECT_INVALID",
                "knowledge base access subject type is invalid",
                status_code=400,
                details={"subject_type": subject_type},
            )
        if permission not in SUPPORTED_KB_ACCESS_PERMISSIONS:
            raise AdminServiceError(
                "ADMIN_KB_ACCESS_PERMISSION_INVALID",
                "knowledge base access permission is invalid",
                status_code=400,
                details={"permission": permission},
            )
        if not subject_id:
            raise AdminServiceError(
                "ADMIN_KB_ACCESS_SUBJECT_INVALID",
                "knowledge base access subject id is required",
                status_code=400,
            )
        normalized[(subject_type, subject_id, permission)] = AdminKnowledgeBaseAccessRuleInput(
            subject_type=subject_type,
            subject_id=subject_id,
            permission=permission,
        )
    if kb_visibility != "enterprise" and not _rules_include_query_for_department(
        normalized.values(),
        owner_department_id,
    ):
        for permission in ("discover", "query", "manage"):
            normalized[("department", owner_department_id, permission)] = (
                AdminKnowledgeBaseAccessRuleInput(
                    subject_type="department",
                    subject_id=owner_department_id,
                    permission=permission,
                )
            )
    return tuple(normalized[key] for key in sorted(normalized))


def _rules_include_query_for_department(
    access_rules: Any,
    department_id: str,
) -> bool:
    return any(
        rule.subject_type == "department"
        and rule.subject_id == department_id
        and rule.permission in {"query", "manage"}
        for rule in access_rules
    )


def _kb_access_rule_key(access_rules: Any) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (rule.subject_type, rule.subject_id, rule.permission)
            for rule in access_rules
        )
    )


def _kb_visibility_policy_visibility(kb_visibility: str) -> str:
    return "enterprise" if kb_visibility == "enterprise" else "department"


def _kb_visibility_rank(kb_visibility: str) -> int:
    return {"private": 0, "department_acl": 1, "enterprise": 2}[kb_visibility]


def _kb_visibility_expands(previous: str, next_visibility: str) -> bool:
    return _kb_visibility_rank(next_visibility) > _kb_visibility_rank(previous)


def _kb_visibility_tightens(previous: str, next_visibility: str) -> bool:
    return _kb_visibility_rank(next_visibility) < _kb_visibility_rank(previous)


def _department_can_query_knowledge_base(
    knowledge_base: AdminKnowledgeBase,
    department_id: str,
) -> bool:
    if knowledge_base.kb_visibility == "enterprise":
        return True
    return _rules_include_query_for_department(knowledge_base.access_rules, department_id)


def _visibility_expands(previous: str, next_visibility: str) -> bool:
    return previous == "department" and next_visibility == "enterprise"


def _visibility_tightens(previous: str, next_visibility: str) -> bool:
    return previous == "enterprise" and next_visibility == "department"


def _document_permission_tightens(
    *,
    previous_visibility: str,
    next_visibility: str,
    previous_owner_department_id: str,
    next_owner_department_id: str,
) -> bool:
    return _visibility_tightens(previous_visibility, next_visibility) or (
        next_visibility == "department"
        and next_owner_department_id != previous_owner_department_id
    )
