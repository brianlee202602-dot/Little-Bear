"""Document detail, version, and chunk readers."""

from __future__ import annotations

from app.modules.knowledge.access_control import KnowledgeAccessGuard
from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import (
    AccessibleChunkList,
    AccessibleDocument,
    AccessibleDocumentVersionList,
)
from sqlalchemy.orm import Session


class KnowledgeDocumentReader:
    """Read accessible document details, versions, and chunk previews."""

    def __init__(
        self,
        *,
        access_guard: KnowledgeAccessGuard | None = None,
        repository: KnowledgeRepository | None = None,
    ) -> None:
        self._access_guard = access_guard or KnowledgeAccessGuard()
        self._repository = repository or KnowledgeRepository()

    def get_document(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        document_id: str,
        request_id: str | None = None,
    ) -> AccessibleDocument:
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
            raise _document_not_found(document_id)
        permission_filter = self._access_guard.permission_service.build_filter(
            context,
            kb_ids=(document_kb_id,),
            active_index_version_ids=active_index_ids,
            required_scope="document:read",
        )
        document = self._repository.get_document(
            session,
            permission_filter=permission_filter,
            document_id=document_id,
        )
        if document is None:
            raise _document_not_found(document_id)
        return document

    def list_document_versions(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        document_id: str,
        page: int,
        page_size: int,
        request_id: str | None = None,
    ) -> AccessibleDocumentVersionList:
        self.get_document(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            document_id=document_id,
            request_id=request_id,
        )
        items, total = self._repository.list_document_versions(
            session,
            enterprise_id=enterprise_id,
            document_id=document_id,
            page=page,
            page_size=page_size,
        )
        return AccessibleDocumentVersionList(items=items, total=total)

    def list_document_chunks(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        document_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> AccessibleChunkList:
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
            return AccessibleChunkList(items=[], total=0)
        permission_filter = self._access_guard.permission_service.build_filter(
            context,
            kb_ids=(document_kb_id,),
            active_index_version_ids=active_index_ids,
            required_scope="document:read",
        )
        items, total = self._repository.list_document_chunks(
            session,
            permission_filter=permission_filter,
            document_id=document_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
        )
        return AccessibleChunkList(items=items, total=total)


def _document_not_found(document_id: str) -> KnowledgeServiceError:
    return KnowledgeServiceError(
        "KNOWLEDGE_DOCUMENT_NOT_FOUND",
        "document is not accessible",
        status_code=404,
        details={"document_id": document_id},
    )
