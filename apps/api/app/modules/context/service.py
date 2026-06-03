"""查询上下文组装器。"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.modules.context.schemas import ContextChunk, QueryContext
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import QueryAllowedCandidate
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

DEFAULT_MAX_CONTEXT_CHUNKS = 6
DEFAULT_MAX_CONTEXT_CHARS = 6000
DEFAULT_MAX_CONTEXT_TOKENS = 1500


class ContextBuilder:
    """基于已通过权限 gate 的候选组装 LLM 可消费上下文。"""

    def __init__(
        self,
        *,
        max_chunks: int = DEFAULT_MAX_CONTEXT_CHUNKS,
        max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
        max_context_tokens: int | None = None,
        max_chunks_per_document: int = 3,
        max_chunks_per_section: int = 2,
        mmr_enabled: bool = True,
        mmr_lambda: float = 0.7,
        chunk_text_reader: ChunkTextReader | None = None,
        token_estimator: ContextTokenEstimator | None = None,
    ) -> None:
        self.max_chunks = max(max_chunks, 1)
        self.max_chars = max(max_chars, 1)
        self.max_context_tokens = (
            max(max_context_tokens, 1) if max_context_tokens is not None else None
        )
        self.max_chunks_per_document = max(max_chunks_per_document, 1)
        self.max_chunks_per_section = max(max_chunks_per_section, 1)
        self.mmr_enabled = mmr_enabled
        self.mmr_lambda = min(max(float(mmr_lambda), 0.0), 1.0)
        self.chunk_text_reader = chunk_text_reader
        self.token_estimator = token_estimator or ConservativeTokenEstimator()

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

        rows = self._load_chunks(
            session,
            chunk_ids=tuple(candidate.candidate.chunk_id for candidate in allowed_candidates),
        )
        loaded_by_id = {chunk.chunk_id: chunk for chunk in rows}
        selected = self._select_context_items(
            tuple(
                _ContextCandidate(allowed=allowed, chunk=loaded)
                for allowed in allowed_candidates
                if (loaded := loaded_by_id.get(allowed.candidate.chunk_id)) is not None
            )
        )
        chunks: list[ContextChunk] = []
        total_chars = 0
        total_tokens = 0
        truncated = False
        per_chunk_char_limit = _multi_query_chunk_char_limit(selected, self.max_chars)
        per_chunk_token_limit = (
            _multi_query_chunk_token_limit(selected, self.max_context_tokens)
            if self.max_context_tokens is not None
            else None
        )
        for allowed in selected:
            candidate = allowed.candidate
            loaded = loaded_by_id.get(candidate.chunk_id)
            if loaded is None:
                continue
            content = self._context_content(loaded)
            content, content_tokens, content_truncated = self._fit_content_to_budget(
                content,
                total_chars=total_chars,
                total_tokens=total_tokens,
                per_chunk_char_limit=per_chunk_char_limit,
                per_chunk_token_limit=per_chunk_token_limit,
            )
            if content_truncated:
                truncated = True
            if not content:
                if self._budget_exhausted(total_chars=total_chars, total_tokens=total_tokens):
                    break
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
                    matched_query=candidate.matched_query,
                    matched_query_index=candidate.matched_query_index,
                )
            )
            total_chars += len(content)
            total_tokens += content_tokens
            if self._budget_exhausted(total_chars=total_chars, total_tokens=total_tokens):
                truncated = True
                break
        return QueryContext(
            query_text=query_text,
            chunks=tuple(chunks),
            estimated_tokens=total_tokens,
            truncated=truncated,
        )

    def _fit_content_to_budget(
        self,
        content: str,
        *,
        total_chars: int,
        total_tokens: int,
        per_chunk_char_limit: int | None,
        per_chunk_token_limit: int | None,
    ) -> tuple[str, int, bool]:
        remaining_chars = self.max_chars - total_chars
        if remaining_chars <= 0:
            return "", 0, True
        char_limit = (
            min(remaining_chars, per_chunk_char_limit)
            if per_chunk_char_limit is not None
            else remaining_chars
        )
        truncated = False
        if len(content) > char_limit:
            content = content[:char_limit].rstrip()
            truncated = True
        if not content:
            return "", 0, truncated
        if self.max_context_tokens is None:
            return content, self.token_estimator.estimate_tokens(content), truncated

        remaining_tokens = self.max_context_tokens - total_tokens
        if remaining_tokens <= 0:
            return "", 0, True
        token_limit = (
            min(remaining_tokens, per_chunk_token_limit)
            if per_chunk_token_limit is not None
            else remaining_tokens
        )
        content_tokens = self.token_estimator.estimate_tokens(content)
        if content_tokens > token_limit:
            content = self.token_estimator.truncate_to_tokens(content, token_limit).rstrip()
            content_tokens = self.token_estimator.estimate_tokens(content)
            truncated = True
        return content, content_tokens, truncated

    def _budget_exhausted(self, *, total_chars: int, total_tokens: int) -> bool:
        if total_chars >= self.max_chars:
            return True
        return self.max_context_tokens is not None and total_tokens >= self.max_context_tokens

    def _select_context_items(
        self,
        items: tuple[_ContextCandidate, ...],
    ) -> tuple[QueryAllowedCandidate, ...]:
        if not items:
            return ()
        unique_items = tuple(_dedupe_context_items(items))
        coverage_items = _query_coverage_items(unique_items)
        if coverage_items:
            return self._select_with_seed(unique_items, coverage_items)
        if self.mmr_enabled:
            selected_items = self._select_with_mmr(unique_items)
        else:
            selected_items = self._select_by_rank(unique_items)
        return tuple(item.allowed for item in selected_items)

    def _select_with_seed(
        self,
        items: tuple[_ContextCandidate, ...],
        seed_items: tuple[_ContextCandidate, ...],
    ) -> tuple[QueryAllowedCandidate, ...]:
        selected: list[_ContextCandidate] = []
        doc_counts: dict[str, int] = {}
        section_counts: dict[tuple[str, str], int] = {}
        for item in seed_items:
            if len(selected) >= self.max_chunks:
                break
            if not _within_context_limits(
                item,
                doc_counts=doc_counts,
                section_counts=section_counts,
                max_chunks_per_document=self.max_chunks_per_document,
                max_chunks_per_section=self.max_chunks_per_section,
            ):
                continue
            selected.append(item)
            _increase_context_counts(item, doc_counts=doc_counts, section_counts=section_counts)
        if len(selected) >= self.max_chunks:
            return tuple(item.allowed for item in selected)

        selected_ids = {item.chunk.chunk_id for item in selected}
        remaining = tuple(item for item in items if item.chunk.chunk_id not in selected_ids)
        if self.mmr_enabled:
            filler = self._select_with_mmr(
                remaining,
                selected_items=selected,
                doc_counts=doc_counts,
                section_counts=section_counts,
            )
        else:
            filler = self._select_by_rank(
                remaining,
                selected_items=selected,
                doc_counts=doc_counts,
                section_counts=section_counts,
            )
        return tuple(item.allowed for item in (*selected, *filler))

    def _select_by_rank(
        self,
        items: tuple[_ContextCandidate, ...],
        *,
        selected_items: list[_ContextCandidate] | None = None,
        doc_counts: dict[str, int] | None = None,
        section_counts: dict[tuple[str, str], int] | None = None,
    ) -> tuple[_ContextCandidate, ...]:
        selected = list(selected_items or [])
        doc_counts = dict(doc_counts or {})
        section_counts = dict(section_counts or {})
        added: list[_ContextCandidate] = []
        for item in items:
            if not _within_context_limits(
                item,
                doc_counts=doc_counts,
                section_counts=section_counts,
                max_chunks_per_document=self.max_chunks_per_document,
                max_chunks_per_section=self.max_chunks_per_section,
            ):
                continue
            selected.append(item)
            added.append(item)
            _increase_context_counts(item, doc_counts=doc_counts, section_counts=section_counts)
            if len(selected) >= self.max_chunks:
                break
        return tuple(added)

    def _select_with_mmr(
        self,
        items: tuple[_ContextCandidate, ...],
        *,
        selected_items: list[_ContextCandidate] | None = None,
        doc_counts: dict[str, int] | None = None,
        section_counts: dict[tuple[str, str], int] | None = None,
    ) -> tuple[_ContextCandidate, ...]:
        remaining = list(items)
        selected = list(selected_items or [])
        doc_counts = dict(doc_counts or {})
        section_counts = dict(section_counts or {})
        added: list[_ContextCandidate] = []
        token_sets = {
            item.chunk.chunk_id: _tokens(item.chunk.content)
            for item in (*selected, *remaining)
        }
        while remaining and len(selected) < self.max_chunks:
            best_item: _ContextCandidate | None = None
            best_score: float | None = None
            for item in remaining:
                if not _within_context_limits(
                    item,
                    doc_counts=doc_counts,
                    section_counts=section_counts,
                    max_chunks_per_document=self.max_chunks_per_document,
                    max_chunks_per_section=self.max_chunks_per_section,
                ):
                    continue
                similarity = max(
                    (
                        _context_item_similarity(
                            item,
                            selected_item,
                            token_sets=token_sets,
                        )
                        for selected_item in selected
                    ),
                    default=0.0,
                )
                score = self.mmr_lambda * item.allowed.candidate.score - (
                    1.0 - self.mmr_lambda
                ) * similarity
                if best_score is None or score > best_score:
                    best_score = score
                    best_item = item
            if best_item is None:
                break
            selected.append(best_item)
            added.append(best_item)
            _increase_context_counts(
                best_item,
                doc_counts=doc_counts,
                section_counts=section_counts,
            )
            remaining.remove(best_item)
        return tuple(added)

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
                        c.text_object_key,
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

    def _context_content(self, chunk: _LoadedChunk) -> str:
        if chunk.text_object_key and self.chunk_text_reader is not None:
            content = self.chunk_text_reader.read_text(object_key=chunk.text_object_key)
            if content and content.strip():
                return content
        return chunk.content


class ChunkTextReader(Protocol):
    """读取 chunk 完整正文的最小端口。"""

    def read_text(self, *, object_key: str) -> str | None:
        """按对象 key 读取完整 chunk 正文；不可用时返回 None。"""
        ...


class ContextTokenEstimator(Protocol):
    """上下文 token 预算估算端口，后续可替换为真实 provider tokenizer。"""

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数。"""
        ...

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """截断到不超过指定 token 数的前缀文本。"""
        ...


