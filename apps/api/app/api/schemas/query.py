"""查询 API 请求和响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kb_ids: list[str] = Field(min_length=1)
    query: str = Field(min_length=1)
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

    request_id: str
    answer: str
    citations: list[CitationData]
    confidence: Literal["low", "medium", "high"]
    degraded: bool
    degrade_reason: str | None = None
    trace_id: str
