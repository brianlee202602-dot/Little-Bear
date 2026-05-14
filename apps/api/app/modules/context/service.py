"""查询上下文组装器。"""

from __future__ import annotations

import json
from typing import Any

from app.modules.context.schemas import ContextChunk, QueryContext
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import QueryAllowedCandidate
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

DEFAULT_MAX_CONTEXT_CHUNKS = 6
DEFAULT_MAX_CONTEXT_CHARS = 6000


class ContextBuilder:
    """基于已通过权限 gate 的候选组装 LLM 可消费上下文。"""

    def __init__(
        self,
        *,
        max_chunks: int = DEFAULT_MAX_CONTEXT_CHUNKS,
        max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    ) -> None:
        self.max_chunks = max(max_chunks, 1)
        self.max_chars = max(max_chars, 1)

    def build(
        self,
        session: Session,
        *,
        query_text: str,
        allowed_candidates: tuple[QueryAllowedCandidate, ...],
    ) -> QueryContext:
        if not allowed_candidates:
            return QueryContext(
                query_text=query_text,
                chunks=(),
                estimated_tokens=0,
                truncated=False,
            )

        selected = allowed_candidates[: self.max_chunks]
        rows = self._load_chunks(
            session,
            chunk_ids=tuple(candidate.candidate.chunk_id for candidate in selected),
        )
        loaded_by_id = {chunk.chunk_id: chunk for chunk in rows}
        chunks: list[ContextChunk] = []
        total_chars = 0
        truncated = False
        for allowed in selected:
            candidate = allowed.candidate
            loaded = loaded_by_id.get(candidate.chunk_id)
            if loaded is None:
                continue
            remaining_chars = self.max_chars - total_chars
            if remaining_chars <= 0:
                truncated = True
                break
            content = loaded.content
            if len(content) > remaining_chars:
                content = content[:remaining_chars].rstrip()
                truncated = True
            if not content:
                continue
            chunks.append(
                ContextChunk(
                    chunk_id=loaded.chunk_id,
                    document_id=loaded.document_id,
                    document_version_id=loaded.document_version_id,
                    title=loaded.title,
                    content=content,
                    heading_path=loaded.heading_path,
                    page_start=loaded.page_start,
                    page_end=loaded.page_end,
                    score=candidate.score,
                    rank=candidate.rank,
                    source_offsets=loaded.source_offsets,
                )
            )
            total_chars += len(content)
            if total_chars >= self.max_chars:
                truncated = True
                break
        return QueryContext(
            query_text=query_text,
            chunks=tuple(chunks),
            estimated_tokens=_estimate_tokens(total_chars),
            truncated=truncated,
        )

    def _load_chunks(
        self,
        session: Session,
        *,
        chunk_ids: tuple[str, ...],
    ) -> tuple[_LoadedChunk, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        c.id::text AS chunk_id,
                        c.document_id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        d.title,
                        c.text_preview,
                        c.heading_path,
                        c.page_start,
                        c.page_end,
                        c.source_offsets
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.id = ANY(CAST(:chunk_ids AS uuid[]))
                      AND c.deleted_at IS NULL
                    """
                ),
                {"chunk_ids": list(chunk_ids)},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_CONTEXT_UNAVAILABLE",
                "query context chunks cannot be loaded",
                exc,
            ) from exc
        return tuple(_loaded_chunk_from_mapping(dict(row._mapping)) for row in rows)


class _LoadedChunk:
    def __init__(
        self,
        *,
        chunk_id: str,
        document_id: str,
        document_version_id: str,
        title: str,
        content: str,
        heading_path: str | None,
        page_start: int | None,
        page_end: int | None,
        source_offsets: dict[str, Any] | None,
    ) -> None:
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_version_id = document_version_id
        self.title = title
        self.content = content
        self.heading_path = heading_path
        self.page_start = page_start
        self.page_end = page_end
        self.source_offsets = source_offsets


def _loaded_chunk_from_mapping(row: dict[str, Any]) -> _LoadedChunk:
    return _LoadedChunk(
        chunk_id=str(row["chunk_id"]),
        document_id=str(row["document_id"]),
        document_version_id=str(row["document_version_id"]),
        title=str(row["title"]),
        content=str(row["text_preview"]),
        heading_path=_optional_str(row.get("heading_path")),
        page_start=_optional_int(row.get("page_start")),
        page_end=_optional_int(row.get("page_end")),
        source_offsets=_json_mapping(row.get("source_offsets")),
    )


def _estimate_tokens(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return max((char_count + 3) // 4, 1)


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _json_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> QueryServiceError:
    return QueryServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