class ConservativeTokenEstimator:
    """无 provider tokenizer 时使用的保守估算器。

    CJK 字符按 1 token 计，ASCII 连续词按约 4 字符 1 token 计，标点按
    1 token 计。它不是精确 tokenizer，但比纯字符预算更贴近中英文混合
    RAG 上下文的真实成本，并且行为可测试、可替换。
    """

    def estimate_tokens(self, text: str) -> int:
        return _estimate_text_tokens(text)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        if self.estimate_tokens(text) <= max_tokens:
            return text
        low = 0
        high = len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if self.estimate_tokens(text[:mid]) <= max_tokens:
                low = mid
            else:
                high = mid - 1
        return text[:low]


class _LoadedChunk:
    def __init__(
        self,
        *,
        chunk_id: str,
        document_id: str,
        document_version_id: str,
        title: str,
        content: str,
        text_object_key: str | None,
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
        self.text_object_key = text_object_key
        self.heading_path = heading_path
        self.page_start = page_start
        self.page_end = page_end
        self.source_offsets = source_offsets


@dataclass(frozen=True)
class _ContextCandidate:
    allowed: QueryAllowedCandidate
    chunk: _LoadedChunk


def _loaded_chunk_from_mapping(row: dict[str, Any]) -> _LoadedChunk:
    return _LoadedChunk(
        chunk_id=str(row["chunk_id"]),
        document_id=str(row["document_id"]),
        document_version_id=str(row["document_version_id"]),
        title=str(row["title"]),
        content=str(row["text_preview"]),
        text_object_key=_optional_str(row.get("text_object_key")),
        heading_path=_optional_str(row.get("heading_path")),
        page_start=_optional_int(row.get("page_start")),
        page_end=_optional_int(row.get("page_end")),
        source_offsets=_json_mapping(row.get("source_offsets")),
    )


def _estimate_text_tokens(text: str) -> int:
    token_count = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if _is_cjk(char):
            token_count += 1
            index += 1
            continue
        if char.isascii() and char.isalnum():
            start = index
            while index < len(text) and text[index].isascii() and text[index].isalnum():
                index += 1
            token_count += max((index - start + 3) // 4, 1)
            continue
        token_count += 1
        index += 1
    return token_count


def _is_cjk(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2A6DF
        or 0x2A700 <= codepoint <= 0x2B73F
        or 0x2B740 <= codepoint <= 0x2B81F
        or 0x2B820 <= codepoint <= 0x2CEAF
    )


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


def _dedupe_context_items(items: tuple[_ContextCandidate, ...]) -> list[_ContextCandidate]:
    deduped: list[_ContextCandidate] = []
    seen: set[str] = set()
    for item in items:
        if item.chunk.chunk_id in seen:
            continue
        seen.add(item.chunk.chunk_id)
        deduped.append(item)
    return deduped


def _query_coverage_items(items: tuple[_ContextCandidate, ...]) -> tuple[_ContextCandidate, ...]:
    query_indexes = sorted(
        {
            item.allowed.candidate.matched_query_index
            for item in items
            if item.allowed.candidate.matched_query_index > 0
        }
    )
    if len(query_indexes) <= 1:
        return ()
    selected: list[_ContextCandidate] = []
    for query_index in query_indexes:
        for item in items:
            if item.allowed.candidate.matched_query_index == query_index:
                selected.append(item)
                break
    return tuple(selected)


def _multi_query_chunk_char_limit(
    selected: tuple[QueryAllowedCandidate, ...],
    max_chars: int,
) -> int | None:
    query_indexes = {
        item.candidate.matched_query_index
        for item in selected
        if item.candidate.matched_query_index > 0
    }
    if len(query_indexes) <= 1:
        return None
    # 联合问题的目标是覆盖多个子问题，而不是让每个子问题的第一个大 chunk
    # 吃满预算。按已选 chunk 数量拆分字符预算，可以用更短摘要换取更完整覆盖。
    return max(max_chars // max(len(selected), len(query_indexes)), 1)


def _multi_query_chunk_token_limit(
    selected: tuple[QueryAllowedCandidate, ...],
    max_context_tokens: int | None,
) -> int | None:
    if max_context_tokens is None:
        return None
    query_indexes = {
        item.candidate.matched_query_index
        for item in selected
        if item.candidate.matched_query_index > 0
    }
    if len(query_indexes) <= 1:
        return None
    return max(max_context_tokens // max(len(selected), len(query_indexes)), 1)


def _within_context_limits(
    item: _ContextCandidate,
    *,
    doc_counts: dict[str, int],
    section_counts: dict[tuple[str, str], int],
    max_chunks_per_document: int,
    max_chunks_per_section: int,
) -> bool:
    if doc_counts.get(_document_limit_key(item), 0) >= max_chunks_per_document:
        return False
    section_key = _section_key(item)
    if section_counts.get(section_key, 0) >= max_chunks_per_section:
        return False
    return True


def _increase_context_counts(
    item: _ContextCandidate,
    *,
    doc_counts: dict[str, int],
    section_counts: dict[tuple[str, str], int],
) -> None:
    document_key = _document_limit_key(item)
    doc_counts[document_key] = doc_counts.get(document_key, 0) + 1
    section_key = _section_key(item)
    section_counts[section_key] = section_counts.get(section_key, 0) + 1


def _section_key(item: _ContextCandidate) -> tuple[str, str]:
    scope_key = _context_limit_scope(item)
    section_id = None
    if item.chunk.source_offsets:
        section_id = item.chunk.source_offsets.get("section_id")
    if isinstance(section_id, str) and section_id:
        return (scope_key, f"{item.chunk.document_id}:{section_id}")
    if item.chunk.heading_path:
        return (scope_key, f"{item.chunk.document_id}:{item.chunk.heading_path}")
    return (scope_key, f"{item.chunk.document_id}:{item.chunk.chunk_id}")


def _document_limit_key(item: _ContextCandidate) -> str:
    return f"{_context_limit_scope(item)}:{item.chunk.document_id}"


def _context_limit_scope(item: _ContextCandidate) -> str:
    query_index = item.allowed.candidate.matched_query_index
    return f"query:{query_index}" if query_index > 0 else "query:default"


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"\W+", value.lower()) if token}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _context_item_similarity(
    left: _ContextCandidate,
    right: _ContextCandidate,
    *,
    token_sets: dict[str, set[str]],
) -> float:
    left_embedding = left.allowed.candidate.embedding
    right_embedding = right.allowed.candidate.embedding
    if left_embedding is not None and right_embedding is not None:
        cosine = _cosine_similarity(left_embedding, right_embedding)
        if cosine is not None:
            return cosine
    return _jaccard(
        token_sets[left.chunk.chunk_id],
        token_sets[right.chunk.chunk_id],
    )


def _cosine_similarity(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float | None:
    if not left or len(left) != len(right):
        return None
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return None
    value = sum(left[index] * right[index] for index in range(len(left))) / (
        left_norm * right_norm
    )
    return max(min(value, 1.0), 0.0)


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
