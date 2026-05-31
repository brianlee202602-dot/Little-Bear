"""Permission boundary guards for admin services."""

from __future__ import annotations

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.policies import (
    _department_can_query_knowledge_base,
    _rules_include_query_for_department,
)
from app.modules.admin.schemas import (
    AdminDocument,
    AdminKnowledgeBaseAccessRule,
    AdminKnowledgeBaseAccessRuleInput,
)
from sqlalchemy.orm import Session


class AdminPermissionGuardMixin:
    """Compatibility mixin exposing historical AdminService permission guards."""

    def _ensure_default_document_permission_within_kb_access(
        self,
        *,
        kb_visibility: str,
        access_rules: tuple[AdminKnowledgeBaseAccessRuleInput, ...]
        | tuple[AdminKnowledgeBaseAccessRule, ...],
        default_document_visibility: str,
        default_document_owner_department_id: str,
    ) -> None:
        if default_document_visibility == "enterprise":
            return
        if kb_visibility == "enterprise":
            return
        if _rules_include_query_for_department(
            access_rules,
            default_document_owner_department_id,
        ):
            return
        raise AdminServiceError(
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
        session: Session,
        *,
        enterprise_id: str,
        document: AdminDocument,
        next_visibility: str,
        next_owner_department_id: str,
    ) -> None:
        knowledge_base = self._load_knowledge_base(
            session,
            document.kb_id,
            enterprise_id=enterprise_id,
        )
        if next_visibility == "enterprise":
            return
        if not _department_can_query_knowledge_base(knowledge_base, next_owner_department_id):
            raise AdminServiceError(
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
