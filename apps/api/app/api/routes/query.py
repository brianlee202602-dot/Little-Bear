"""查询 API 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import query_conversations, query_execute, query_stream
from app.api.routes.query_conversations import (
    create_query_conversation,
    delete_query_conversation,
    get_query_conversation,
    list_query_conversations,
)
from app.api.routes.query_execute import (
    _attach_conversation,
    _execute_query,
    attach_conversation,
    create_query,
    execute_query,
)
from app.api.routes.query_stream import (
    _mark_stream_message_failed,
    _prepare_query_stream,
    _query_sse_events,
    _query_stream_sse_events,
    _sse_event,
    _stream_tokens,
    create_query_stream,
    mark_stream_message_failed,
    prepare_query_stream,
    query_sse_events,
    query_stream_sse_events,
    sse_event,
    stream_tokens,
)
from app.modules.query.conversations import QueryConversationService, QueryConversationWriteContext

router = APIRouter()
router.include_router(query_conversations.router)
router.include_router(query_execute.router)
router.include_router(query_stream.router)

__all__ = [
    "QueryConversationService",
    "QueryConversationWriteContext",
    "_attach_conversation",
    "_execute_query",
    "_mark_stream_message_failed",
    "_prepare_query_stream",
    "_query_sse_events",
    "_query_stream_sse_events",
    "_sse_event",
    "_stream_tokens",
    "attach_conversation",
    "create_query",
    "create_query_conversation",
    "create_query_stream",
    "delete_query_conversation",
    "execute_query",
    "get_query_conversation",
    "list_query_conversations",
    "mark_stream_message_failed",
    "prepare_query_stream",
    "query_sse_events",
    "query_stream_sse_events",
    "router",
    "sse_event",
    "stream_tokens",
]

