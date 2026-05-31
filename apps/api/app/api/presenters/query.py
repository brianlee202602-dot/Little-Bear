"""查询响应 DTO 映射。"""

from __future__ import annotations

import hashlib

from app.api.schemas.query import (
    CitationData,
    QueryConversationData,
    QueryConversationResponse,
    QueryMessageData,
    QueryResponse,
)
from app.modules.query.conversations import (
    QueryConversationDetail,
    QueryConversationSummary,
    QueryMessage,
)
from app.modules.query.schemas import QueryCitation, QueryResult


def query_response(result: QueryResult) -> QueryResponse:
    return QueryResponse(
        debug_id=public_debug_id(result.request_id, result.trace_id) or "dbg_unknown",
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        answer=result.answer,
        citations=[citation_data(citation) for citation in result.citations],
        confidence=result.confidence,
        degraded=result.degraded,
        degrade_reason=result.degrade_reason,
    )


def citation_data(citation: QueryCitation) -> CitationData:
    return CitationData(
        source_id=citation.source_id,
        doc_id=citation.doc_id,
        document_version_id=citation.document_version_id,
        title=citation.title,
        page_start=citation.page_start,
        page_end=citation.page_end,
        score=citation.score,
    )


def conversation_response(
    detail: QueryConversationDetail,
    *,
    request_id: str,
) -> QueryConversationResponse:
    return QueryConversationResponse(
        request_id=request_id,
        data=conversation_data(detail.conversation),
        messages=[message_data(message) for message in detail.messages],
        messages_pagination={
            "page": detail.message_page,
            "page_size": detail.message_page_size,
            "total": detail.message_total,
        },
    )


def conversation_data(conversation: QueryConversationSummary) -> QueryConversationData:
    return QueryConversationData(
        id=conversation.id,
        title=conversation.title,
        status="active" if conversation.status == "active" else "deleted",
        kb_ids=list(conversation.kb_ids),
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def message_data(message: QueryMessage) -> QueryMessageData:
    return QueryMessageData(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        status=message.status,
        citations=[citation_data(citation) for citation in message.citations],
        confidence=message.confidence,
        degraded=message.degraded,
        degrade_reason=message.degrade_reason,
        debug_id=public_debug_id(message.request_id, message.trace_id),
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


def public_debug_id(*values: str | None) -> str | None:
    seed = "|".join(value for value in values if value)
    if not seed:
        return None
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"dbg_{digest}"

