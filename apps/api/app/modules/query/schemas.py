"""Query Service 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.modules.context.schemas import QueryContext
from app.modules.permissions.schemas import PermissionContext
from app.modules.retrieval import RetrievalModelCall
from app.modules.retrieval.schemas import RetrievalCandidate


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
class QueryScopeSummary:
    mode: Literal["explicit", "auto_all_accessible"]
    resolved_kb_count: int


@dataclass(frozen=True)
class QueryResult:
    request_id: str
    answer: str
    citations: tuple[QueryCitation, ...]
    confidence: Literal["low", "medium", "high"]
    degraded: bool
    degrade_reason: str | None
    trace_id: str
    query_scope: QueryScopeSummary = QueryScopeSummary(mode="explicit", resolved_kb_count=0)
    kb_ids: tuple[str, ...] = ()
    context: QueryContext | None = None
    conversation_id: str | None = None
    message_id: str | None = None


@dataclass(frozen=True)
class QueryFilterClause:
    sql: str
    params: dict[str, Any]


@dataclass(frozen=True)
class ActiveIndexVersion:
    id: str
    collection_name: str


@dataclass(frozen=True)
class QueryAllowedCandidate:
    candidate: RetrievalCandidate
    citation: QueryCitation


@dataclass(frozen=True)
class QueryCandidateGateDiagnostics:
    input_count: int
    allowed_count: int
    rejected_count: int
    missing_metadata_count: int
    rejection_reasons: dict[str, int]


@dataclass(frozen=True)
class QueryCandidateGateResult:
    allowed_candidates: tuple[QueryAllowedCandidate, ...]
    diagnostics: QueryCandidateGateDiagnostics


@dataclass(frozen=True)
class _CitationValidationResult:
    valid: bool
    degrade_reason: str
    referenced_source_ids: tuple[str, ...]
    invalid_source_ids: tuple[str, ...]
    allowed_source_count: int

    def summary(self) -> dict[str, object]:
        return {
            "degrade_reason": self.degrade_reason,
            "referenced_source_count": len(self.referenced_source_ids),
            "invalid_source_ids": list(self.invalid_source_ids[:10]),
            "invalid_source_count": len(self.invalid_source_ids),
            "allowed_source_count": self.allowed_source_count,
        }


@dataclass(frozen=True)
class _QueryAuditEvent:
    event_name: str
    result: Literal["failure", "denied"]
    risk_level: Literal["medium", "high", "critical"]
    error_code: str | None
    summary: dict[str, object]


@dataclass(frozen=True)
class _CurrentCandidateFacts:
    candidate: RetrievalCandidate
    access_blocked: bool


@dataclass(frozen=True)
class QueryStreamPlan:
    request_id: str
    trace_id: str
    mode: str
    started_at: float
    normalized_query: str
    normalized_kb_ids: tuple[str, ...]
    config_version: int
    context: PermissionContext
    query_context: QueryContext | None
    allowed_candidates: tuple[QueryAllowedCandidate, ...]
    citations: tuple[QueryCitation, ...]
    confidence: Literal["low", "medium", "high"]
    pre_degrade_reasons: tuple[str, ...]
    audit_events: tuple[_QueryAuditEvent, ...]
    rerank_model_calls: tuple[RetrievalModelCall, ...]
    model_route_hash: str | None
    candidate_count: int
    permission_filter_hash: str
    permission_version: int
    index_version_hash: str | None
    query_scope_mode: Literal["explicit", "auto_all_accessible"]
    rewritten_queries: tuple[str, ...] = ()
    query_rewrite_model_call: RetrievalModelCall | None = None
    retrieval_diagnostics: dict[str, object] | None = None
    conversation_id: str | None = None
    message_id: str | None = None
