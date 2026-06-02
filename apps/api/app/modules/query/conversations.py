"""普通用户查询会话持久化服务。

SQL、消息生命周期和映射逻辑分别下沉到 conversation_repository、
conversation_messages 和 conversation_mappers。
"""

from __future__ import annotations

from typing import Literal

from app.modules.query.conversation_mappers import conversation_not_found
from app.modules.query.conversation_messages import QueryConversationMessageService
from app.modules.query.conversation_models import (
    QueryConversationDetail,
    QueryConversationList,
    QueryConversationSummary,
    QueryConversationWriteContext,
    QueryMessage,
)
from app.modules.query.conversation_repository import QueryConversationRepository
from app.modules.query.schemas import QueryCitation
from sqlalchemy.orm import Session


class QueryConversationService:
    """提供当前登录用户自己的查询会话读写能力。"""

    def __init__(self, repository: QueryConversationRepository | None = None) -> None:
        self._repository = repository or QueryConversationRepository()
        self._message_service = QueryConversationMessageService(self._repository)

    def list_conversations(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> QueryConversationList:
        items, total = self._repository.list_conversations(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        return QueryConversationList(items=items, total=total)

    def create_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        title: str,
        kb_ids: tuple[str, ...],
    ) -> QueryConversationSummary:
        return self._repository.create_conversation(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            title=title,
            kb_ids=kb_ids,
        )

    def get_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
        page: int,
        page_size: int,
    ) -> QueryConversationDetail:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        conversation = self._load_owned_active_conversation(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        messages, total = self._repository.list_messages(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            conversation_id=conversation_id,
            page=page,
            page_size=page_size,
        )
        return QueryConversationDetail(
            conversation=conversation,
            messages=messages,
            message_page=page,
            message_page_size=page_size,
            message_total=total,
        )

    def delete_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> None:
        result = self._repository.delete_conversation(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if result == "not_found":
            raise conversation_not_found(conversation_id)

    def prepare_query_messages(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str | None,
        kb_ids: tuple[str, ...],
        query_text: str,
        request_id: str,
        trace_id: str,
    ) -> QueryConversationWriteContext:
        return self._message_service.prepare_query_messages(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            conversation_id=conversation_id,
            kb_ids=kb_ids,
            query_text=query_text,
            request_id=request_id,
            trace_id=trace_id,
        )

    def complete_assistant_message(
        self,
        session: Session,
        *,
        message_id: str,
        answer: str,
        citations: tuple[QueryCitation, ...],
        confidence: Literal["low", "medium", "high"],
        degraded: bool,
        degrade_reason: str | None,
        request_id: str,
        trace_id: str,
    ) -> None:
        self._message_service.complete_assistant_message(
            session,
            message_id=message_id,
            answer=answer,
            citations=citations,
            confidence=confidence,
            degraded=degraded,
            degrade_reason=degrade_reason,
            request_id=request_id,
            trace_id=trace_id,
        )

    def fail_assistant_message(
        self,
        session: Session,
        *,
        message_id: str,
        message: str,
        status: Literal["error", "cancelled"] = "error",
        request_id: str,
        trace_id: str,
        degrade_reason: str | None = None,
    ) -> None:
        self._message_service.fail_assistant_message(
            session,
            message_id=message_id,
            message=message,
            status=status,
            request_id=request_id,
            trace_id=trace_id,
            degrade_reason=degrade_reason,
        )

    def _load_owned_active_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> QueryConversationSummary:
        conversation = self._repository.load_owned_active_conversation(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if conversation is None:
            raise conversation_not_found(conversation_id)
        return conversation


__all__ = [
    "QueryConversationDetail",
    "QueryConversationList",
    "QueryConversationService",
    "QueryConversationSummary",
    "QueryConversationWriteContext",
    "QueryMessage",
]
