"""Query Service 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class QueryCitation:
    source_id: str
    doc_id: str
    document_version_id: str
    title: str
    page_start: int
    page_end: int
    score: float


@dataclass(frozen=True)
class QueryResult:
    request_id: str
    answer: str
    citations: tuple[QueryCitation, ...]
    confidence: Literal["low", "medium", "high"]
    degraded: bool
    degrade_reason: str | None
    trace_id: str


@dataclass(frozen=True)
class QueryFilterClause:
    sql: str
    params: dict[str, Any]


@dataclass(frozen=True)
class ActiveIndexVersion:
    id: str
    collection_name: str
