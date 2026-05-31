"""查询会话领域数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.modules.query.schemas import QueryCitation


@dataclass(frozen=True)
class QueryConversationSummary:
    id: str
    title: str
    status: str
    kb_ids: tuple[str, ...]
    last_message_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class QueryMessage:
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["running", "done", "error", "cancelled"]
    citations: tuple[QueryCitation, ...]
    confidence: Literal["low", "medium", "high"] | None
    degraded: bool
    degrade_reason: str | None
    request_id: str | None
    trace_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class QueryConversationDetail:
    conversation: QueryConversationSummary
    messages: tuple[QueryMessage, ...]
    message_page: int
    message_page_size: int
    message_total: int


@dataclass(frozen=True)
class QueryConversationList:
    items: tuple[QueryConversationSummary, ...]
    total: int


@dataclass(frozen=True)
class QueryConversationWriteContext:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str

