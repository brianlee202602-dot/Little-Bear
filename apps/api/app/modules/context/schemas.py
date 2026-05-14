"""Context Builder 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextChunk:
    chunk_id: str
    document_id: str
    document_version_id: str
    title: str
    content: str
    heading_path: str | None
    page_start: int | None
    page_end: int | None
    score: float
    rank: int
    source_offsets: dict[str, Any] | None = None


@dataclass(frozen=True)
class QueryContext:
    query_text: str
    chunks: tuple[ContextChunk, ...]
    estimated_tokens: int
    truncated: bool
