"""Citation source reader for accessible document chunks."""

from __future__ import annotations

from typing import Any

from app.modules.knowledge.access_control import KnowledgeAccessGuard
from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.knowledge.mappers import _json_mapping, _optional_int, _optional_str
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import AccessibleCitationSource
from app.modules.storage.service import ObjectStorage
from sqlalchemy.orm import Session


class KnowledgeSourceReader:
    """Read verifiable source text for a document chunk."""

    def __init__(
        self,
        *,
        access_guard: KnowledgeAccessGuard | None = None,
        repository: KnowledgeRepository | None = None,
        object_storage: ObjectStorage | None = None,
    ) -> None:
        self._access_guard = access_guard or KnowledgeAccessGuard()
        self._repository = repository or KnowledgeRepository()
        self._object_storage = object_storage

    def get_document_source(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        document_id: str,
        source_id: str,
        request_id: str | None = None,
    ) -> AccessibleCitationSource:
        context = self._access_guard.permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope="document:read",
        )
        document_kb_id = self._repository.load_document_kb_id(
            session,
            enterprise_id=context.enterprise_id,
            document_id=document_id,
        )
        self._access_guard.ensure_queryable_knowledge_base(session, context, kb_id=document_kb_id)
        active_index_ids = self._repository.load_active_index_versions(
            session,
            enterprise_id=context.enterprise_id,
            kb_ids=(document_kb_id,),
        )
        if not active_index_ids:
            raise _source_not_found(document_id, source_id)
        permission_filter = self._access_guard.permission_service.build_filter(
            context,
            kb_ids=(document_kb_id,),
            active_index_version_ids=active_index_ids,
            required_scope="document:read",
        )
        row = self._repository.get_document_source_row(
            session,
            permission_filter=permission_filter,
            document_id=document_id,
            source_id=source_id,
        )
        if row is None:
            raise _source_not_found(document_id, source_id)
        return self.source_from_mapping(row._mapping)

    def source_from_mapping(self, row: Any) -> AccessibleCitationSource:
        text_preview = str(row["text_preview"])
        object_key = _optional_str(row.get("text_object_key"))
        text, text_status = self.read_source_text(
            object_key=object_key,
            text_preview=text_preview,
        )
        return AccessibleCitationSource(
            source_id=str(row["chunk_id"]),
            doc_id=str(row["document_id"]),
            document_version_id=str(row["document_version_id"]),
            title=str(row["title"]),
            text=text,
            text_preview=text_preview,
            page_start=_optional_int(row.get("page_start")),
            page_end=_optional_int(row.get("page_end")),
            ordinal=int(row["ordinal"]),
            heading_path=_optional_str(row.get("heading_path")),
            source_offsets=_json_mapping(row.get("source_offsets")),
            text_status=text_status,
        )

    def read_source_text(
        self,
        *,
        object_key: str | None,
        text_preview: str,
    ) -> tuple[str, str]:
        if not object_key or self._object_storage is None:
            return text_preview, "preview_only"
        try:
            content = self._object_storage.get_object(object_key=object_key)
        except (KeyError, OSError):
            return text_preview, "object_unavailable"
        return content.decode("utf-8", errors="replace"), "object"


def _source_not_found(document_id: str, source_id: str) -> KnowledgeServiceError:
    return KnowledgeServiceError(
        "KNOWLEDGE_SOURCE_NOT_FOUND",
        "source is not accessible",
        status_code=404,
        details={"document_id": document_id, "source_id": source_id},
    )
