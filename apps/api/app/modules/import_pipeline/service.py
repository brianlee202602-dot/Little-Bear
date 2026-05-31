"""Import Service facade."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.import_pipeline import upload_validation as _upload_validation
from app.modules.import_pipeline.audit_writer import ImportAuditWriter
from app.modules.import_pipeline.command_service import ImportCommandService
from app.modules.import_pipeline.document_writer import ImportDocumentWriter
from app.modules.import_pipeline.executors import (
    DocumentChunker,
    DocumentCleaner,
    DocumentParser,
    HeadingParagraphChunker,
    MultiFormatDocumentParser,
    PlainTextCleaner,
)
from app.modules.import_pipeline.permission_guard import ImportPermissionGuard
from app.modules.import_pipeline.repository import ImportPipelineRepository
from app.modules.import_pipeline.retry_service import ImportRetryService
from app.modules.import_pipeline.schemas import (
    DocumentImportItem,
    ImportActorContext,
    ImportJob,
    ImportJobList,
)
from app.modules.import_pipeline.stage_runner import ImportStageRunner
from app.modules.import_pipeline.upload_validation import (
    CONTENT_TYPE_TO_FILE_TYPE,
    DEFAULT_ALLOWED_FILE_TYPES,
    DEFAULT_MAX_UPLOAD_BYTES,
    EXTENSION_TO_FILE_TYPE,
)
from app.modules.import_pipeline.worker_service import ImportWorkerService
from app.modules.indexing.runtime import build_indexing_service
from app.modules.storage.service import InMemoryObjectStorage, ObjectStorage
from sqlalchemy.orm import Session

IMPORT_STAGES = (
    "validate",
    "parse",
    "clean",
    "chunk",
    "embed",
    "index",
    "publish",
    "cleanup",
    "finished",
)
TERMINAL_STATUSES = {"success", "partial_success", "failed", "cancelled"}


class ImportService:
    """Facade for import API commands and worker state-machine workflows."""

    def __init__(
        self,
        *,
        object_storage: ObjectStorage | None = None,
        parser: DocumentParser | None = None,
        cleaner: DocumentCleaner | None = None,
        chunker: DocumentChunker | None = None,
        max_upload_bytes: int | None = None,
        allowed_file_types: tuple[str, ...] | None = None,
    ) -> None:
        self.object_storage = object_storage or InMemoryObjectStorage()
        self.parser = parser or MultiFormatDocumentParser()
        self.cleaner = cleaner or PlainTextCleaner()
        self.chunker = chunker or HeadingParagraphChunker()
        self.command_service = ImportCommandService(self)
        self.retry_service = ImportRetryService(self)
        self.repository = ImportPipelineRepository()
        self.document_writer = ImportDocumentWriter(object_storage=self.object_storage)
        self.permission_guard = ImportPermissionGuard()
        self.worker_service = ImportWorkerService(self)
        self.stage_runner = ImportStageRunner(self)
        self.audit_writer = ImportAuditWriter()
        self.max_upload_bytes = max_upload_bytes or DEFAULT_MAX_UPLOAD_BYTES
        self.allowed_file_types = _upload_validation.normalize_allowed_file_types(
            allowed_file_types or DEFAULT_ALLOWED_FILE_TYPES
        )

    def validate_upload_file(
        self,
        *,
        filename: str,
        content_type: str | None,
        size_bytes: int,
        file_index: int,
    ) -> str:
        return self.command_service.validate_upload_file(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            file_index=file_index,
        )

    def create_document_import(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        actor_user_id: str,
        job_type: str,
        items: list[DocumentImportItem],
        owner_department_id: str | None = None,
        visibility: str | None = None,
        folder_id: str | None = None,
        idempotency_key: str | None = None,
        actor_context: ImportActorContext | None = None,
    ) -> ImportJob:
        return self.command_service.create_document_import(
            session,
            enterprise_id=enterprise_id,
            kb_id=kb_id,
            actor_user_id=actor_user_id,
            job_type=job_type,
            items=items,
            owner_department_id=owner_department_id,
            visibility=visibility,
            folder_id=folder_id,
            idempotency_key=idempotency_key,
            actor_context=actor_context,
        )

    def get_import_job(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str | None = None,
        owner_only: bool = True,
    ) -> ImportJob:
        return self.command_service.get_import_job(
            session,
            job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )

    def list_import_jobs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        status: str | None = None,
        stage: str | None = None,
        kb_id: str | None = None,
        job_type: str | None = None,
        actor_user_id: str | None = None,
        owner_only: bool = True,
    ) -> ImportJobList:
        return self.command_service.list_import_jobs(
            session,
            enterprise_id=enterprise_id,
            page=page,
            page_size=page_size,
            status=status,
            stage=stage,
            kb_id=kb_id,
            job_type=job_type,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )

    def request_cancel(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str,
        owner_only: bool = True,
    ) -> ImportJob:
        return self.command_service.request_cancel(
            session,
            job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )

    def create_retry(
        self,
        session: Session,
        job_id: str,
        *,
        enterprise_id: str,
        actor_user_id: str,
        owner_only: bool = True,
    ) -> ImportJob:
        return self.retry_service.create_retry(
            session,
            job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )

    def create_index_job_retries(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        job_ids: list[str],
        owner_only: bool = False,
    ) -> ImportJobList:
        return self.retry_service.create_index_job_retries(
            session,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            job_ids=job_ids,
            owner_only=owner_only,
        )

    def claim_next_job(
        self,
        session: Session,
        *,
        worker_id: str,
        lock_seconds: int = 60,
        now: datetime | None = None,
    ) -> ImportJob | None:
        return self.worker_service.claim_next_job(
            session,
            worker_id=worker_id,
            lock_seconds=lock_seconds,
            now=now,
        )

    def advance_claimed_job(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
    ) -> ImportJob:
        return self.worker_service.advance_claimed_job(
            session,
            job_id=job_id,
            worker_id=worker_id,
        )

    def mark_claimed_job_failed(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        error_details: dict[str, Any] | None = None,
        retry_delay_seconds: int = 60,
    ) -> ImportJob:
        return self.worker_service.mark_claimed_job_failed(
            session,
            job_id=job_id,
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
            error_details=error_details,
            retry_delay_seconds=retry_delay_seconds,
        )

    def heartbeat_claimed_job(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        lock_seconds: int = 60,
    ) -> None:
        self.worker_service.heartbeat_claimed_job(
            session,
            job_id=job_id,
            worker_id=worker_id,
            lock_seconds=lock_seconds,
        )

    def _apply_stage_effect(self, session: Session, *, row: Any) -> None:
        original = self.stage_runner.indexing_service_factory
        self.stage_runner.indexing_service_factory = build_indexing_service
        try:
            self.stage_runner.apply_stage_effect(session, row=row)
        finally:
            self.stage_runner.indexing_service_factory = original

    def _create_retry_from_row(
        self,
        session: Session,
        *,
        row: Any,
        enterprise_id: str,
        actor_user_id: str,
        retried_from_job_id: str,
        risk_level: str = "medium",
        batch_job_ids: list[str] | None = None,
    ) -> ImportJob:
        return self.retry_service.create_retry_from_row(
            session,
            row=row,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            risk_level=risk_level,
            retried_from_job_id=retried_from_job_id,
            batch_job_ids=batch_job_ids,
        )

    def _mark_documents_indexing(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> None:
        self.stage_runner.mark_documents_indexing(session, request_json=request_json)

    def _mark_versions_parsed(
        self,
        session: Session,
        *,
        row: Any,
        request_json: dict[str, Any],
    ) -> None:
        self.stage_runner.mark_versions_parsed(session, row=row, request_json=request_json)

    def _mark_versions_cleaned(
        self,
        session: Session,
        *,
        row: Any,
        request_json: dict[str, Any],
    ) -> None:
        self.stage_runner.mark_versions_cleaned(session, row=row, request_json=request_json)

    def _write_draft_chunks(
        self,
        session: Session,
        *,
        row: Any,
        request_json: dict[str, Any] | None = None,
    ) -> None:
        self.stage_runner.write_draft_chunks(session, row=row, request_json=request_json)

    def _source_document_from_item(self, item: dict[str, Any]) -> Any:
        return self.stage_runner.source_document_from_item(item)

    def _item_stage_text(self, item: dict[str, Any], *, preferred_key: str) -> str:
        return self.stage_runner.item_stage_text(item, preferred_key=preferred_key)

    def _get_object(self, *, object_key: str, error_code: str) -> bytes:
        return self.stage_runner.get_object(object_key=object_key, error_code=error_code)

    def _put_text_object(self, *, object_key: str, text_content: str, error_code: str) -> None:
        self.stage_runner.put_text_object(
            object_key=object_key,
            text_content=text_content,
            error_code=error_code,
        )

    def _update_job_request_json(
        self,
        session: Session,
        *,
        job_id: str,
        request_json: dict[str, Any],
    ) -> None:
        self.stage_runner.update_job_request_json(
            session,
            job_id=job_id,
            request_json=request_json,
        )

    def _load_job_by_idempotency(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_user_id: str,
        idempotency_key: str,
    ) -> ImportJob | None:
        return self.repository.load_job_by_idempotency(
            session,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
        )

    def _load_permission_version(self, session: Session, enterprise_id: str) -> int:
        return self.repository.load_permission_version(session, enterprise_id)

    def _replace_resource_policy(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
        owner_department_id: str,
        visibility: str,
        policy_version: int,
        actor_user_id: str,
    ) -> str:
        return self.repository.replace_resource_policy(
            session,
            enterprise_id=enterprise_id,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_department_id=owner_department_id,
            visibility=visibility,
            policy_version=policy_version,
            actor_user_id=actor_user_id,
        )

    def _insert_permission_snapshot(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
        owner_department_id: str,
        visibility: str,
        permission_version: int,
        policy_version: int,
        policy_id: str,
    ) -> dict[str, str]:
        return self.repository.insert_permission_snapshot(
            session,
            enterprise_id=enterprise_id,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_department_id=owner_department_id,
            visibility=visibility,
            permission_version=permission_version,
            policy_version=policy_version,
            policy_id=policy_id,
        )

    def _insert_import_job(
        self,
        session: Session,
        *,
        enterprise_id: str,
        job_id: str,
        job_type: str,
        kb_id: str | None,
        document_id: str | None,
        document_version_id: str | None,
        request_json: dict[str, Any],
        idempotency_key: str | None,
        actor_user_id: str,
        initial_stage: str = "validate",
    ) -> None:
        self.repository.insert_import_job(
            session,
            enterprise_id=enterprise_id,
            job_id=job_id,
            job_type=job_type,
            kb_id=kb_id,
            document_id=document_id,
            document_version_id=document_version_id,
            request_json=request_json,
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            initial_stage=initial_stage,
        )

    def _load_import_job_row(
        self,
        session: Session,
        *,
        job_id: str,
        enterprise_id: str,
        actor_user_id: str | None,
        owner_only: bool,
    ) -> Any:
        return self.repository.load_import_job_row(
            session,
            job_id=job_id,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
            owner_only=owner_only,
        )

    def _job_enterprise_id(self, session: Session, job_id: str) -> str:
        return self.worker_service.job_enterprise_id(session, job_id)

    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        actor_id: str,
        event_name: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        risk_level: str,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        self.audit_writer.write_user_event(
            session,
            enterprise_id=enterprise_id,
            event_name=event_name,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            risk_level=risk_level,
            summary=summary,
            error_code=error_code,
        )

    def _insert_worker_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        event_name: str,
        resource_id: str,
        summary: dict[str, Any],
    ) -> None:
        self.worker_service.insert_worker_audit_log(
            session,
            enterprise_id=enterprise_id,
            event_name=event_name,
            resource_id=resource_id,
            summary=summary,
        )


__all__ = [
    "CONTENT_TYPE_TO_FILE_TYPE",
    "DEFAULT_ALLOWED_FILE_TYPES",
    "DEFAULT_MAX_UPLOAD_BYTES",
    "EXTENSION_TO_FILE_TYPE",
    "IMPORT_STAGES",
    "TERMINAL_STATUSES",
    "ImportService",
    "build_indexing_service",
]
