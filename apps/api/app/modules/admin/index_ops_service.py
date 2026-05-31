"""Index operation administration service."""

from __future__ import annotations

from typing import Any

from app.modules.admin.access_control import AdminActorContext
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.schemas import AdminAcceptedResult
from app.modules.admin.utils import _database_error, _unique_strings
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminIndexOpsService:
    """索引运维任务管理写模型。"""

    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def create_document_index_rebuild_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        doc_id: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        """创建文档索引重建任务，复用当前 active document version 和 chunks。"""

        self._core_service._ensure_actor_can_index_documents(actor_context)
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "index rebuild requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: rebuild"},
            )
        document = self._core_service._load_document(
            session,
            doc_id,
            enterprise_id=enterprise_id,
        )
        knowledge_base = self._core_service._load_knowledge_base(
            session,
            document.kb_id,
            enterprise_id=enterprise_id,
        )
        self._core_service._ensure_actor_can_access_knowledge_base(
            actor_context,
            knowledge_base,
        )
        if document.lifecycle_status != "active" or document.current_version_id is None:
            raise AdminServiceError(
                "ADMIN_INDEX_REBUILD_UNAVAILABLE",
                "only active indexed documents can be rebuilt",
                status_code=409,
                details={
                    "doc_id": doc_id,
                    "lifecycle_status": document.lifecycle_status,
                    "current_version_id": document.current_version_id,
                },
            )
        job_id = self._core_service._enqueue_index_rebuild_job(
            session,
            enterprise_id=enterprise_id,
            kb_id=document.kb_id,
            doc_id=document.id,
            document_version_id=document.current_version_id,
            actor_user_id=actor_user_id,
        )
        try:
            session.execute(
                text(
                    """
                    UPDATE documents
                    SET index_status = 'indexing',
                        updated_at = now()
                    WHERE id = CAST(:doc_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                    """
                ),
                {"enterprise_id": enterprise_id, "doc_id": doc_id},
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_INDEX_REBUILD_DOCUMENT_UPDATE_FAILED",
                "document index rebuild state cannot be updated",
                exc,
            ) from exc
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="document.index_rebuild_requested",
            resource_type="document",
            resource_id=doc_id,
            action="index_rebuild",
            result="success",
            risk_level="high",
            summary={
                "job_id": job_id,
                "document_version_id": document.current_version_id,
            },
        )
        return AdminAcceptedResult(accepted=True, job_id=job_id)

    def create_index_rebuild_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        kb_id: str | None,
        document_ids: list[str],
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        """创建知识库级或指定文档集合的批量索引重建任务。"""

        self._core_service._ensure_actor_can_index_documents(actor_context)
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "index rebuild requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: rebuild"},
            )
        document_ids = _unique_strings(document_ids)
        if kb_id and document_ids:
            raise AdminServiceError(
                "ADMIN_INDEX_REBUILD_TARGET_CONFLICT",
                "index rebuild accepts either kb_id or document_ids, not both",
                status_code=400,
            )
        if kb_id:
            knowledge_base = self._core_service._load_knowledge_base(
                session,
                kb_id,
                enterprise_id=enterprise_id,
            )
            self._core_service._ensure_actor_can_access_knowledge_base(
                actor_context,
                knowledge_base,
            )
            targets = self._core_service._load_index_rebuild_targets_for_kb(
                session,
                enterprise_id=enterprise_id,
                kb_id=kb_id,
            )
            resource_type = "knowledge_base"
            resource_id = kb_id
        elif document_ids:
            targets = self._core_service._load_index_rebuild_targets_for_documents(
                session,
                enterprise_id=enterprise_id,
                document_ids=document_ids,
            )
            returned_ids = {target.document_id for target in targets}
            missing_ids = [
                document_id
                for document_id in document_ids
                if document_id not in returned_ids
            ]
            if missing_ids:
                raise AdminServiceError(
                    "ADMIN_INDEX_REBUILD_UNAVAILABLE",
                    "some documents cannot be rebuilt",
                    status_code=409,
                    details={"document_ids": missing_ids},
                )
            for target_kb_id in sorted({target.kb_id for target in targets}):
                knowledge_base = self._core_service._load_knowledge_base(
                    session,
                    target_kb_id,
                    enterprise_id=enterprise_id,
                )
                self._core_service._ensure_actor_can_access_knowledge_base(
                    actor_context,
                    knowledge_base,
                )
            resource_type = "document"
            resource_id = document_ids[0] if len(document_ids) == 1 else None
        else:
            raise AdminServiceError(
                "ADMIN_INDEX_REBUILD_TARGET_REQUIRED",
                "index rebuild requires kb_id or document_ids",
                status_code=400,
            )

        if not targets:
            raise AdminServiceError(
                "ADMIN_INDEX_REBUILD_TARGET_EMPTY",
                "no active documents can be rebuilt",
                status_code=409,
                details={"kb_id": kb_id, "document_ids": document_ids},
            )
        batch_kb_id = targets[0].kb_id if len({target.kb_id for target in targets}) == 1 else None
        job_id = self._core_service._enqueue_index_rebuild_batch_job(
            session,
            enterprise_id=enterprise_id,
            kb_id=batch_kb_id,
            targets=targets,
            actor_user_id=actor_user_id,
        )
        self._core_service._mark_index_rebuild_targets_indexing(
            session,
            enterprise_id=enterprise_id,
            document_ids=[target.document_id for target in targets],
        )
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="index_rebuild.batch_requested",
            resource_type=resource_type,
            resource_id=resource_id,
            action="index_rebuild",
            result="success",
            risk_level="high",
            summary={
                "job_id": job_id,
                "kb_id": batch_kb_id,
                "document_count": len(targets),
                "document_ids": [target.document_id for target in targets],
            },
        )
        return AdminAcceptedResult(accepted=True, job_id=job_id)

    def create_collection_index_rebuild_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        collection_name: str,
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        """按 Qdrant collection 创建批量索引重建任务。"""

        self._core_service._ensure_actor_can_index_documents(actor_context)
        collection_name = collection_name.strip()
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "collection index rebuild requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: rebuild"},
            )
        if not collection_name:
            raise AdminServiceError(
                "ADMIN_INDEX_COLLECTION_INVALID",
                "collection name is required",
                status_code=400,
            )
        targets = self._core_service._load_index_rebuild_targets_for_collection(
            session,
            enterprise_id=enterprise_id,
            collection_name=collection_name,
        )
        if not targets:
            raise AdminServiceError(
                "ADMIN_INDEX_REBUILD_TARGET_EMPTY",
                "no active documents can be rebuilt for collection",
                status_code=409,
                details={"collection_name": collection_name},
            )
        for target_kb_id in sorted({target.kb_id for target in targets}):
            knowledge_base = self._core_service._load_knowledge_base(
                session,
                target_kb_id,
                enterprise_id=enterprise_id,
            )
            self._core_service._ensure_actor_can_access_knowledge_base(
                actor_context,
                knowledge_base,
            )

        batch_kb_id = targets[0].kb_id if len({target.kb_id for target in targets}) == 1 else None
        job_id = self._core_service._enqueue_index_rebuild_batch_job(
            session,
            enterprise_id=enterprise_id,
            kb_id=batch_kb_id,
            targets=targets,
            actor_user_id=actor_user_id,
        )
        self._core_service._mark_index_rebuild_targets_indexing(
            session,
            enterprise_id=enterprise_id,
            document_ids=[target.document_id for target in targets],
        )
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="index_collection.rebuild_requested",
            resource_type="config",
            resource_id=collection_name,
            action="index_rebuild",
            result="success",
            risk_level="high",
            summary={
                "job_id": job_id,
                "collection_name": collection_name,
                "kb_id": batch_kb_id,
                "document_count": len(targets),
                "document_ids": [target.document_id for target in targets],
            },
        )
        return AdminAcceptedResult(accepted=True, job_id=job_id)

    def create_index_version_cleanup_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        index_version_ids: list[str],
        confirmed: bool,
        actor_context: AdminActorContext | None = None,
    ) -> AdminAcceptedResult:
        """创建按 index_version 精确清理 pending_delete 索引的运维任务。"""

        self._core_service._ensure_actor_can_index_documents(actor_context)
        if not confirmed:
            raise AdminServiceError(
                "ADMIN_CONFIRMATION_REQUIRED",
                "index cleanup requires confirmation",
                status_code=428,
                details={"required_header": "x-index-confirm: cleanup"},
            )
        normalized_ids = _unique_strings(index_version_ids)
        if not normalized_ids:
            raise AdminServiceError(
                "ADMIN_INDEX_CLEANUP_TARGET_REQUIRED",
                "index cleanup requires index_version_ids",
                status_code=400,
            )
        targets = self._core_service._load_index_cleanup_targets(
            session,
            enterprise_id=enterprise_id,
            index_version_ids=normalized_ids,
        )
        returned_ids = {target.index_version_id for target in targets}
        missing_ids = [
            index_version_id
            for index_version_id in normalized_ids
            if index_version_id not in returned_ids
        ]
        if missing_ids:
            raise AdminServiceError(
                "ADMIN_INDEX_CLEANUP_TARGET_INVALID",
                "some index versions cannot be cleaned",
                status_code=409,
                details={"index_version_ids": missing_ids},
            )
        for target_kb_id in sorted({target.kb_id for target in targets}):
            knowledge_base = self._core_service._load_knowledge_base(
                session,
                target_kb_id,
                enterprise_id=enterprise_id,
            )
            self._core_service._ensure_actor_can_access_knowledge_base(
                actor_context,
                knowledge_base,
            )

        batch_kb_id = (
            targets[0].kb_id if len({target.kb_id for target in targets}) == 1 else None
        )
        batch_document_id = (
            targets[0].document_id
            if len({target.document_id for target in targets}) == 1
            else None
        )
        batch_document_version_id = (
            targets[0].document_version_id
            if len({target.document_version_id for target in targets}) == 1
            else None
        )
        job_id = self._core_service._enqueue_index_version_cleanup_job(
            session,
            enterprise_id=enterprise_id,
            kb_id=batch_kb_id,
            document_id=batch_document_id,
            document_version_id=batch_document_version_id,
            index_version_ids=normalized_ids,
            actor_user_id=actor_user_id,
        )
        self._core_service._insert_audit_log(
            session,
            enterprise_id=enterprise_id,
            actor_id=actor_user_id,
            event_name="index_version.cleanup_requested",
            resource_type="document",
            resource_id=batch_document_id,
            action="index_cleanup",
            result="success",
            risk_level="high",
            summary={
                "job_id": job_id,
                "kb_id": batch_kb_id,
                "document_id": batch_document_id,
                "index_version_count": len(targets),
                "index_version_ids": normalized_ids,
                "collection_names": sorted({target.collection_name for target in targets}),
            },
        )
        return AdminAcceptedResult(accepted=True, job_id=job_id)
