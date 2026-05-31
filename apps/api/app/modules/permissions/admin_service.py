"""权限管理写服务。

该服务承接管理后台的权限策略替换能力，避免 permissions 路由反向依赖 admin 模块。
"""

from __future__ import annotations

from app.modules.permissions.admin_audit import PermissionAdminAuditMixin
from app.modules.permissions.admin_guards import PermissionAdminGuardMixin
from app.modules.permissions.admin_policy import (
    document_permission_event,
    document_permission_tightens,
    kb_access_rule_key,
    kb_visibility_policy_visibility,
    kb_visibility_tightens,
    normalize_kb_access_rules,
    validate_kb_visibility,
    validate_visibility,
    visibility_expands,
)
from app.modules.permissions.admin_readers import (
    PermissionAdminResourceReaderMixin,
    _database_error,
)
from app.modules.permissions.admin_schemas import (
    PermissionAdminActorContext,
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


class PermissionAdminService(
    PermissionAdminResourceReaderMixin,
    PermissionAdminGuardMixin,
    PermissionAdminAuditMixin,
):
    """权限策略和权限快照的管理后台写模型。"""

    def __init__(
        self,
        *,
        resource_writer: PermissionResourceWriter | None = None,
        refresh_job_writer: PermissionRefreshJobWriter | None = None,
    ) -> None:
        self.resource_writer = resource_writer or PermissionResourceWriter()
        self.refresh_job_writer = refresh_job_writer or PermissionRefreshJobWriter()

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
        access_rules: list[PermissionKnowledgeBaseAccessRuleInput],
        confirmed: bool,
        actor_context: PermissionAdminActorContext | None = None,
    ) -> PermissionKnowledgeBasePolicy:
        """替换知识库可见性、默认文档权限和访问规则。"""

        self._ensure_actor_can_manage_permissions(actor_context)
        if not confirmed:
            raise PermissionServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "replacing knowledge base permissions requires confirmation",
                status_code=428,
            )
        current = self._load_knowledge_base(session, kb_id, enterprise_id=enterprise_id)
        self._ensure_actor_can_access_knowledge_base(actor_context, current)
        validate_kb_visibility(kb_visibility)
        validate_visibility(default_document_visibility)
        default_document_owner = self._resolve_department(
            session,
            enterprise_id=enterprise_id,
            department_id=default_document_owner_department_id,
        )
        normalized_access_rules = normalize_kb_access_rules(
            access_rules,
            kb_visibility=kb_visibility,
            owner_department_id=current.owner_department_id,
        )
        self._ensure_default_document_permission_within_kb_access(
            kb_visibility=kb_visibility,
            access_rules=normalized_access_rules,
            default_document_visibility=default_document_visibility,
            default_document_owner_department_id=default_document_owner.id,
        )
        permission_changed = (
            kb_visibility != current.kb_visibility
            or default_document_visibility != current.default_document_visibility
            or default_document_owner.id != current.default_document_owner_department_id
            or kb_access_rule_key(normalized_access_rules)
            != kb_access_rule_key(current.access_rules)
        )
        if not permission_changed:
            return PermissionKnowledgeBasePolicy(
                resource_type="knowledge_base",
                resource_id=current.id,
                kb_visibility=current.kb_visibility,
                default_document_visibility=current.default_document_visibility,
                default_document_owner_department_id=current.default_document_owner_department_id,
                access_rules=current.access_rules,
                permission_version=self.resource_writer.load_resource_permission_version(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="knowledge_base",
                    resource_id=current.id,
                ),
            )

        permission_tightened = kb_visibility_tightens(current.kb_visibility, kb_visibility)
        next_policy_version = current.policy_version + 1
        try:
            self.resource_writer.replace_knowledge_base_access_rules(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                access_rules=normalized_access_rules,
                actor_user_id=actor_user_id,
            )
            permission_version = self.resource_writer.bump_permission_version(
                session,
                enterprise_id,
            )
            policy_id = self.resource_writer.replace_resource_policy(
                session,
                enterprise_id=enterprise_id,
                resource_type="knowledge_base",
                resource_id=kb_id,
                owner_department_id=current.owner_department_id,
                visibility=kb_visibility_policy_visibility(kb_visibility),
                policy_version=next_policy_version,
                actor_user_id=actor_user_id,
            )
            snapshot = self.resource_writer.insert_permission_snapshot(
                session,
                enterprise_id=enterprise_id,
                resource_type="knowledge_base",
                resource_id=kb_id,
                owner_department_id=current.owner_department_id,
                visibility=kb_visibility_policy_visibility(kb_visibility),
                permission_version=permission_version,
                policy_version=next_policy_version,
                policy_id=policy_id,
            )
            refresh_job_id = self.refresh_job_writer.enqueue_permission_refresh_job(
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
            self._insert_audit_log(
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
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASE_PERMISSION_UPDATE_FAILED",
                "knowledge base permissions cannot be updated",
                exc,
            ) from exc
        return PermissionKnowledgeBasePolicy(
            resource_type="knowledge_base",
            resource_id=kb_id,
            kb_visibility=kb_visibility,
            default_document_visibility=default_document_visibility,
            default_document_owner_department_id=default_document_owner.id,
            access_rules=tuple(
                PermissionKnowledgeBaseAccessRule(
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
        actor_context: PermissionAdminActorContext | None = None,
    ) -> PermissionPolicy:
        """替换文档可见性和所属部门，并生成快照刷新任务。"""

        self._ensure_actor_can_manage_permissions(actor_context)
        if not confirmed:
            raise PermissionServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "replacing document permissions requires confirmation",
                status_code=428,
            )
        validate_visibility(visibility)
        current = self._load_document(session, doc_id, enterprise_id=enterprise_id)
        knowledge_base = self._load_knowledge_base(
            session,
            current.kb_id,
            enterprise_id=enterprise_id,
        )
        self._ensure_actor_can_access_knowledge_base(actor_context, knowledge_base)
        next_owner_department_id = current.owner_department_id
        if owner_department_id is not None:
            owner_department_id = owner_department_id.strip()
            if not owner_department_id:
                raise PermissionServiceError(
                    "ADMIN_DOCUMENT_INVALID",
                    "document owner department is required",
                    status_code=400,
                )
            next_owner_department_id = self._resolve_department(
                session,
                enterprise_id=enterprise_id,
                department_id=owner_department_id,
            ).id
        self._ensure_document_permission_within_parent_knowledge_base(
            knowledge_base=knowledge_base,
            document=current,
            next_visibility=visibility,
            next_owner_department_id=next_owner_department_id,
        )
        permission_changed = (
            next_owner_department_id != current.owner_department_id
            or visibility != current.visibility
        )
        if not permission_changed:
            return PermissionPolicy(
                resource_type="document",
                resource_id=current.id,
                visibility=current.visibility,
                permission_version=self.resource_writer.load_resource_permission_version(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="document",
                    resource_id=current.id,
                ),
            )

        permission_tightened = document_permission_tightens(
            previous_visibility=current.visibility,
            next_visibility=visibility,
            previous_owner_department_id=current.owner_department_id,
            next_owner_department_id=next_owner_department_id,
        )
        try:
            permission_version = self.resource_writer.bump_permission_version(
                session,
                enterprise_id,
            )
            next_policy_version = current.policy_version + 1
            policy_id = self.resource_writer.replace_resource_policy(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=doc_id,
                owner_department_id=next_owner_department_id,
                visibility=visibility,
                policy_version=next_policy_version,
                actor_user_id=actor_user_id,
            )
            snapshot = self.resource_writer.insert_permission_snapshot(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=doc_id,
                owner_department_id=next_owner_department_id,
                visibility=visibility,
                permission_version=permission_version,
                policy_version=next_policy_version,
                policy_id=policy_id,
            )
            access_block_id = None
            if permission_tightened:
                access_block_id = self.resource_writer.insert_access_block(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="document",
                    resource_id=doc_id,
                    reason="permission_tightened",
                    block_level="query",
                    actor_user_id=actor_user_id,
                    metadata={
                        "previous_visibility": current.visibility,
                        "next_visibility": visibility,
                        "previous_owner_department_id": current.owner_department_id,
                        "next_owner_department_id": next_owner_department_id,
                        "permission_version": permission_version,
                    },
                )
            refresh_job_id = self.refresh_job_writer.enqueue_permission_refresh_job(
                session,
                enterprise_id=enterprise_id,
                kb_id=current.kb_id,
                doc_id=doc_id,
                actor_user_id=actor_user_id,
                reason="document_permission_changed",
                permission_snapshot_id=snapshot["snapshot_id"],
                permission_version=permission_version,
            )
            session.execute(
                text(
                    """
                    UPDATE documents
                    SET owner_department_id = CAST(:owner_department_id AS uuid),
                        visibility = :visibility,
                        permission_snapshot_id = CAST(:permission_snapshot_id AS uuid),
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:doc_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                      AND lifecycle_status != 'deleted'
                    """
                ),
                {
                    "doc_id": doc_id,
                    "enterprise_id": enterprise_id,
                    "owner_department_id": next_owner_department_id,
                    "visibility": visibility,
                    "permission_snapshot_id": snapshot["snapshot_id"],
                    "actor_user_id": actor_user_id,
                },
            )
            visibility_expanded = visibility_expands(current.visibility, visibility)
            event_name, action, risk_level = document_permission_event(
                visibility_expanded=visibility_expanded,
                permission_tightened=permission_tightened,
            )
            self._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name=event_name,
                resource_type="document",
                resource_id=doc_id,
                action=action,
                result="success",
                risk_level=risk_level,
                summary={
                    "document_id": doc_id,
                    "kb_id": current.kb_id,
                    "before": {
                        "owner_department_id": current.owner_department_id,
                        "visibility": current.visibility,
                        "permission_snapshot_id": current.permission_snapshot_id,
                        "policy_version": current.policy_version,
                    },
                    "after": {
                        "owner_department_id": next_owner_department_id,
                        "visibility": visibility,
                        "permission_snapshot_id": snapshot["snapshot_id"],
                        "policy_version": next_policy_version,
                    },
                    "changed_fields": ["owner_department_id", "visibility"],
                    "permission_version": permission_version,
                    "permission_snapshot_id": snapshot["snapshot_id"],
                    "refresh_job_id": refresh_job_id,
                    "access_block_id": access_block_id,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_PERMISSION_UPDATE_FAILED",
                "document permissions cannot be updated",
                exc,
            ) from exc
        return PermissionPolicy(
            resource_type="document",
            resource_id=doc_id,
            visibility=visibility,
            permission_version=permission_version,
        )
