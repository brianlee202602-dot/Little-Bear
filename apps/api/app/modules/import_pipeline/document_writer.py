"""Import document persistence helpers."""

from __future__ import annotations

from app.modules.import_pipeline import request_items as _request_helpers
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import DocumentImportItem
from app.modules.storage.service import ObjectStorage
from sqlalchemy import text
from sqlalchemy.orm import Session


class ImportDocumentWriter:
    """Persists pre-created import documents and source objects."""

    def __init__(
        self,
        *,
        object_storage: ObjectStorage,
    ) -> None:
        self.object_storage = object_storage

    def store_upload_object(
        self,
        *,
        enterprise_id: str,
        kb_id: str,
        document_id: str,
        actor_user_id: str,
        item: DocumentImportItem,
    ) -> str:
        if item.object_content is None:
            raise ImportServiceError(
                "IMPORT_OBJECT_CONTENT_REQUIRED",
                "upload import item requires raw object content",
                status_code=400,
                details={"title": item.title},
            )
        object_key = _build_upload_object_key(
            enterprise_id=enterprise_id,
            kb_id=kb_id,
            document_id=document_id,
            filename=_request_helpers.metadata_filename(item.metadata) or item.title,
        )
        try:
            self.object_storage.put_object(
                object_key=object_key,
                content=item.object_content,
                content_type=item.content_type,
            )
        except Exception as exc:
            raise ImportServiceError(
                "IMPORT_OBJECT_STORE_FAILED",
                "upload source object cannot be stored",
                status_code=503,
                retryable=True,
                details={
                    "document_id": document_id,
                    "kb_id": kb_id,
                    "filename": _request_helpers.metadata_filename(item.metadata) or item.title,
                    "actor_user_id": actor_user_id,
                },
            ) from exc
        return object_key

    def insert_document(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        folder_id: str | None,
        document_id: str,
        title: str,
        source_type: str,
        source_uri: str | None,
        owner_department_id: str,
        visibility: str,
        content_hash: str,
        permission_snapshot_id: str,
        tags: list[str],
        actor_user_id: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO documents(
                    id, enterprise_id, kb_id, folder_id, title, source_type, source_uri,
                    lifecycle_status, index_status, owner_department_id, visibility,
                    content_hash, permission_snapshot_id, tags, created_by, updated_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid), CAST(:kb_id AS uuid),
                    CAST(:folder_id AS uuid), :title, :source_type, :source_uri,
                    'draft', 'none', CAST(:owner_department_id AS uuid), :visibility,
                    :content_hash, CAST(:permission_snapshot_id AS uuid), :tags,
                    CAST(:actor_user_id AS uuid), CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": document_id,
                "enterprise_id": enterprise_id,
                "kb_id": kb_id,
                "folder_id": folder_id,
                "title": title,
                "source_type": source_type,
                "source_uri": source_uri,
                "owner_department_id": owner_department_id,
                "visibility": visibility,
                "content_hash": content_hash,
                "permission_snapshot_id": permission_snapshot_id,
                "tags": tags,
                "actor_user_id": actor_user_id,
            },
        )

    def insert_document_version(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_id: str,
        document_version_id: str,
        object_key: str | None,
        content_hash: str,
        actor_user_id: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO document_versions(
                    id, enterprise_id, document_id, version_no, object_key,
                    content_hash, status, created_by
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:enterprise_id AS uuid),
                    CAST(:document_id AS uuid), 1, :object_key,
                    :content_hash, 'draft', CAST(:actor_user_id AS uuid)
                )
                """
            ),
            {
                "id": document_version_id,
                "enterprise_id": enterprise_id,
                "document_id": document_id,
                "object_key": object_key,
                "content_hash": content_hash,
                "actor_user_id": actor_user_id,
            },
        )

def _build_upload_object_key(
    *,
    enterprise_id: str,
    kb_id: str,
    document_id: str,
    filename: str,
) -> str:
    safe_name = filename.strip().replace("/", "_") or "document.txt"
    return f"uploads/{enterprise_id}/{kb_id}/{document_id}/{safe_name}"
