"""Knowledge-base administration write service."""

# ruff: noqa: F401

from __future__ import annotations

import uuid
from typing import Any

from app.modules.admin.access_control import (
    AdminActorContext,
    actor_can_manage_all_knowledge_bases,
    actor_kb_manage_acl_sql,
)
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.events import _knowledge_base_update_event
from app.modules.admin.mappers import (
    _knowledge_base_list_item_from_mapping,
    _knowledge_base_option_from_mapping,
)
from app.modules.admin.policies import (
    _kb_access_rule_key,
    _kb_visibility_expands,
    _kb_visibility_policy_visibility,
    _normalize_kb_access_rules,
    _validate_kb_visibility,
    _validate_visibility,
)
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminKnowledgeBase,
    AdminKnowledgeBaseAccessRule,
    AdminKnowledgeBaseAccessRuleInput,
    AdminKnowledgeBaseList,
    AdminKnowledgeBaseOptionList,
)
from app.modules.admin.utils import _database_error
from app.modules.permissions.errors import PermissionServiceError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


class AdminKnowledgeBaseWriter:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def create_knowledge_base(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        name: str,
        owner_department_id: str,
        kb_visibility: str,
        default_document_visibility: str,
        default_document_owner_department_id: str | None = None,
        access_rules: list[AdminKnowledgeBaseAccessRuleInput] | None = None,
        config_scope_id: str | None = None,
        confirmed_enterprise_visibility: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminKnowledgeBase:
        """创建知识库，并同步写入 P0 可见性策略与权限快照。"""

        self._core_service._ensure_actor_can_manage_knowledge_bases(actor_context)
        name = name.strip()
        owner_department_id = owner_department_id.strip()
        config_scope_id = config_scope_id.strip() if config_scope_id else None
        if not name or not owner_department_id:
            raise AdminServiceError(
                "ADMIN_KNOWLEDGE_BASE_INVALID",
                "knowledge base name and owner department are required",
                status_code=400,
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
        if kb_visibility == "enterprise" and not confirmed_enterprise_visibility:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "enterprise visible knowledge base requires confirmation",
                status_code=428,
                details={"kb_visibility": kb_visibility},
            )

        owner_department = self._core_service._resolve_department(
            session,
            enterprise_id=enterprise_id,
            department_id=owner_department_id,
        )
        self._core_service._ensure_actor_can_manage_kb_owner(
            actor_context,
            owner_department.id,
        )
        default_document_owner = self._core_service._resolve_department(
            session,
            enterprise_id=enterprise_id,
            department_id=default_document_owner_department_id or owner_department.id,
        )
        normalized_access_rules = _normalize_kb_access_rules(
            access_rules or [],
            kb_visibility=kb_visibility,
            owner_department_id=owner_department.id,
        )
        self._core_service._ensure_default_document_permission_within_kb_access(
            kb_visibility=kb_visibility,
            access_rules=normalized_access_rules,
            default_document_visibility=default_document_visibility,
            default_document_owner_department_id=default_document_owner.id,
        )

        kb_id = str(uuid.uuid4())
        policy_version = 1
        try:
            session.execute(
                text(
                    """
                    INSERT INTO knowledge_bases(
                        id, enterprise_id, name, status, owner_department_id,
                        kb_visibility, default_document_visibility,
                        default_document_owner_department_id, policy_version, config_scope_id,
                        created_by, updated_by
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :name, 'active',
                        CAST(:owner_department_id AS uuid), :kb_visibility,
                        :default_document_visibility,
                        CAST(:default_document_owner_department_id AS uuid), :policy_version,
                        :config_scope_id, CAST(:actor_user_id AS uuid),
                        CAST(:actor_user_id AS uuid)
                    )
                    """
                ),
                {
                    "id": kb_id,
                    "enterprise_id": enterprise_id,
                    "name": name,
                    "owner_department_id": owner_department.id,
                    "kb_visibility": kb_visibility,
                    "default_document_visibility": default_document_visibility,
                    "default_document_owner_department_id": default_document_owner.id,
                    "policy_version": policy_version,
                    "config_scope_id": config_scope_id,
                    "actor_user_id": actor_user_id,
                },
            )
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
                owner_department_id=owner_department.id,
                visibility=_kb_visibility_policy_visibility(kb_visibility),
                policy_version=policy_version,
                actor_user_id=actor_user_id,
            )
            snapshot = self._core_service._insert_permission_snapshot(
                session,
                enterprise_id=enterprise_id,
                resource_type="knowledge_base",
                resource_id=kb_id,
                owner_department_id=owner_department.id,
                visibility=_kb_visibility_policy_visibility(kb_visibility),
                permission_version=permission_version,
                policy_version=policy_version,
                policy_id=policy_id,
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="knowledge_base.created",
                resource_type="knowledge_base",
                resource_id=kb_id,
                action="create",
                result="success",
                risk_level="medium",
                summary={
                    "kb_id": kb_id,
                    "name": name,
                    "kb_visibility": kb_visibility,
                    "default_document_visibility": default_document_visibility,
                    "default_document_owner_department_id": default_document_owner.id,
                    "access_rules": [rule.__dict__ for rule in normalized_access_rules],
                    "owner_department_id": owner_department.id,
                    "permission_version": permission_version,
                    "policy_version": policy_version,
                    "permission_snapshot_id": snapshot["snapshot_id"],
                },
            )
        except IntegrityError as exc:
            raise AdminServiceError(
                "ADMIN_KNOWLEDGE_BASE_CONFLICT",
                "knowledge base already exists",
                status_code=409,
                details={"error_type": exc.__class__.__name__},
            ) from exc
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
                "ADMIN_KNOWLEDGE_BASE_CREATE_FAILED",
                "knowledge base cannot be created",
                exc,
            ) from exc

        return AdminKnowledgeBase(
            id=kb_id,
            name=name,
            status="active",
            owner_department_id=owner_department.id,
            kb_visibility=kb_visibility,
            default_document_visibility=default_document_visibility,
            default_document_owner_department_id=default_document_owner.id,
            owner_department=owner_department,
            default_document_owner_department=default_document_owner,
            config_scope_id=config_scope_id,
            policy_version=policy_version,
            access_rules=tuple(
                AdminKnowledgeBaseAccessRule(
                    subject_type=rule.subject_type,
                    subject_id=rule.subject_id,
                    permission=rule.permission,
                )
                for rule in normalized_access_rules
            ),
        )

    def patch_knowledge_base(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        kb_id: str,
        name: str | None = None,
        status: str | None = None,
        kb_visibility: str | None = None,
        default_document_visibility: str | None = None,
        default_document_owner_department_id: str | None = None,
        config_scope_id: str | None = None,
        confirmed_visibility_expand: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminKnowledgeBase:
        """更新知识库基础信息；可见性变更会同步权限策略和快照。"""

        self._core_service._ensure_actor_can_manage_knowledge_bases(actor_context)
        current = self._core_service.get_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        updates: list[str] = []
        params: dict[str, Any] = {
            "kb_id": kb_id,
            "enterprise_id": enterprise_id,
            "actor_user_id": actor_user_id,
        }
        before = {
            "name": current.name,
            "status": current.status,
            "kb_visibility": current.kb_visibility,
            "default_document_visibility": current.default_document_visibility,
            "default_document_owner_department_id": current.default_document_owner_department_id,
            "owner_department_id": current.owner_department_id,
            "access_rules": [rule.__dict__ for rule in current.access_rules],
            "config_scope_id": current.config_scope_id,
            "policy_version": current.policy_version,
        }

        if name is not None:
            name = name.strip()
            if not name:
                raise AdminServiceError(
                    "ADMIN_KNOWLEDGE_BASE_INVALID",
                    "knowledge base name is required",
                    status_code=400,
                )
            updates.append("name = :name")
            params["name"] = name
        if status is not None:
            if status not in {"active", "disabled", "archived"}:
                raise AdminServiceError(
                    "ADMIN_KNOWLEDGE_BASE_STATUS_INVALID",
                    "knowledge base status is invalid",
                    status_code=400,
                )
            updates.append("status = :status")
            params["status"] = status
        next_kb_visibility = current.kb_visibility
        if kb_visibility is not None:
            _validate_kb_visibility(kb_visibility)
            next_kb_visibility = kb_visibility
        next_default_document_visibility = current.default_document_visibility
        if default_document_visibility is not None:
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
            next_default_document_visibility = default_document_visibility
        next_default_document_owner_department_id = current.default_document_owner_department_id
        if default_document_owner_department_id is not None:
            next_default_document_owner_department_id = (
                self._core_service._resolve_department(
                    session,
                    enterprise_id=enterprise_id,
                    department_id=default_document_owner_department_id,
                ).id
            )

        visibility_changed = next_kb_visibility != current.kb_visibility
        default_document_permission_changed = (
            next_default_document_visibility != current.default_document_visibility
            or next_default_document_owner_department_id
            != current.default_document_owner_department_id
        )
        effective_access_rules = current.access_rules
        if next_kb_visibility != "enterprise":
            effective_access_rules = _normalize_kb_access_rules(
                [
                    AdminKnowledgeBaseAccessRuleInput(
                        subject_type=rule.subject_type,
                        subject_id=rule.subject_id,
                        permission=rule.permission,
                    )
                    for rule in current.access_rules
                ],
                kb_visibility=next_kb_visibility,
                owner_department_id=current.owner_department_id,
            )
        access_rules_changed = (
            _kb_access_rule_key(effective_access_rules)
            != _kb_access_rule_key(current.access_rules)
        )
        next_policy_version = current.policy_version
        if kb_visibility is not None:
            if (
                visibility_changed
                and _kb_visibility_expands(current.kb_visibility, next_kb_visibility)
                and not confirmed_visibility_expand
            ):
                raise AdminServiceError(
                    "ADMIN_CONFIRMATION_REQUIRED",
                    "expanding knowledge base visibility requires confirmation",
                    status_code=428,
                    details={
                        "previous_visibility": current.kb_visibility,
                        "next_visibility": next_kb_visibility,
                    },
                )
            updates.append("kb_visibility = :kb_visibility")
            params["kb_visibility"] = next_kb_visibility
            if visibility_changed:
                next_policy_version = current.policy_version + 1
                updates.append("policy_version = :policy_version")
                params["policy_version"] = next_policy_version
        if default_document_visibility is not None:
            updates.append("default_document_visibility = :default_document_visibility")
            params["default_document_visibility"] = next_default_document_visibility
        if default_document_owner_department_id is not None:
            updates.append(
                "default_document_owner_department_id = "
                "CAST(:default_document_owner_department_id AS uuid)"
            )
            params["default_document_owner_department_id"] = (
                next_default_document_owner_department_id
            )
        if visibility_changed or default_document_permission_changed:
            self._core_service._ensure_default_document_permission_within_kb_access(
                kb_visibility=next_kb_visibility,
                access_rules=effective_access_rules,
                default_document_visibility=next_default_document_visibility,
                default_document_owner_department_id=next_default_document_owner_department_id,
            )
        if config_scope_id is not None:
            config_scope_id = config_scope_id.strip() or None
            updates.append("config_scope_id = :config_scope_id")
            params["config_scope_id"] = config_scope_id
        if not updates:
            return current

        try:
            session.execute(
                text(
                    f"""
                    UPDATE knowledge_bases
                    SET {", ".join(updates)},
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:kb_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                params,
            )
            permission_version = self._core_service._bump_permission_version(
                session,
                enterprise_id,
            )
            snapshot_id = None
            refresh_job_id = None
            if access_rules_changed:
                self._core_service._replace_knowledge_base_access_rules(
                    session,
                    enterprise_id=enterprise_id,
                    kb_id=kb_id,
                    access_rules=effective_access_rules,
                    actor_user_id=actor_user_id,
                )
            if visibility_changed:
                policy_id = self._core_service._replace_resource_policy(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="knowledge_base",
                    resource_id=kb_id,
                    owner_department_id=current.owner_department_id,
                    visibility=_kb_visibility_policy_visibility(next_kb_visibility),
                    policy_version=next_policy_version,
                    actor_user_id=actor_user_id,
                )
                snapshot = self._core_service._insert_permission_snapshot(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="knowledge_base",
                    resource_id=kb_id,
                    owner_department_id=current.owner_department_id,
                    visibility=_kb_visibility_policy_visibility(next_kb_visibility),
                    permission_version=permission_version,
                    policy_version=next_policy_version,
                    policy_id=policy_id,
                )
                snapshot_id = snapshot["snapshot_id"]
                refresh_job_id = self._core_service._enqueue_permission_refresh_job(
                    session,
                    enterprise_id=enterprise_id,
                    kb_id=kb_id,
                    doc_id=None,
                    actor_user_id=actor_user_id,
                    reason="knowledge_base_permission_changed",
                    permission_snapshot_id=snapshot_id,
                    permission_version=permission_version,
                    resource_type="knowledge_base",
                )
            after = self._core_service._load_knowledge_base(
                session,
                kb_id,
                enterprise_id=enterprise_id,
            )
            event_name, action, risk_level = _knowledge_base_update_event(
                before_status=current.status,
                after_status=after.status,
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name=event_name,
                resource_type="knowledge_base",
                resource_id=kb_id,
                action=action,
                result="success",
                risk_level=risk_level,
                summary={
                    "kb_id": kb_id,
                    "before": before,
                    "after": {
                        "name": after.name,
                        "status": after.status,
                        "kb_visibility": after.kb_visibility,
                        "default_document_visibility": after.default_document_visibility,
                        "default_document_owner_department_id": (
                            after.default_document_owner_department_id
                        ),
                        "owner_department_id": after.owner_department_id,
                        "access_rules": [rule.__dict__ for rule in after.access_rules],
                        "config_scope_id": after.config_scope_id,
                        "policy_version": after.policy_version,
                    },
                    "changed_fields": [
                        field.split(" = ", 1)[0]
                        for field in updates
                        if field != "policy_version = :policy_version"
                    ],
                    "permission_version": permission_version,
                    "permission_snapshot_id": snapshot_id,
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
                "ADMIN_KNOWLEDGE_BASE_UPDATE_FAILED",
                "knowledge base cannot be updated",
                exc,
            ) from exc
        return after

    def delete_knowledge_base(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        kb_id: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        """先阻断知识库查询，再软删除并创建异步索引删除任务。"""

        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "deleting knowledge base requires confirmation",
                status_code=428,
            )
        self._core_service._ensure_actor_can_manage_knowledge_bases(actor_context)
        current = self._core_service.get_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        try:
            access_block_id = self._core_service._insert_access_block(
                session,
                enterprise_id=enterprise_id,
                resource_type="knowledge_base",
                resource_id=kb_id,
                reason="deleted",
                block_level="all",
                actor_user_id=actor_user_id,
                metadata={"kb_id": kb_id, "name": current.name},
            )
            session.execute(
                text(
                    """
                    UPDATE knowledge_bases
                    SET status = 'deleted',
                        deleted_at = now(),
                        updated_at = now(),
                        updated_by = CAST(:actor_user_id AS uuid)
                    WHERE id = CAST(:kb_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                {
                    "kb_id": kb_id,
                    "enterprise_id": enterprise_id,
                    "actor_user_id": actor_user_id,
                },
            )
            session.execute(
                text(
                    """
                    UPDATE resource_policies
                    SET status = 'archived', archived_at = now()
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND resource_type = 'knowledge_base'
                      AND resource_id = CAST(:kb_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {"enterprise_id": enterprise_id, "kb_id": kb_id},
            )
            permission_version = self._core_service._bump_permission_version(
                session,
                enterprise_id,
            )
            cleanup_job_id = self._core_service._enqueue_index_delete_job(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
                actor_user_id=actor_user_id,
                reason="knowledge_base_deleted",
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="knowledge_base.deleted",
                resource_type="knowledge_base",
                resource_id=kb_id,
                action="delete",
                result="success",
                risk_level="critical",
                summary={
                    "kb_id": kb_id,
                    "name": current.name,
                    "reason": "admin_deleted",
                    "access_block_id": access_block_id,
                    "cleanup_job_id": cleanup_job_id,
                    "permission_version": permission_version,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASE_DELETE_FAILED",
                "knowledge base cannot be deleted",
                exc,
            ) from exc
        return AdminAcceptedResult(accepted=True, job_id=cleanup_job_id)

