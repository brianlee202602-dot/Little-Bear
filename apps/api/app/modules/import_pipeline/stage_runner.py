"""Import worker stage-effect workflows."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

from app.modules.import_pipeline import request_items as _request_helpers
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.executors import ParsedDocument, SourceDocument
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.runtime import build_indexing_service
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.orm import Session


class ImportStageRunner:
    """Execute parse, clean, chunk and indexing side effects for claimed jobs."""

    def __init__(
        self,
        owner: Any,
        *,
        indexing_service_factory: Callable[[Session], Any] | None = None,
    ) -> None:
        self.owner = owner
        self.indexing_service_factory = indexing_service_factory or build_indexing_service

    def apply_stage_effect(self, session: Session, *, row: Any) -> None:
        stage = row["stage"]
        job_type = row["job_type"]
        request_json = _request_helpers.json_mapping(row["request_json"])
        if job_type == "permission_refresh":
            if stage == "index":
                try:
                    self.indexing_service_factory(session).refresh_permission_payloads(
                        session,
                        request_json=request_json,
                    )
                    return
                except IndexingServiceError as exc:
                    raise _indexing_error(exc) from exc
            if stage in {"publish", "cleanup"}:
                return
        if stage == "cleanup":
            try:
                self.indexing_service_factory(session).cleanup_pending_delete_indexes(
                    session,
                    request_json=request_json,
                )
                return
            except IndexingServiceError as exc:
                raise _indexing_error(exc) from exc
        if stage == "validate":
            self.mark_documents_indexing(session, request_json=request_json)
            return
        if stage == "parse":
            self.mark_versions_parsed(session, row=row, request_json=request_json)
            return
        if stage == "clean":
            self.mark_versions_cleaned(session, row=row, request_json=request_json)
            return
        if stage == "chunk":
            self.write_draft_chunks(session, row=row, request_json=request_json)
            return
        if stage not in {"embed", "index", "publish"}:
            return
        try:
            indexing_service = self.indexing_service_factory(session)
            if stage == "embed":
                indexing_service.create_draft_indexes(session, request_json=request_json)
                return
            if stage == "index":
                indexing_service.write_draft_indexes(session, request_json=request_json)
                return
            if stage == "publish":
                indexing_service.publish_ready_indexes(session, request_json=request_json)
                return
        except IndexingServiceError as exc:
            raise _indexing_error(exc) from exc

    def mark_documents_indexing(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> None:
        document_ids = _request_helpers.document_ids_from_request(request_json, None)
        if not document_ids:
            raise ImportServiceError(
                "IMPORT_DOCUMENTS_REQUIRED",
                "import job request does not include document ids",
                status_code=409,
            )
        session.execute(
            text(
                """
                UPDATE documents
                SET index_status = 'indexing',
                    updated_at = now()
                WHERE id = ANY(CAST(:document_ids AS uuid[]))
                  AND index_status IN ('none', 'index_failed')
                  AND lifecycle_status = 'draft'
                """
            ),
            {"document_ids": document_ids},
        )

    def mark_versions_parsed(
        self,
        session: Session,
        *,
        row: Any,
        request_json: dict[str, Any],
    ) -> None:
        items = _request_helpers.request_items(request_json)
        for item in items:
            document_id = _request_helpers.item_str(item, "document_id")
            document_version_id = _request_helpers.item_str(item, "document_version_id")
            if not document_id or not document_version_id:
                continue
            source = self.source_document_from_item(item)
            parsed = self.owner.parser.parse(source)
            parsed_object_key = _derived_object_key(
                "parsed",
                enterprise_id=row["enterprise_id"],
                document_id=document_id,
                document_version_id=document_version_id,
            )
            self.put_text_object(
                object_key=parsed_object_key,
                text_content=parsed.text,
                error_code="IMPORT_PARSED_OBJECT_STORE_FAILED",
            )
            item["parsed_object_key"] = parsed_object_key
            item["parser_version"] = parsed.parser_version
            session.execute(
                text(
                    """
                    UPDATE document_versions
                    SET status = CASE WHEN status = 'draft' THEN 'parsed' ELSE status END,
                        parser_version = :parser_version,
                        parsed_object_key = :parsed_object_key
                    WHERE id = CAST(:document_version_id AS uuid)
                      AND status IN ('draft', 'parsed')
                    """
                ),
                {
                    "document_version_id": document_version_id,
                    "parser_version": parsed.parser_version,
                    "parsed_object_key": parsed_object_key,
                },
            )
        if not any(_request_helpers.item_str(item, "document_version_id") for item in items):
            raise ImportServiceError(
                "IMPORT_DOCUMENT_VERSIONS_REQUIRED",
                "import job request does not include document version ids",
                status_code=409,
            )
        self.update_job_request_json(session, job_id=row["job_id"], request_json=request_json)

    def mark_versions_cleaned(
        self,
        session: Session,
        *,
        row: Any,
        request_json: dict[str, Any],
    ) -> None:
        items = _request_helpers.request_items(request_json)
        for item in items:
            document_id = _request_helpers.item_str(item, "document_id")
            document_version_id = _request_helpers.item_str(item, "document_version_id")
            if not document_id or not document_version_id:
                continue
            parsed_text = self.item_stage_text(item, preferred_key="parsed_object_key")
            cleaned = self.owner.cleaner.clean(
                ParsedDocument(
                    text=parsed_text,
                    parser_version=(
                        _request_helpers.item_str(item, "parser_version") or "stage-text"
                    ),
                    metadata=_request_helpers.item_metadata(item),
                )
            )
            cleaned_object_key = _derived_object_key(
                "cleaned",
                enterprise_id=row["enterprise_id"],
                document_id=document_id,
                document_version_id=document_version_id,
            )
            self.put_text_object(
                object_key=cleaned_object_key,
                text_content=cleaned.text,
                error_code="IMPORT_CLEANED_OBJECT_STORE_FAILED",
            )
            item["cleaned_object_key"] = cleaned_object_key
            item["cleaner_version"] = cleaned.cleaner_version
            session.execute(
                text(
                    """
                    UPDATE document_versions
                    SET cleaned_object_key = :cleaned_object_key
                    WHERE id = CAST(:document_version_id AS uuid)
                      AND status IN ('parsed', 'chunked')
                    """
                ),
                {
                    "document_version_id": document_version_id,
                    "cleaned_object_key": cleaned_object_key,
                },
            )
        if not any(_request_helpers.item_str(item, "document_version_id") for item in items):
            raise ImportServiceError(
                "IMPORT_DOCUMENT_VERSIONS_REQUIRED",
                "import job request does not include document version ids",
                status_code=409,
            )
        self.update_job_request_json(session, job_id=row["job_id"], request_json=request_json)

    def write_draft_chunks(
        self,
        session: Session,
        *,
        row: Any,
        request_json: dict[str, Any] | None = None,
    ) -> None:
        request_json = request_json or _request_helpers.json_mapping(row["request_json"])
        items = _request_helpers.request_items(request_json)
        if not items:
            raise ImportServiceError(
                "IMPORT_ITEMS_REQUIRED",
                "import job request does not include items for chunking",
                status_code=409,
            )
        document_version_ids: list[str] = []
        for item_index, item in enumerate(items):
            document_id = _request_helpers.item_str(item, "document_id")
            document_version_id = _request_helpers.item_str(item, "document_version_id")
            if not document_id or not document_version_id:
                continue
            document_version_ids.append(document_version_id)
            text_content = self.item_stage_text(item, preferred_key="cleaned_object_key")
            cleaned = self.owner.cleaner.clean(
                ParsedDocument(
                    text=text_content,
                    parser_version=(
                        _request_helpers.item_str(item, "parser_version") or "stage-text"
                    ),
                    metadata=_request_helpers.item_metadata(item),
                )
            )
            chunk_documents = self.owner.chunker.chunk(
                cleaned,
                title=_request_helpers.item_title(item),
            )
            item["chunk_count"] = len(chunk_documents)
            item["chunker_version"] = self.owner.chunker.version
            for chunk in chunk_documents:
                chunk_text = chunk.text
                preview = chunk_text[:500]
                content_hash = stable_json_hash(
                    {
                        "document_id": document_id,
                        "document_version_id": document_version_id,
                        "ordinal": chunk.ordinal,
                        "text": chunk_text,
                    }
                )
                text_object_key = _chunk_text_object_key(
                    enterprise_id=row["enterprise_id"],
                    document_id=document_id,
                    document_version_id=document_version_id,
                    ordinal=chunk.ordinal,
                )
                self.put_text_object(
                    object_key=text_object_key,
                    text_content=chunk_text,
                    error_code="IMPORT_CHUNK_OBJECT_STORE_FAILED",
                )
                session.execute(
                    text(
                        """
                        INSERT INTO chunks(
                            id, enterprise_id, kb_id, document_id, document_version_id,
                            ordinal, text_object_key, text_preview, heading_path, source_offsets,
                            content_hash, token_count, status, permission_snapshot_id
                        )
                        SELECT
                            CAST(:id AS uuid), d.enterprise_id, d.kb_id, d.id, dv.id,
                            :ordinal, :text_object_key, :text_preview, :heading_path,
                            CAST(:source_offsets AS jsonb), :content_hash, :token_count,
                            'draft', d.permission_snapshot_id
                        FROM documents d
                        JOIN document_versions dv
                          ON dv.id = CAST(:document_version_id AS uuid)
                         AND dv.document_id = d.id
                        WHERE d.id = CAST(:document_id AS uuid)
                        ON CONFLICT ON CONSTRAINT uq_chunks_version_ordinal DO NOTHING
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "document_version_id": document_version_id,
                        "ordinal": chunk.ordinal,
                        "text_object_key": text_object_key,
                        "text_preview": preview,
                        "heading_path": chunk.heading_path,
                        "source_offsets": json.dumps(
                            {
                                "item_index": item_index,
                                "chunk_ordinal": chunk.ordinal,
                                **chunk.source_offsets,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "content_hash": content_hash,
                        "token_count": chunk.token_count,
                    },
                )
        if document_version_ids:
            session.execute(
                text(
                    """
                    UPDATE document_versions
                    SET status = 'chunked',
                        chunker_version = :chunker_version
                    WHERE id = ANY(CAST(:document_version_ids AS uuid[]))
                      AND status IN ('parsed', 'chunked')
                    """
                ),
                {
                    "document_version_ids": document_version_ids,
                    "chunker_version": self.owner.chunker.version,
                },
            )
        self.update_job_request_json(session, job_id=row["job_id"], request_json=request_json)

    def source_document_from_item(self, item: dict[str, Any]) -> SourceDocument:
        object_key = _request_helpers.item_str(item, "object_key")
        content = None
        if object_key and _request_helpers.looks_like_object_key(object_key):
            content = self.get_object(
                object_key=object_key,
                error_code="IMPORT_OBJECT_READ_FAILED",
            )
        return SourceDocument(
            title=_request_helpers.item_title(item),
            url=_request_helpers.item_str(item, "url"),
            object_key=object_key,
            content=content,
            content_type=_request_helpers.item_content_type(item),
            metadata=_request_helpers.item_metadata(item),
        )

    def item_stage_text(self, item: dict[str, Any], *, preferred_key: str) -> str:
        object_key = _request_helpers.item_str(item, preferred_key)
        if object_key:
            content = self.get_object(
                object_key=object_key,
                error_code="IMPORT_STAGE_OBJECT_READ_FAILED",
            )
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ImportServiceError(
                    "IMPORT_STAGE_OBJECT_ENCODING_UNSUPPORTED",
                    "derived import object is not valid UTF-8 text",
                    status_code=422,
                    retryable=False,
                    details={"object_key": object_key},
                ) from exc
        return _request_helpers.item_text_content(item)

    def get_object(self, *, object_key: str, error_code: str) -> bytes:
        try:
            return self.owner.object_storage.get_object(object_key=object_key)
        except Exception as exc:
            raise ImportServiceError(
                error_code,
                "import object cannot be read",
                status_code=503,
                retryable=True,
                details={"object_key": object_key},
            ) from exc

    def put_text_object(self, *, object_key: str, text_content: str, error_code: str) -> None:
        try:
            self.owner.object_storage.put_object(
                object_key=object_key,
                content=text_content.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )
        except Exception as exc:
            raise ImportServiceError(
                error_code,
                "derived import object cannot be stored",
                status_code=503,
                retryable=True,
                details={"object_key": object_key},
            ) from exc

    def update_job_request_json(
        self,
        session: Session,
        *,
        job_id: str,
        request_json: dict[str, Any],
    ) -> None:
        session.execute(
            text(
                """
                UPDATE import_jobs
                SET request_json = CAST(:request_json AS jsonb),
                    updated_at = now()
                WHERE id = CAST(:job_id AS uuid)
                """
            ),
            {
                "job_id": job_id,
                "request_json": json.dumps(request_json, ensure_ascii=False, sort_keys=True),
            },
        )


def _derived_object_key(
    kind: str,
    *,
    enterprise_id: str,
    document_id: str,
    document_version_id: str,
) -> str:
    return f"derived/{enterprise_id}/{document_id}/{document_version_id}/{kind}.txt"


def _chunk_text_object_key(
    *,
    enterprise_id: str,
    document_id: str,
    document_version_id: str,
    ordinal: int,
) -> str:
    return f"chunks/{enterprise_id}/{document_id}/{document_version_id}/{ordinal:06d}.txt"


def _indexing_error(exc: IndexingServiceError) -> ImportServiceError:
    return ImportServiceError(
        exc.error_code,
        exc.message,
        status_code=exc.status_code,
        retryable=exc.retryable,
        details=exc.details,
    )
