"""查询 API 请求和响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.config import PaginationData


class QueryHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kb_ids: list[str] = Field(min_length=1)
    query: str = Field(min_length=1)
    conversation_id: str | None = None
    history: list[QueryHistoryMessage] = Field(default_factory=list, max_length=20)
    mode: Literal["answer", "search"] = "answer"
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=8, ge=1, le=50)
    include_sources: bool = True


class CitationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    doc_id: str
    document_version_id: str
    title: str
    page_start: int
    page_end: int
    score: float


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    debug_id: str
    conversation_id: str | None = None
    message_id: str | None = None
    answer: str
    citations: list[CitationData]
    confidence: Literal["low", "medium", "high"]
    degraded: bool
    degrade_reason: str | None = None


class QueryConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    kb_ids: list[str] = Field(default_factory=list)


class QueryMessageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["running", "done", "error", "cancelled"]
    citations: list[CitationData] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] | None = None
    degraded: bool = False
    degrade_reason: str | None = None
    debug_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueryConversationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: Literal["active", "deleted"]
    kb_ids: list[str] = Field(default_factory=list)
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueryConversationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: list[QueryConversationData]
    pagination: PaginationData


class QueryConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: QueryConversationData
    messages: list[QueryMessageData] = Field(default_factory=list)
    messages_pagination: PaginationData
