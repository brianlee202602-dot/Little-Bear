"""Facade for user-facing knowledge browsing."""

from __future__ import annotations

from typing import Any

from app.modules.knowledge.access_control import KnowledgeAccessGuard
from app.modules.knowledge.browser_service import KnowledgeBrowserService
from app.modules.knowledge.document_reader import KnowledgeDocumentReader
from app.modules.knowledge.mappers import (
    _chunk_from_mapping,
    _database_error,
    _document_from_mapping,
    _document_list_item_from_mapping,
    _document_version_from_mapping,
    _json_mapping,
    _knowledge_base_from_mapping,
    _knowledge_base_visibility_sql,
    _optional_int,
    _optional_str,
)
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import (
    AccessibleChunkList,
    AccessibleCitationSource,
    AccessibleDocument,
    AccessibleDocumentList,
    AccessibleDocumentVersionList,
    AccessibleFolderList,
    AccessibleKnowledgeBase,
    AccessibleKnowledgeBaseList,
)
from app.modules.knowledge.source_reader import KnowledgeSourceReader
from app.modules.permissions import PermissionService
from app.modules.permissions.schemas import PermissionContext
from app.modules.storage.service import ObjectStorage
from sqlalchemy.orm import Session


class KnowledgeService:
    """Route-facing facade for knowledge browsing and source verification."""

    def __init__(
        self,
        *,
        permission_service: PermissionService | None = None,
        object_storage: ObjectStorage | None = None,
        repository: KnowledgeRepository | None = None,
    ) -> None:
        self.permission_service = permission_service or PermissionService()
        self.object_storage = object_storage
        self._repository = repository or KnowledgeRepository()
        self._access_guard = KnowledgeAccessGuard(self.permission_service)

    def list_knowledge_bases(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> AccessibleKnowledgeBaseList:
        return self._browser_service().list_knowledge_bases(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
            request_id=request_id,
        )

    def get_knowledge_base(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_id: str,
        request_id: str | None = None,
    ) -> AccessibleKnowledgeBase:
        return self._browser_service().get_knowledge_base(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            kb_id=kb_id,
            request_id=request_id,
        )

    def list_folders(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
        request_id: str | None = None,
    ) -> AccessibleFolderList:
        return self._browser_service().list_folders(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            kb_id=kb_id,
            page=page,
            page_size=page_size,
            request_id=request_id,
        )

    def list_documents(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> AccessibleDocumentList:
        return self._browser_service().list_documents(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            kb_id=kb_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
            request_id=request_id,
        )

    def get_document(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        document_id: str,
        request_id: str | None = None,
    ) -> AccessibleDocument:
        return self._document_reader().get_document(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            document_id=document_id,
            request_id=request_id,
        )

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
        return self._document_reader().list_document_versions(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            document_id=document_id,
            page=page,
            page_size=page_size,
            request_id=request_id,
        )

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
        return self._document_reader().list_document_chunks(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            document_id=document_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
            request_id=request_id,
        )

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
        return self._source_reader().get_document_source(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            document_id=document_id,
            source_id=source_id,
            request_id=request_id,
        )

    def _source_from_mapping(self, row: Any) -> AccessibleCitationSource:
        return self._source_reader().source_from_mapping(row)

    def _read_source_text(
        self,
        *,
        object_key: str | None,
        text_preview: str,
    ) -> tuple[str, str]:
        return self._source_reader().read_source_text(
            object_key=object_key,
            text_preview=text_preview,
        )

    def _permission_context(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        request_id: str | None,
        required_scope: str,
    ) -> PermissionContext:
        return self._access_guard.permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope=required_scope,
        )

    def _load_active_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        return self._repository.load_active_index_versions(
            session,
            enterprise_id=enterprise_id,
            kb_ids=kb_ids,
        )

    def _ensure_queryable_knowledge_base(
        self,
        session: Session,
        context: PermissionContext,
        *,
        kb_id: str,
    ) -> None:
        self._access_guard.ensure_queryable_knowledge_base(session, context, kb_id=kb_id)

    def _load_document_kb_id(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_id: str,
    ) -> str:
        return self._repository.load_document_kb_id(
            session,
            enterprise_id=enterprise_id,
            document_id=document_id,
        )

    def _browser_service(self) -> KnowledgeBrowserService:
        return KnowledgeBrowserService(
            access_guard=self._access_guard,
            repository=self._repository,
        )

    def _document_reader(self) -> KnowledgeDocumentReader:
        return KnowledgeDocumentReader(
            access_guard=self._access_guard,
            repository=self._repository,
        )

    def _source_reader(self) -> KnowledgeSourceReader:
        return KnowledgeSourceReader(
            access_guard=self._access_guard,
            repository=self._repository,
            object_storage=self.object_storage,
        )


__all__ = [
    "KnowledgeService",
    "_chunk_from_mapping",
    "_database_error",
    "_document_from_mapping",
    "_document_list_item_from_mapping",
    "_document_version_from_mapping",
    "_json_mapping",
    "_knowledge_base_from_mapping",
    "_knowledge_base_visibility_sql",
    "_optional_int",
    "_optional_str",
]
