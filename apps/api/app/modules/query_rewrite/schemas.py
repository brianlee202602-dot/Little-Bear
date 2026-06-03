"""Query Rewrite 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.retrieval import RetrievalModelCall


@dataclass(frozen=True)
class RewriteConversationMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class QueryRewriteInput:
    original_query: str
    conversation_messages: tuple[RewriteConversationMessage, ...] = ()
    max_queries: int = 4
    locale: str = "zh-CN"


@dataclass(frozen=True)
class QueryRewriteItem:
    query: str
    intent: str | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    rewritten_queries: tuple[QueryRewriteItem, ...]
    degraded: bool = False
    degrade_reason: str | None = None
    model_call: RetrievalModelCall | None = None
