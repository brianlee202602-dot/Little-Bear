"""User-facing knowledge base and document browser."""

from __future__ import annotations

from app.modules.knowledge.access_control import KnowledgeAccessGuard
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import AccessibleDocumentList, AccessibleKnowledgeBaseList
from sqlalchemy.orm import Session


class KnowledgeBrowserService:
    """List knowledge bases and visible documents for an end user."""

    def __init__(
        self,
        *,
        access_guard: KnowledgeAccessGuard | None = None,
        repository: KnowledgeRepository | None = None,
    ) -> None:
        self._access_guard = access_guard or KnowledgeAccessGuard()
        self._repository = repository or KnowledgeRepository()

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
        context = self._access_guard.permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope="knowledge_base:read",
        )
        items, total = self._repository.list_knowledge_bases(
            session,
            context=context,
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
        )
        return AccessibleKnowledgeBaseList(items=items, total=total)

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
        context = self._access_guard.permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope="document:read",
        )
        self._access_guard.ensure_queryable_knowledge_base(session, context, kb_id=kb_id)
        active_index_ids = self._repository.load_active_index_versions(
            session,
            enterprise_id=context.enterprise_id,
            kb_ids=(kb_id,),
        )
        if not active_index_ids:
            return AccessibleDocumentList(items=[], total=0)
        permission_filter = self._access_guard.permission_service.build_filter(
            context,
            kb_ids=(kb_id,),
            active_index_version_ids=active_index_ids,
            required_scope="document:read",
        )
        items, total = self._repository.list_documents(
            session,
            permission_filter=permission_filter,
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
        )
        return AccessibleDocumentList(items=items, total=total)
