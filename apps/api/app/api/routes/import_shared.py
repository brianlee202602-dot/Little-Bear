"""导入路由共享工具。"""

from __future__ import annotations

from functools import partial

from fastapi import UploadFile

from app.api.dependencies.auth import authenticate_required_scope as _authenticate
from app.api.dependencies.auth import current_request_id as _request_id
from app.api.dependencies.auth import extract_bearer_token as _extract_bearer_token
from app.api.errors import database_error_response, service_error_response
from app.api.schemas.import_pipeline import ImportJobData, ImportJobListItemData
from app.modules.auth.schemas import AuthContext
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import (
    DocumentImportItem,
    ImportActorContext,
    ImportJob,
)
from app.modules.import_pipeline.service import ImportService

_auth_error_response = service_error_response
_import_error_response = service_error_response
_database_error_response = partial(
    database_error_response,
    error_code="IMPORT_DATABASE_ERROR",
    message="import database operation failed",
)


def actor_context(auth_context: AuthContext) -> ImportActorContext:
    knowledge_base_ids = tuple(
        role.scope_id
        for role in auth_context.user.roles
        if role.scope_type == "knowledge_base" and role.scope_id
    )
    can_import_all_knowledge_bases = any(
        role.scope_type == "enterprise"
        and any(
            scope in {"*", "knowledge_base:*", "document:*", "document:import"}
            for scope in role.scopes
        )
        for role in auth_context.user.roles
    )
    return ImportActorContext(
        user_id=auth_context.user.id,
        scopes=auth_context.user.scopes,
        department_ids=tuple(department.id for department in auth_context.user.departments),
        role_ids=tuple(role.id for role in auth_context.user.roles),
        knowledge_base_ids=knowledge_base_ids,
        can_import_all_knowledge_bases=can_import_all_knowledge_bases,
    )


def job_data(job: ImportJob) -> ImportJobData:
    return ImportJobData(
        id=job.id,
        kb_id=job.kb_id,
        job_type=job.job_type,
        status=job.status,
        stage=job.stage,
        document_ids=list(job.document_ids),
        error_summary=job.error_summary,
    )


def job_list_item_data(job: ImportJob) -> ImportJobListItemData:
    return ImportJobListItemData(
        id=job.id,
        kb_id=job.kb_id,
        job_type=job.job_type,
        status=job.status,
        stage=job.stage,
        document_count=len(job.document_ids),
        error_summary=job.error_summary,
    )


async def upload_items(
    files: list[UploadFile],
    *,
    service: ImportService,
) -> list[DocumentImportItem]:
    if not files:
        raise ImportServiceError(
            "IMPORT_FILES_REQUIRED",
            "upload import requires at least one file",
            status_code=400,
        )
    items: list[DocumentImportItem] = []
    for index, upload in enumerate(files):
        content = await upload.read()
        if not content:
            raise ImportServiceError(
                "IMPORT_FILE_EMPTY",
                "uploaded file is empty",
                status_code=400,
                details={"file_index": index, "filename": upload.filename},
            )
        filename = upload.filename or f"document-{index + 1}.txt"
        file_type = service.validate_upload_file(
            filename=filename,
            content_type=upload.content_type,
            size_bytes=len(content),
            file_index=index,
        )
        items.append(
            DocumentImportItem(
                title=filename,
                object_content=content,
                content_type=upload.content_type,
                metadata={
                    "filename": filename,
                    "content_type": upload.content_type,
                    "file_type": file_type,
                    "size_bytes": len(content),
                },
            )
        )
    return items


_actor_context = actor_context
_job_data = job_data
_job_list_item_data = job_list_item_data
_upload_items = upload_items

__all__ = [
    "_actor_context",
    "_auth_error_response",
    "_authenticate",
    "_database_error_response",
    "_extract_bearer_token",
    "_import_error_response",
    "_job_data",
    "_job_list_item_data",
    "_request_id",
    "_upload_items",
]

