"""Query Service P0 非流式最小闭环。

当前版本接入 PostgreSQL 关键词索引、向量召回端口和 RRF 融合排序。真实
embedding / Qdrant adapter 尚未接入时，向量召回会显式降级，不影响关键词闭环。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from app.modules.permissions import CandidateMetadata, PermissionService, PermissionServiceError
from app.modules.permissions.schemas import PermissionContext, PermissionFilter
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import (
    ActiveIndexVersion,
    QueryCitation,
    QueryFilterClause,
    QueryResult,
)
from app.modules.retrieval import (
    ReciprocalRankFusion,
    RetrievalCandidate,
    UnavailableVectorRetriever,
    VectorRetriever,
)
from app.shared.json_utils import json_int, stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

MAX_QUERY_LENGTH = 4000
SUPPORTED_FILTERS = {"department_scope", "updated_after", "source_type", "tags"}


class QueryService:
    """非流式查询编排。"""

    def __init__(
        self,
        *,
        permission_service: PermissionService | None = None,
        vector_retriever: VectorRetriever | None = None,
        fusion_service: ReciprocalRankFusion | None = None,
    ) -> None:
        self.permission_service = permission_service or PermissionService()
        self.vector_retriever = vector_retriever or UnavailableVectorRetriever()
        self.fusion_service = fusion_service or ReciprocalRankFusion()

    def create_query(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_ids: list[str],
        query_text: str,
        mode: str,
        filters: dict[str, Any] | None,
        top_k: int,
        include_sources: bool,
        request_id: str,
        trace_id: str,
    ) -> QueryResult:
        started_at = time.monotonic()
        normalized_query = _normalize_query(query_text)
        normalized_kb_ids = _normalize_ids(kb_ids)
        normalized_top_k = min(max(top_k, 1), 50)
        request_filters = filters or {}
        filter_clause = _build_filter_clause(request_filters)
        config_version = self._load_active_config_version(session)

        try:
            context = self.permission_service.build_context(
                session,
                user_id=user_id,
                enterprise_id=enterprise_id,
                request_id=request_id,
            )
            active_indexes = self._load_active_index_versions(
                session,
                enterprise_id=context.enterprise_id,
                kb_ids=normalized_kb_ids,
            )
            active_index_ids = tuple(index.id for index in active_indexes)
            collection_names = tuple(index.collection_name for index in active_indexes)
            index_version_hash = _index_version_hash(active_index_ids)
            citations: tuple[QueryCitation, ...] = ()
            degrade_reasons: list[str] = []
            if active_index_ids:
                permission_filter = self.permission_service.build_filter(
                    context,
                    kb_ids=normalized_kb_ids,
                    active_index_version_ids=active_index_ids,
                    required_scope="rag:query",
                )
                keyword_candidates = self._keyword_search(
                    session,
                    permission_filter=permission_filter,
                    query_text=normalized_query,
                    filter_clause=filter_clause,
                    limit=normalized_top_k * 3,
                )
                vector_result = self.vector_retriever.search(
                    query_text=normalized_query,
                    permission_filter=permission_filter,
                    collection_names=collection_names,
                    top_k=normalized_top_k * 3,
                )
                if vector_result.degraded:
                    degrade_reasons.append(
                        vector_result.degrade_reason or "vector_retrieval_degraded"
                    )
                candidates = self.fusion_service.fuse(
                    keyword_candidates + vector_result.candidates,
                    limit=normalized_top_k * 3,
                )
                citations = self._gate_candidates(
                    context,
                    candidates,
                    allowed_kb_ids=normalized_kb_ids,
                    active_index_version_ids=active_index_ids,
                    limit=normalized_top_k,
                    include_sources=include_sources,
                )
                candidate_count = len(candidates)
                permission_filter_hash = permission_filter.permission_filter_hash
                permission_version = permission_filter.permission_version
            else:
                candidate_count = 0
                permission_filter_hash = context.permission_filter_hash
                permission_version = context.permission_version

            if mode == "answer":
                degrade_reasons.append("llm_not_implemented_keyword_only")
            degraded = bool(degrade_reasons)
            degrade_reason = ";".join(degrade_reasons) if degrade_reasons else None
            result = QueryResult(
                request_id=request_id,
                answer="",
                citations=citations,
                confidence=_confidence(citations),
                degraded=degraded,
                degrade_reason=degrade_reason,
                trace_id=trace_id,
            )
            self._insert_query_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=context.enterprise_id,
                user_id=context.user_id,
                kb_ids=normalized_kb_ids,
                query_hash=_query_hash(normalized_query),
                status="success",
                degraded=degraded,
                degrade_reason=degrade_reason,
                config_version=config_version,
                permission_version=permission_version,
                permission_filter_hash=permission_filter_hash,
                index_version_hash=index_version_hash,
                latency_ms=_elapsed_ms(started_at),
                candidate_count=candidate_count,
                citation_count=len(citations),
                error_code=None,
            )
            return result
        except PermissionServiceError as exc:
            self._insert_denied_query_log(
                session,
                request_id=request_id,
                trace_id=trace_id,
                enterprise_id=enterprise_id,
                user_id=user_id,
                kb_ids=normalized_kb_ids,
                query_text=normalized_query,
                config_version=config_version,
                latency_ms=_elapsed_ms(started_at),
                error_code=exc.error_code,
            )
            raise QueryServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def _load_active_config_version(self, session: Session) -> int:
        try:
            row = session.execute(
                text(
                    """
                    SELECT value_json
                    FROM system_state
                    WHERE key = 'active_config_version'
                    LIMIT 1
                    """
                )
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_CONFIG_UNAVAILABLE",
                "active config version cannot be loaded",
                exc,
            ) from exc
        version = json_int(row._mapping["value_json"], "version") if row else None
        if version is None:
            raise QueryServiceError(
                "QUERY_CONFIG_UNAVAILABLE",
                "active config version is missing",
                status_code=503,
                retryable=True,
            )
        return version

    def _load_active_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[ActiveIndexVersion, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS index_version_id,
                        collection_name
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = ANY(CAST(:kb_ids AS uuid[]))
                      AND status = 'active'
                    ORDER BY activated_at DESC NULLS LAST, id
                    """
                ),
                {"enterprise_id": enterprise_id, "kb_ids": list(kb_ids)},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_INDEX_UNAVAILABLE",
                "active index versions cannot be loaded",
                exc,
            ) from exc
        return tuple(
            ActiveIndexVersion(
                id=str(row._mapping["index_version_id"]),
                collection_name=str(row._mapping["collection_name"]),
            )
            for row in rows
        )

    def _keyword_search(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        query_text: str,
        filter_clause: QueryFilterClause,
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        params = dict(permission_filter.params)
        params.update(filter_clause.params)
        params.update(
            {
                "query_text": query_text,
                "like_query": f"%{query_text}%",
                "limit": limit,
            }
        )
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        kie.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        c.id::text AS chunk_id,
                        d.title,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.lifecycle_status AS document_lifecycle_status,
                        d.index_status AS document_index_status,
                        c.status AS chunk_status,
                        kie.visibility_state,
                        iv.id::text AS index_version_id,
                        LEAST(
                            kie.indexed_permission_version,
                            cir.indexed_permission_version
                        ) AS indexed_permission_version,
                        c.page_start,
                        c.page_end,
                        GREATEST(
                            ts_rank_cd(kie.search_tsv, plainto_tsquery('simple', :query_text)),
                            CASE WHEN kie.search_text ILIKE :like_query THEN 0.05 ELSE 0 END
                        )::float AS score
                    FROM keyword_index_entries kie
                    JOIN chunks c ON c.id = kie.chunk_id
                    JOIN documents d ON d.id = kie.document_id
                    JOIN index_versions iv ON iv.id = kie.index_version_id
                    JOIN chunk_index_refs cir
                      ON cir.keyword_id = kie.id
                     AND cir.chunk_id = c.id
                     AND cir.index_version_id = iv.id
                    WHERE {permission_filter.keyword_where_sql}
                      AND iv.status = 'active'
                      AND (
                          kie.search_tsv @@ plainto_tsquery('simple', :query_text)
                          OR kie.search_text ILIKE :like_query
                      )
                      {filter_clause.sql}
                    ORDER BY score DESC, c.ordinal ASC
                    LIMIT :limit
                    """
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_KEYWORD_SEARCH_FAILED",
                "keyword search failed",
                exc,
            ) from exc
        return tuple(
            _candidate_from_mapping(dict(row._mapping), source="keyword", rank=rank)
            for rank, row in enumerate(rows, start=1)
        )

    def _gate_candidates(
        self,
        context: PermissionContext,
        candidates: tuple[RetrievalCandidate, ...],
        *,
        allowed_kb_ids: tuple[str, ...],
        active_index_version_ids: tuple[str, ...],
        limit: int,
        include_sources: bool,
    ) -> tuple[QueryCitation, ...]:
        if not include_sources:
            return ()
        citations: list[QueryCitation] = []
        for candidate in candidates:
            gate_result = self.permission_service.gate_candidate(
                context,
                CandidateMetadata(
                    enterprise_id=candidate.enterprise_id,
                    kb_id=candidate.kb_id,
                    document_id=candidate.document_id,
                    chunk_id=candidate.chunk_id,
                    owner_department_id=candidate.owner_department_id,
                    visibility=candidate.visibility,
                    document_lifecycle_status=candidate.document_lifecycle_status,
                    document_index_status=candidate.document_index_status,
                    chunk_status=candidate.chunk_status,
                    visibility_state=candidate.visibility_state,
                    index_version_id=candidate.index_version_id,
                    indexed_permission_version=candidate.indexed_permission_version,
                    access_blocked=False,
                ),
                allowed_kb_ids=allowed_kb_ids,
                active_index_version_ids=active_index_version_ids,
            )
            if not gate_result.allowed:
                continue
            citations.append(_citation_from_candidate(candidate))
            if len(citations) >= limit:
                break
        return tuple(citations)

    def _insert_denied_query_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        user_id: str,
        kb_ids: tuple[str, ...],
        query_text: str,
        config_version: int,
        latency_ms: int,
        error_code: str,
    ) -> None:
        self._insert_query_log(
            session,
            request_id=request_id,
            trace_id=trace_id,
            enterprise_id=enterprise_id,
            user_id=user_id,
            kb_ids=kb_ids,
            query_hash=_query_hash(query_text),
            status="denied",
            degraded=False,
            degrade_reason=None,
            config_version=config_version,
            permission_version=0,
            permission_filter_hash="unavailable",
            index_version_hash=None,
            latency_ms=latency_ms,
            candidate_count=0,
            citation_count=0,
            error_code=error_code,
        )

    def _insert_query_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        user_id: str,
        kb_ids: tuple[str, ...],
        query_hash: str,
        status: str,
        degraded: bool,
        degrade_reason: str | None,
        config_version: int,
        permission_version: int,
        permission_filter_hash: str,
        index_version_hash: str | None,
        latency_ms: int,
        candidate_count: int,
        citation_count: int,
        error_code: str | None,
    ) -> None:
        try:
            session.execute(
                text(
                    """
                    INSERT INTO query_logs(
                        id, enterprise_id, request_id, trace_id, user_id, kb_ids,
                        query_hash, status, degraded, degrade_reason, config_version,
                        permission_version, permission_filter_hash, index_version_hash,
                        model_route_hash, latency_ms, candidate_count, citation_count,
                        error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, CAST(:user_id AS uuid), CAST(:kb_ids AS uuid[]),
                        :query_hash, :status, :degraded, :degrade_reason, :config_version,
                        :permission_version, :permission_filter_hash, :index_version_hash,
                        NULL, :latency_ms, :candidate_count, :citation_count, :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "kb_ids": list(kb_ids),
                    "query_hash": query_hash,
                    "status": status,
                    "degraded": degraded,
                    "degrade_reason": degrade_reason,
                    "config_version": config_version,
                    "permission_version": permission_version,
                    "permission_filter_hash": permission_filter_hash,
                    "index_version_hash": index_version_hash,
                    "latency_ms": latency_ms,
                    "candidate_count": candidate_count,
                    "citation_count": citation_count,
                    "error_code": error_code,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_LOG_WRITE_FAILED",
                "query log cannot be written",
                exc,
            ) from exc


def _normalize_query(value: str) -> str:
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


def _normalize_ids(values: list[str]) -> tuple[str, ...]:
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


def _build_filter_clause(filters: dict[str, Any]) -> QueryFilterClause:
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
    source_types = _string_list(filters.get("source_type"))
    if source_types:
        conditions.append("d.source_type = ANY(CAST(:source_types AS text[]))")
        params["source_types"] = source_types
    tags = _string_list(filters.get("tags"))
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


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _candidate_from_mapping(
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
        page_start=_optional_int(row.get("page_start")),
        page_end=_optional_int(row.get("page_end")),
        rank=rank,
        score=float(row["score"] or 0),
    )


def _citation_from_candidate(candidate: RetrievalCandidate) -> QueryCitation:
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


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _query_hash(query_text: str) -> str:
    return stable_json_hash({"query": query_text})


def _index_version_hash(index_version_ids: tuple[str, ...]) -> str:
    return stable_json_hash({"active_index_version_ids": sorted(index_version_ids)})


def _confidence(citations: tuple[QueryCitation, ...]) -> Literal["low", "medium", "high"]:
    if len(citations) >= 3:
        return "medium"
    return "low"


def _elapsed_ms(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)


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
