"""查询会话消息生命周期服务。"""

from __future__ import annotations

import uuid
from typing import Literal

from app.modules.query.conversation_mappers import conversation_not_found
from app.modules.query.conversation_models import QueryConversationWriteContext
from app.modules.query.conversation_repository import QueryConversationRepository
from app.modules.query.schemas import QueryCitation
from sqlalchemy.orm import Session


class QueryConversationMessageService:
    """创建用户消息、assistant 占位消息并完成或失败 assistant 消息。"""

    def __init__(self, repository: QueryConversationRepository | None = None) -> None:
        self._repository = repository or QueryConversationRepository()

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
        if conversation_id:
            conversation = self._repository.load_owned_active_conversation(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if conversation is None:
                raise conversation_not_found(conversation_id)
        else:
            conversation = self._repository.create_conversation(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                title=query_text,
                kb_ids=kb_ids,
            )

        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        self._repository.touch_conversation_kbs(
            session,
            conversation_id=conversation.id,
            kb_ids=kb_ids,
        )
        self._repository.insert_user_message(
            session,
            message_id=user_message_id,
            conversation_id=conversation.id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            content=query_text,
            request_id=request_id,
            trace_id=trace_id,
        )
        self._repository.insert_assistant_placeholder(
            session,
            message_id=assistant_message_id,
            conversation_id=conversation.id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            request_id=request_id,
            trace_id=trace_id,
        )
        return QueryConversationWriteContext(
            conversation_id=conversation.id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
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
        self._repository.finish_assistant_message(
            session,
            message_id=message_id,
            content=answer,
            status="done",
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
        self._repository.finish_assistant_message(
            session,
            message_id=message_id,
            content=message,
            status=status,
            citations=(),
            confidence=None,
            degraded=True,
            degrade_reason=degrade_reason or message,
            request_id=request_id,
            trace_id=trace_id,
        )

