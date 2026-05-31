"""Compatibility service for legacy admin permission methods."""

from __future__ import annotations

from typing import Any

from app.modules.admin.access_control import (
    AdminActorContext,
    permission_admin_actor_context,
)
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.policies import (
    _kb_access_rule_key,
    _kb_visibility_policy_visibility,
    _kb_visibility_tightens,
    _normalize_kb_access_rules,
    _validate_kb_visibility,
    _validate_visibility,
)
from app.modules.admin.schemas import (
    AdminKnowledgeBaseAccessRule,
    AdminKnowledgeBaseAccessRuleInput,
    AdminKnowledgeBasePermissionPolicy,
    AdminPermissionPolicy,
)
from app.modules.admin.utils import _database_error
from app.modules.permissions.errors import PermissionServiceError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminPermissionService:
    """兼容旧 AdminService 权限策略入口。

    新权限路由已经使用 `modules.permissions.PermissionAdminService`；这里保留旧
    `AdminService` 上的两个方法，避免已有调用方和单元测试在服务拆分期失效。
    """

    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def replace_knowledge_base_permissions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        kb_id: str,
        kb_visibility: str,
        default_document_visibility: str,
        default_document_owner_department_id: str,
        access_rules: list[AdminKnowledgeBaseAccessRuleInput],
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminKnowledgeBasePermissionPolicy:
        """独立替换知识库权限策略。"""

        self._core_service._ensure_actor_can_manage_permissions(actor_context)
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "replacing knowledge base permissions requires confirmation",
                status_code=428,
            )
        current = self._core_service._load_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
        )
        self._core_service._ensure_actor_can_access_knowledge_base(
            actor_context,
            current,
        )
        _validate_kb_visibility(kb_visibility)
        try:
            _validate_visibility(default_document_visibility)
        except PermissionServiceError as exc:
            raise AdminServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc
        default_document_owner = self._core_service._resolve_department(
            session,
            enterprise_id=enterprise_id,
            department_id=default_document_owner_department_id,
        )
        normalized_access_rules = _normalize_kb_access_rules(
            access_rules,
            kb_visibility=kb_visibility,
            owner_department_id=current.owner_department_id,
        )
        self._core_service._ensure_default_document_permission_within_kb_access(
            kb_visibility=kb_visibility,
            access_rules=normalized_access_rules,
            default_document_visibility=default_document_visibility,
            default_document_owner_department_id=default_document_owner.id,
        )
        permission_changed = (
            kb_visibility != current.kb_visibility
            or default_document_visibility != current.default_document_visibility
            or default_document_owner.id != current.default_document_owner_department_id
            or _kb_access_rule_key(normalized_access_rules)
            != _kb_access_rule_key(current.access_rules)
        )
        if not permission_changed:
            return AdminKnowledgeBasePermissionPolicy(
                resource_type="knowledge_base",
                resource_id=current.id,
                kb_visibility=current.kb_visibility,
                default_document_visibility=current.default_document_visibility,
                default_document_owner_department_id=(
                    current.default_document_owner_department_id
                ),
                access_rules=current.access_rules,
                permission_version=self._core_service._load_resource_permission_version(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="knowledge_base",
                    resource_id=current.id,
                ),
            )

        permission_tightened = _kb_visibility_tightens(current.kb_visibility, kb_visibility)
        next_policy_version = current.policy_version + 1
        try:
            self._core_service._replace_knowledge_base_access_rules(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                access_rules=normalized_access_rules,
                actor_user_id=actor_user_id,
            )
            permission_version = self._core_service._bump_permission_version(
                session,
                enterprise_id,
            )
            policy_id = self._core_service._replace_resource_policy(
                session,
                enterprise_id=enterprise_id,
                resource_type="knowledge_base",
                resource_id=kb_id,
                owner_department_id=current.owner_department_id,
                visibility=_kb_visibility_policy_visibility(kb_visibility),
                policy_version=next_policy_version,
                actor_user_id=actor_user_id,
            )
            snapshot = self._core_service._insert_permission_snapshot(
                session,
                enterprise_id=enterprise_id,
                resource_type="knowledge_base",
                resource_id=kb_id,
                owner_department_id=current.owner_department_id,
                visibility=_kb_visibility_policy_visibility(kb_visibility),
                permission_version=permission_version,
                policy_version=next_policy_version,
                policy_id=policy_id,
            )
            refresh_job_id = self._core_service._enqueue_permission_refresh_job(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                doc_id=None,
                actor_user_id=actor_user_id,
                reason="knowledge_base_permission_changed",
                permission_snapshot_id=snapshot["snapshot_id"],
                permission_version=permission_version,
                resource_type="knowledge_base",
            )
            session.execute(
                text(
                    """
                    UPDATE knowledge_bases
                    SET kb_visibility = :kb_visibility,
                        default_document_visibility = :default_document_visibility,
                        default_document_owner_department_id =
                            CAST(:default_document_owner_department_id AS uuid),
                        policy_version = :policy_version,
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:kb_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                {
                    "kb_id": kb_id,
                    "enterprise_id": enterprise_id,
                    "kb_visibility": kb_visibility,
                    "default_document_visibility": default_document_visibility,
                    "default_document_owner_department_id": default_document_owner.id,
                    "policy_version": next_policy_version,
                    "actor_user_id": actor_user_id,
                },
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name=(
                    "knowledge_base.permission_tightened"
                    if permission_tightened
                    else "knowledge_base.permission_replaced"
                ),
                resource_type="knowledge_base",
                resource_id=kb_id,
                action="replace_permission",
                result="success",
                risk_level="critical" if permission_tightened else "high",
                summary={
                    "kb_id": kb_id,
                    "previous_kb_visibility": current.kb_visibility,
                    "next_kb_visibility": kb_visibility,
                    "previous_default_document_visibility": (
                        current.default_document_visibility
                    ),
                    "next_default_document_visibility": default_document_visibility,
                    "previous_default_document_owner_department_id": (
                        current.default_document_owner_department_id
                    ),
                    "next_default_document_owner_department_id": default_document_owner.id,
                    "previous_access_rules": [
                        rule.__dict__ for rule in current.access_rules
                    ],
                    "next_access_rules": [
                        rule.__dict__ for rule in normalized_access_rules
                    ],
                    "permission_version": permission_version,
                    "permission_snapshot_id": snapshot["snapshot_id"],
                    "refresh_job_id": refresh_job_id,
                },
            )
        except PermissionServiceError as exc:
            raise AdminServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASE_PERMISSION_UPDATE_FAILED",
                "knowledge base permissions cannot be updated",
                exc,
            ) from exc
        return AdminKnowledgeBasePermissionPolicy(
            resource_type="knowledge_base",
            resource_id=kb_id,
            kb_visibility=kb_visibility,
            default_document_visibility=default_document_visibility,
            default_document_owner_department_id=default_document_owner.id,
            access_rules=tuple(
                AdminKnowledgeBaseAccessRule(
                    subject_type=rule.subject_type,
                    subject_id=rule.subject_id,
                    permission=rule.permission,
                )
                for rule in normalized_access_rules
            ),
            permission_version=permission_version,
        )

    def replace_document_permissions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        doc_id: str,
        visibility: str,
        owner_department_id: str | None,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminPermissionPolicy:
        """独立替换文档权限策略。"""

        self._core_service._ensure_actor_can_manage_permissions(actor_context)
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "replacing document permissions requires confirmation",
                status_code=428,
            )
        permission_actor = permission_admin_actor_context(actor_context)
        document = self._core_service.patch_document(
            session,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            doc_id=doc_id,
            owner_department_id=owner_department_id,
            visibility=visibility,
            confirmed_visibility_expand=True,
            actor_context=permission_actor,
        )
        return AdminPermissionPolicy(
            resource_type="document",
            resource_id=document.id,
            visibility=document.visibility,
            permission_version=self._core_service._load_resource_permission_version(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=document.id,
            ),
        )
