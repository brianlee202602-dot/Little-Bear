"""Document administration write service."""

# ruff: noqa: F401

from __future__ import annotations

from typing import Any

from app.modules.admin.access_control import AdminActorContext
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.events import (
    _changed_update_fields,
    _document_update_event,
)
from app.modules.admin.mappers import (
    _admin_chunk_from_mapping,
    _admin_index_version_from_mapping,
    _document_from_mapping,
    _document_version_from_mapping,
)
from app.modules.admin.policies import (
    _document_permission_tightens,
    _validate_visibility,
    _visibility_expands,
)
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminChunkList,
    AdminDocument,
    AdminDocumentList,
    AdminDocumentPreview,
    AdminDocumentPreviewChunk,
    AdminDocumentVersionList,
    AdminIndexVersionList,
)
from app.modules.admin.utils import (
    _database_error,
    _json_mapping,
    _normalize_tags,
    _optional_int,
    _optional_str,
)
from app.modules.permissions.errors import PermissionServiceError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminDocumentWriter:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def patch_document(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        doc_id: str,
        title: str | None = None,
        folder_id: str | None = None,
        folder_id_provided: bool = False,
        tags: list[str] | None = None,
        tags_provided: bool = False,
        owner_department_id: str | None = None,
        visibility: str | None = None,
        lifecycle_status: str | None = None,
        confirmed_visibility_expand: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminDocument:
        """更新文档元数据；权限字段变更会生成策略、快照和刷新任务。"""

        self._core_service._ensure_actor_can_manage_documents(actor_context)
        current = self._core_service.get_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        updates: list[str] = []
        params: dict[str, Any] = {
            "doc_id": doc_id,
            "enterprise_id": enterprise_id,
            "actor_user_id": actor_user_id,
        }
        before = {
            "title": current.title,
            "folder_id": current.folder_id,
            "tags": list(current.tags),
            "lifecycle_status": current.lifecycle_status,
            "index_status": current.index_status,
            "owner_department_id": current.owner_department_id,
            "visibility": current.visibility,
            "permission_snapshot_id": current.permission_snapshot_id,
            "policy_version": current.policy_version,
        }

        if title is not None:
            normalized_title = title.strip()
            if not normalized_title:
                raise AdminServiceError(
                    "ADMIN_DOCUMENT_INVALID",
                    "document title is required",
                    status_code=400,
                )
            updates.append("title = :title")
            params["title"] = normalized_title
        if folder_id_provided:
            folder = self._core_service._resolve_document_folder(
                session,
                enterprise_id=enterprise_id,
                kb_id=current.kb_id,
                folder_id=folder_id,
            )
            updates.append("folder_id = CAST(:folder_id AS uuid)")
            params["folder_id"] = folder.id if folder else None
        if tags_provided:
            updates.append("tags = CAST(:tags AS text[])")
            params["tags"] = _normalize_tags(tags or [])
        if lifecycle_status is not None:
            if lifecycle_status == "deleted":
                raise AdminServiceError(
                    "ADMIN_DOCUMENT_STATUS_INVALID",
                    "use DELETE to remove documents",
                    status_code=409,
                    details={"lifecycle_status": lifecycle_status},
                )
            if lifecycle_status not in {"active", "archived"}:
                raise AdminServiceError(
                    "ADMIN_DOCUMENT_STATUS_INVALID",
                    "document lifecycle status is invalid",
                    status_code=400,
                    details={"lifecycle_status": lifecycle_status},
                )
            updates.append("lifecycle_status = :lifecycle_status")
            params["lifecycle_status"] = lifecycle_status

        next_owner_department_id = current.owner_department_id
        if owner_department_id is not None:
            owner_department_id = owner_department_id.strip()
            if not owner_department_id:
                raise AdminServiceError(
                    "ADMIN_DOCUMENT_INVALID",
                    "document owner department is required",
                    status_code=400,
                )
            owner_department = self._core_service._resolve_department(
                session,
                enterprise_id=enterprise_id,
                department_id=owner_department_id,
            )
            self._core_service._ensure_actor_can_manage_document_owner(
                actor_context,
                kb_id=current.kb_id,
                owner_department_id=owner_department.id,
            )
            next_owner_department_id = owner_department.id
            updates.append("owner_department_id = CAST(:owner_department_id AS uuid)")
            params["owner_department_id"] = owner_department.id

        next_visibility = current.visibility
        if visibility is not None:
            try:
                _validate_visibility(visibility)
            except PermissionServiceError as exc:
                raise AdminServiceError(
                    exc.error_code,
                    exc.message,
                    status_code=exc.status_code,
                    retryable=exc.retryable,
                    details=exc.details,
                ) from exc
            next_visibility = visibility
            if (
                _visibility_expands(current.visibility, next_visibility)
                and not confirmed_visibility_expand
            ):
                raise AdminServiceError(
                    "ADMIN_CONFIRMATION_REQUIRED",
                    "expanding document visibility requires confirmation",
                    status_code=428,
                    details={
                        "previous_visibility": current.visibility,
                        "next_visibility": next_visibility,
                    },
                )
            updates.append("visibility = :visibility")
            params["visibility"] = next_visibility

        permission_changed = (
            next_owner_department_id != current.owner_department_id
            or next_visibility != current.visibility
        )
        if permission_changed:
            self._core_service._ensure_document_permission_within_parent_knowledge_base(
                session,
                enterprise_id=enterprise_id,
                document=current,
                next_visibility=next_visibility,
                next_owner_department_id=next_owner_department_id,
            )
        permission_tightened = _document_permission_tightens(
            previous_visibility=current.visibility,
            next_visibility=next_visibility,
            previous_owner_department_id=current.owner_department_id,
            next_owner_department_id=next_owner_department_id,
        )
        if permission_changed:
            updates.append("permission_snapshot_id = CAST(:permission_snapshot_id AS uuid)")
        if not updates:
            return current

        try:
            permission_version = None
            snapshot_id = None
            refresh_job_id = None
            access_block_id = None
            next_policy_version = current.policy_version
            if permission_changed:
                permission_version = self._core_service._bump_permission_version(
                    session,
                    enterprise_id,
                )
                next_policy_version = current.policy_version + 1
                policy_id = self._core_service._replace_resource_policy(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="document",
                    resource_id=doc_id,
                    owner_department_id=next_owner_department_id,
                    visibility=next_visibility,
                    policy_version=next_policy_version,
                    actor_user_id=actor_user_id,
                )
                snapshot = self._core_service._insert_permission_snapshot(
                    session,
                    enterprise_id=enterprise_id,
                    resource_type="document",
                    resource_id=doc_id,
                    owner_department_id=next_owner_department_id,
                    visibility=next_visibility,
                    permission_version=permission_version,
                    policy_version=next_policy_version,
                    policy_id=policy_id,
                )
                snapshot_id = snapshot["snapshot_id"]
                params["permission_snapshot_id"] = snapshot_id
                if permission_tightened:
                    access_block_id = self._core_service._insert_access_block(
                        session,
                        enterprise_id=enterprise_id,
                        resource_type="document",
                        resource_id=doc_id,
                        reason="permission_tightened",
                        block_level="query",
                        actor_user_id=actor_user_id,
                        metadata={
                            "previous_visibility": current.visibility,
                            "next_visibility": next_visibility,
                            "previous_owner_department_id": current.owner_department_id,
                            "next_owner_department_id": next_owner_department_id,
                            "permission_version": permission_version,
                        },
                    )
                refresh_job_id = self._core_service._enqueue_permission_refresh_job(
                    session,
                    enterprise_id=enterprise_id,
                    kb_id=current.kb_id,
                    doc_id=doc_id,
                    actor_user_id=actor_user_id,
                    reason="document_permission_changed",
                    permission_snapshot_id=snapshot_id,
                    permission_version=permission_version,
                )
            session.execute(
                text(
                    f"""
                    UPDATE documents
                    SET {", ".join(updates)},
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:doc_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                      AND lifecycle_status != 'deleted'
                    """
                ),
                params,
            )
            after = self._core_service._load_document(
                session,
                doc_id,
                enterprise_id=enterprise_id,
            )
            event_name, action, risk_level = _document_update_event(
                before_status=current.lifecycle_status,
                after_status=after.lifecycle_status,
                visibility_expanded=_visibility_expands(current.visibility, next_visibility),
                permission_tightened=permission_tightened,
            )
            self._core_service._insert_audit_log(
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
                    "before": before,
                    "after": {
                        "title": after.title,
                        "folder_id": after.folder_id,
                        "tags": list(after.tags),
                        "lifecycle_status": after.lifecycle_status,
                        "index_status": after.index_status,
                        "owner_department_id": after.owner_department_id,
                        "visibility": after.visibility,
                        "permission_snapshot_id": after.permission_snapshot_id,
                        "policy_version": after.policy_version,
                    },
                    "changed_fields": _changed_update_fields(updates),
                    "visibility": after.visibility,
                    "owner_department_id": after.owner_department_id,
                    "permission_version": permission_version,
                    "permission_snapshot_id": snapshot_id,
                    "refresh_job_id": refresh_job_id,
                    "access_block_id": access_block_id,
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
                "ADMIN_DOCUMENT_UPDATE_FAILED",
                "document cannot be updated",
                exc,
            ) from exc
        return after

    def delete_document(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        doc_id: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "deleting document requires confirmation",
                status_code=428,
            )
        self._core_service._ensure_actor_can_manage_documents(actor_context)
        current = self._core_service.get_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        try:
            access_block_id = self._core_service._insert_access_block(
                session,
                enterprise_id=enterprise_id,
                resource_type="document",
                resource_id=doc_id,
                reason="deleted",
                block_level="all",
                actor_user_id=actor_user_id,
                metadata={"document_id": doc_id, "kb_id": current.kb_id},
            )
            session.execute(
                text(
                    """
                    UPDATE documents
                    SET lifecycle_status = 'deleted',
                        index_status = 'blocked',
                        deleted_at = now(),
                        updated_at = now(),
                        updated_by = CAST(:actor_user_id AS uuid)
                    WHERE id = CAST(:doc_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                      AND lifecycle_status != 'deleted'
                    """
                ),
                {
                    "doc_id": doc_id,
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
                      AND resource_type = 'document'
                      AND resource_id = CAST(:doc_id AS uuid)
                      AND status = 'active'
                    """
                ),
                {"enterprise_id": enterprise_id, "doc_id": doc_id},
            )
            permission_version = self._core_service._bump_permission_version(
                session,
                enterprise_id,
            )
            cleanup_job_id = self._core_service._enqueue_index_delete_job(
                session,
                enterprise_id=enterprise_id,
                kb_id=current.kb_id,
                actor_user_id=actor_user_id,
                reason="document_deleted",
                document_id=doc_id,
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="document.deleted",
                resource_type="document",
                resource_id=doc_id,
                action="delete",
                result="success",
                risk_level="critical",
                summary={
                    "document_id": doc_id,
                    "kb_id": current.kb_id,
                    "reason": "admin_deleted",
                    "access_block_id": access_block_id,
                    "cleanup_job_id": cleanup_job_id,
                    "content_hash": current.content_hash,
                    "permission_version": permission_version,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_DELETE_FAILED",
                "document cannot be deleted",
                exc,
            ) from exc
        return AdminAcceptedResult(accepted=True, job_id=cleanup_job_id)

