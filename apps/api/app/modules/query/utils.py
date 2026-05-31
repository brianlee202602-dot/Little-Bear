"""Query workflow pure helpers."""

from __future__ import annotations

import time
from typing import Any, Literal

from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import (
    QueryAllowedCandidate,
    QueryCitation,
    QueryFilterClause,
    _QueryAuditEvent,
)
from app.modules.retrieval import RerankResult, RetrievalCandidate
from app.shared.json_utils import stable_json_hash
from sqlalchemy.exc import SQLAlchemyError

MAX_QUERY_LENGTH = 4000
SUPPORTED_FILTERS = {"department_scope", "updated_after", "source_type", "tags"}
DEFAULT_RERANK_MIN_SCORE = 0.05


def normalize_query(value: str) -> str:
    query = value.strip()
    if not query:
        raise QueryServiceError("QUERY_INVALID_REQUEST", "query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryServiceError(
            "QUERY_TOO_LONG",
            "query is too long",
            status_code=413,
            details={"max_length": MAX_QUERY_LENGTH},
        )
    return query


def normalize_ids(values: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    if not normalized:
        raise QueryServiceError("QUERY_INVALID_REQUEST", "kb_ids must not be empty")
    return tuple(normalized)


def build_filter_clause(filters: dict[str, Any]) -> QueryFilterClause:
    unsupported = sorted(set(filters) - SUPPORTED_FILTERS)
    if unsupported:
        raise QueryServiceError(
            "QUERY_FILTER_UNSUPPORTED",
            "query filter is not supported",
            details={"unsupported_filters": unsupported},
        )
    conditions: list[str] = []
    params: dict[str, Any] = {}
    department_scope = filters.get("department_scope")
    if department_scope not in (None, "my_accessible"):
        raise QueryServiceError(
            "QUERY_FILTER_UNSUPPORTED",
            "department_scope only supports my_accessible in P0",
            details={"department_scope": department_scope},
        )
    source_types = string_list(filters.get("source_type"))
    if source_types:
        conditions.append("d.source_type = ANY(CAST(:source_types AS text[]))")
        params["source_types"] = source_types
    tags = string_list(filters.get("tags"))
    if tags:
        conditions.append("d.tags && CAST(:tags AS text[])")
        params["tags"] = tags
    updated_after = filters.get("updated_after")
    if updated_after is not None:
        if not isinstance(updated_after, str) or not updated_after.strip():
            raise QueryServiceError(
                "QUERY_INVALID_REQUEST",
                "updated_after must be a non-empty string",
            )
        conditions.append("d.updated_at >= CAST(:updated_after AS timestamptz)")
        params["updated_after"] = updated_after.strip()
    sql = "".join(f"\n                      AND {condition}" for condition in conditions)
    return QueryFilterClause(sql=sql, params=params)


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def candidate_from_mapping(
    row: dict[str, Any],
    *,
    source: Literal["keyword", "vector"],
    rank: int,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        source=source,
        enterprise_id=str(row["enterprise_id"]),
        kb_id=str(row["kb_id"]),
        document_id=str(row["document_id"]),
        document_version_id=str(row["document_version_id"]),
        chunk_id=str(row["chunk_id"]),
        title=str(row["title"]),
        owner_department_id=str(row["owner_department_id"]),
        visibility=str(row["visibility"]),
        document_lifecycle_status=str(row["document_lifecycle_status"]),
        document_index_status=str(row["document_index_status"]),
        chunk_status=str(row["chunk_status"]),
        visibility_state=str(row["visibility_state"]),
        index_version_id=str(row["index_version_id"]),
        indexed_permission_version=int(row["indexed_permission_version"]),
        page_start=optional_int(row.get("page_start")),
        page_end=optional_int(row.get("page_end")),
        rank=rank,
        score=float(row["score"] or 0),
    )


def citation_from_candidate(candidate: RetrievalCandidate) -> QueryCitation:
    page_start = candidate.page_start or 0
    return QueryCitation(
        source_id=candidate.chunk_id,
        doc_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        title=candidate.title,
        page_start=page_start,
        page_end=candidate.page_end or page_start,
        score=candidate.score,
    )


def allowed_candidates_from_retrieval(
    candidates: tuple[RetrievalCandidate, ...],
) -> tuple[QueryAllowedCandidate, ...]:
    return tuple(
        QueryAllowedCandidate(candidate=candidate, citation=citation_from_candidate(candidate))
        for candidate in candidates
    )


def apply_relevance_gate(
    rerank_result: RerankResult,
    *,
    min_score: float,
    candidate_count: int,
) -> tuple[tuple[RetrievalCandidate, ...], _QueryAuditEvent | None]:
    candidates = rerank_result.candidates
    model_call = rerank_result.model_call
    if (
        min_score <= 0
        or not candidates
        or rerank_result.degraded
        or model_call is None
        or model_call.status != "success"
        or model_call.degraded
    ):
        return candidates, None

    relevant = tuple(candidate for candidate in candidates if candidate.score >= min_score)
    if relevant:
        return relevant, None

    top_score = max((candidate.score for candidate in candidates), default=0.0)
    return (
        (),
        _QueryAuditEvent(
            event_name="query.relevance_gate_failed",
            result="failure",
            risk_level="medium",
            error_code="retrieval_relevance_too_low",
            summary={
                "degrade_reason": "retrieval_relevance_too_low",
                "min_score": min_score,
                "top_score": top_score,
                "candidate_count": candidate_count,
                "reranked_count": len(candidates),
            },
        ),
    )


def candidate_rerank_text(candidate: RetrievalCandidate, text_preview: str | None) -> str:
    if isinstance(text_preview, str) and text_preview.strip():
        return text_preview.strip()
    return candidate.title


def truncate_error_message(message: str, *, limit: int = 500) -> str:
    compact = " ".join(message.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def query_hash(query_text: str) -> str:
    return stable_json_hash({"query": query_text})


def index_version_hash(index_version_ids: tuple[str, ...]) -> str:
    return stable_json_hash({"active_index_version_ids": sorted(index_version_ids)})


def confidence(citations: tuple[QueryCitation, ...]) -> Literal["low", "medium", "high"]:
    if len(citations) >= 3:
        return "medium"
    return "low"


def elapsed_ms(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)


def database_error(
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


_normalize_query = normalize_query
_normalize_ids = normalize_ids
_build_filter_clause = build_filter_clause
_string_list = string_list
_candidate_from_mapping = candidate_from_mapping
_citation_from_candidate = citation_from_candidate
_allowed_candidates_from_retrieval = allowed_candidates_from_retrieval
_apply_relevance_gate = apply_relevance_gate
_candidate_rerank_text = candidate_rerank_text
_truncate_error_message = truncate_error_message
_optional_int = optional_int
_query_hash = query_hash
_index_version_hash = index_version_hash
_confidence = confidence
_elapsed_ms = elapsed_ms
_database_error = database_error
