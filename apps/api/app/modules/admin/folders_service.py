"""Folder administration service."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.admin.access_control import AdminActorContext
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.events import _folder_update_event
from app.modules.admin.mappers import _folder_from_mapping, _folder_option_from_mapping
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminFolder,
    AdminFolderList,
    AdminFolderOptionList,
)
from app.modules.admin.utils import (
    _build_folder_path,
    _database_error,
    _folder_path_contains,
    _normalize_folder_name,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


class AdminFoldersService:
    """文件夹管理写模型。"""

    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_folders(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
        actor_context: AdminActorContext | None = None,
    ) -> AdminFolderList:
        """读取知识库内文件夹列表。"""

        self._core_service._ensure_actor_can_manage_folders(actor_context)
        knowledge_base = self._core_service.get_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        params = {
            "enterprise_id": enterprise_id,
            "kb_id": knowledge_base.id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS folder_id,
                        kb_id::text AS kb_id,
                        parent_id::text AS parent_id,
                        name,
                        path,
                        status
                    FROM folders
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = CAST(:kb_id AS uuid)
                      AND deleted_at IS NULL
                      AND status != 'deleted'
                    ORDER BY path, name
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM folders
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = CAST(:kb_id AS uuid)
                      AND deleted_at IS NULL
                      AND status != 'deleted'
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_FOLDERS_UNAVAILABLE",
                "folders cannot be read",
                exc,
            ) from exc
        return AdminFolderList(
            items=[_folder_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_folder_options(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminFolderOptionList:
        """读取文件夹选择器选项，避免下拉框复用完整文件夹 DTO。"""

        self._core_service._ensure_actor_can_manage_folders(actor_context)
        knowledge_base = self._core_service.get_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "enterprise_id = CAST(:enterprise_id AS uuid)",
            "kb_id = CAST(:kb_id AS uuid)",
            "deleted_at IS NULL",
            "status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "kb_id": knowledge_base.id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("name ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("status = :status")
            params["status"] = status
        where_sql = " AND ".join(conditions)
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS folder_id,
                        name,
                        status
                    FROM folders
                    WHERE {where_sql}
                    ORDER BY path, name
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM folders WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_FOLDER_OPTIONS_UNAVAILABLE",
                "folder options cannot be read",
                exc,
            ) from exc
        return AdminFolderOptionList(
            items=[_folder_option_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_folder(
        self,
        session: Session,
        folder_id: str,
        *,
        enterprise_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminFolder:
        folder = self._core_service._load_folder(
            session,
            folder_id,
            enterprise_id=enterprise_id,
        )
        self._core_service.get_knowledge_base(
            session,
            folder.kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        self._core_service._ensure_actor_can_manage_folders(actor_context)
        return folder

    def create_folder(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        kb_id: str,
        name: str,
        parent_id: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminFolder:
        self._core_service._ensure_actor_can_manage_folders(actor_context)
        knowledge_base = self._core_service.get_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        name = _normalize_folder_name(name)
        parent = self._core_service._resolve_parent_folder(
            session,
            enterprise_id=enterprise_id,
            kb_id=knowledge_base.id,
            parent_id=parent_id,
        )
        folder_id = str(uuid.uuid4())
        path = _build_folder_path(parent, folder_id)
        try:
            session.execute(
                text(
                    """
                    INSERT INTO folders(
                        id, enterprise_id, kb_id, parent_id, name, path,
                        policy_inherit_mode, status, created_by, updated_by
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid),
                        CAST(:kb_id AS uuid), CAST(:parent_id AS uuid),
                        :name, :path, 'inherit', 'active',
                        CAST(:actor_user_id AS uuid), CAST(:actor_user_id AS uuid)
                    )
                    """
                ),
                {
                    "id": folder_id,
                    "enterprise_id": enterprise_id,
                    "kb_id": knowledge_base.id,
                    "parent_id": parent.id if parent else None,
                    "name": name,
                    "path": path,
                    "actor_user_id": actor_user_id,
                },
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="folder.created",
                resource_type="folder",
                resource_id=folder_id,
                action="create",
                result="success",
                risk_level="low",
                summary={
                    "folder_id": folder_id,
                    "kb_id": knowledge_base.id,
                    "parent_id": parent.id if parent else None,
                    "name": name,
                },
            )
        except IntegrityError as exc:
            raise AdminServiceError(
                "ADMIN_FOLDER_CONFLICT",
                "folder already exists",
                status_code=409,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_FOLDER_CREATE_FAILED",
                "folder cannot be created",
                exc,
            ) from exc
        return AdminFolder(
            id=folder_id,
            kb_id=knowledge_base.id,
            parent_id=parent.id if parent else None,
            name=name,
            status="active",
            path=path,
        )

    def patch_folder(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        folder_id: str,
        name: str | None = None,
        parent_id: str | None = None,
        parent_id_provided: bool = False,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminFolder:
        self._core_service._ensure_actor_can_manage_folders(actor_context)
        current = self._core_service.get_folder(
            session,
            folder_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        updates: list[str] = []
        params: dict[str, Any] = {
            "folder_id": folder_id,
            "enterprise_id": enterprise_id,
            "actor_user_id": actor_user_id,
        }
        before = {
            "name": current.name,
            "parent_id": current.parent_id,
            "status": current.status,
            "path": current.path,
        }
        next_parent = None
        moved = parent_id is not None and parent_id != current.parent_id
        if name is not None:
            updates.append("name = :name")
            params["name"] = _normalize_folder_name(name)
        if status is not None:
            if status not in {"active", "disabled", "archived"}:
                raise AdminServiceError(
                    "ADMIN_FOLDER_STATUS_INVALID",
                    "folder status is invalid",
                    status_code=400,
                )
            updates.append("status = :status")
            params["status"] = status
        if parent_id_provided:
            if parent_id == folder_id:
                raise AdminServiceError(
                    "ADMIN_FOLDER_PARENT_INVALID",
                    "folder cannot be its own parent",
                    status_code=409,
                )
            next_parent = self._core_service._resolve_parent_folder(
                session,
                enterprise_id=enterprise_id,
                kb_id=current.kb_id,
                parent_id=parent_id,
            )
            if next_parent and _folder_path_contains(next_parent.path, folder_id):
                raise AdminServiceError(
                    "ADMIN_FOLDER_PARENT_INVALID",
                    "folder cannot be moved into its descendant",
                    status_code=409,
                )
            updates.append("parent_id = CAST(:parent_id AS uuid)")
            updates.append("path = :path")
            params["parent_id"] = next_parent.id if next_parent else None
            params["path"] = _build_folder_path(next_parent, folder_id)
        if not updates:
            return current

        try:
            session.execute(
                text(
                    f"""
                    UPDATE folders
                    SET {", ".join(updates)},
                        updated_by = CAST(:actor_user_id AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:folder_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                params,
            )
            after = self._core_service._load_folder(
                session,
                folder_id,
                enterprise_id=enterprise_id,
            )
            event_name, action, risk_level = _folder_update_event(
                before_status=current.status,
                after_status=after.status,
                moved=moved,
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name=event_name,
                resource_type="folder",
                resource_id=folder_id,
                action=action,
                result="success",
                risk_level=risk_level,
                summary={
                    "folder_id": folder_id,
                    "kb_id": current.kb_id,
                    "before": before,
                    "after": {
                        "name": after.name,
                        "parent_id": after.parent_id,
                        "status": after.status,
                        "path": after.path,
                    },
                    "changed_fields": [
                        field.split(" = ", 1)[0]
                        for field in updates
                        if field != "path = :path"
                    ],
                },
            )
        except IntegrityError as exc:
            raise AdminServiceError(
                "ADMIN_FOLDER_CONFLICT",
                "folder already exists",
                status_code=409,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_FOLDER_UPDATE_FAILED",
                "folder cannot be updated",
                exc,
            ) from exc
        return after

    def delete_folder(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        folder_id: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "deleting folder requires confirmation",
                status_code=428,
            )
        self._core_service._ensure_actor_can_manage_folders(actor_context)
        current = self._core_service.get_folder(
            session,
            folder_id,
            enterprise_id=enterprise_id,
            actor_context=actor_context,
        )
        try:
            document_impact_count = self._core_service._count_folder_documents(
                session,
                enterprise_id=enterprise_id,
                folder_id=folder_id,
            )
            access_block_id = self._core_service._insert_access_block(
                session,
                enterprise_id=enterprise_id,
                resource_type="folder",
                resource_id=folder_id,
                reason="deleted",
                block_level="all",
                actor_user_id=actor_user_id,
                metadata={"folder_id": folder_id, "kb_id": current.kb_id},
            )
            session.execute(
                text(
                    """
                    UPDATE folders
                    SET status = 'deleted',
                        deleted_at = now(),
                        updated_at = now(),
                        updated_by = CAST(:actor_user_id AS uuid)
                    WHERE id = CAST(:folder_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    """
                ),
                {
                    "folder_id": folder_id,
                    "enterprise_id": enterprise_id,
                    "actor_user_id": actor_user_id,
                },
            )
            cleanup_job_id = self._core_service._enqueue_index_delete_job(
                session,
                enterprise_id=enterprise_id,
                kb_id=current.kb_id,
                actor_user_id=actor_user_id,
                reason="folder_deleted",
                folder_id=folder_id,
            )
            self._core_service._insert_audit_log(
                session,
                enterprise_id=enterprise_id,
                actor_id=actor_user_id,
                event_name="folder.deleted",
                resource_type="folder",
                resource_id=folder_id,
                action="delete",
                result="success",
                risk_level="medium",
                summary={
                    "folder_id": folder_id,
                    "kb_id": current.kb_id,
                    "reason": "admin_deleted",
                    "access_block_id": access_block_id,
                    "cleanup_job_id": cleanup_job_id,
                    "document_impact_count": document_impact_count,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_FOLDER_DELETE_FAILED",
                "folder cannot be deleted",
                exc,
            ) from exc
        return AdminAcceptedResult(accepted=True, job_id=cleanup_job_id)
