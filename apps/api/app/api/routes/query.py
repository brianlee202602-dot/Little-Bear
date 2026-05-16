"""查询 API。"""

from __future__ import annotations

import json
from collections.abc import Iterable

from fastapi import APIRouter, Header
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse, StreamingResponse

from app.api.schemas.query import CitationData, QueryRequest, QueryResponse
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.modules.query.errors import QueryServiceError
from app.modules.query.runtime import build_query_service
from app.modules.query.schemas import QueryCitation, QueryResult
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["query"])


@router.post("/queries", response_model=QueryResponse)
async def create_query(
    payload: QueryRequest,
    authorization: str | None = Header(default=None),
) -> QueryResponse | JSONResponse:
    result_or_error = _execute_query(payload, authorization=authorization, stage="query_create")
    if isinstance(result_or_error, JSONResponse):
        return result_or_error
    return _query_response(result_or_error)


@router.post("/query-streams", response_model=None)
async def create_query_stream(
    payload: QueryRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse | JSONResponse:
    result_or_error = _execute_query(payload, authorization=authorization, stage="query_stream")
    if isinstance(result_or_error, JSONResponse):
        return result_or_error
    return StreamingResponse(
        _query_sse_events(result_or_error),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _execute_query(
    payload: QueryRequest,
    *,
    authorization: str | None,
    stage: str,
) -> QueryResult | JSONResponse:
    token = _extract_bearer_token(authorization)
    query_error: QueryServiceError | None = None
    result = None
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            service = build_query_service(session)
            try:
                result = service.create_query(
                    session,
                    user_id=auth_context.user.id,
                    enterprise_id=auth_context.user.enterprise_id,
                    kb_ids=payload.kb_ids,
                    query_text=payload.query,
                    mode=payload.mode,
                    filters=payload.filters,
                    top_k=payload.top_k,
                    include_sources=payload.include_sources,
                    request_id=_request_id(),
                    trace_id=_trace_id(),
                )
            except QueryServiceError as exc:
                if exc.retryable:
                    raise
                query_error = exc
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage=f"{stage}_auth")
    except QueryServiceError as exc:
        return _query_error_response(exc, stage=stage)
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage=stage)

    if query_error is not None:
        return _query_error_response(query_error, stage=stage)
    if result is None:
        return JSONResponse(
            status_code=500,
            content={
                "request_id": _request_id(),
                "error_code": "QUERY_RESULT_MISSING",
                "message": "query result is missing",
                "stage": stage,
                "retryable": True,
                "details": {},
            },
        )
    return result


def _query_response(result: QueryResult) -> QueryResponse:
    return QueryResponse(
        request_id=result.request_id,
        answer=result.answer,
        citations=[_citation_data(citation) for citation in result.citations],
        confidence=result.confidence,
        degraded=result.degraded,
        degrade_reason=result.degrade_reason,
        trace_id=result.trace_id,
    )


def _query_sse_events(result: QueryResult) -> Iterable[str]:
    yield _sse_event(
        "metadata",
        {
            "request_id": result.request_id,
            "trace_id": result.trace_id,
            "confidence": result.confidence,
            "degraded": result.degraded,
            "degrade_reason": result.degrade_reason,
        },
    )
    for token in _stream_tokens(result.answer):
        yield _sse_event("token", {"delta": token})
    for citation in result.citations:
        yield _sse_event("citation", _citation_data(citation).model_dump())
    yield _sse_event(
        "done",
        {
            "request_id": result.request_id,
            "trace_id": result.trace_id,
            "citations": [
                _citation_data(citation).model_dump() for citation in result.citations
            ],
            "confidence": result.confidence,
            "degraded": result.degraded,
            "degrade_reason": result.degrade_reason,
        },
    )


def _sse_event(event_name: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"


def _stream_tokens(answer: str, *, chunk_size: int = 24) -> Iterable[str]:
    if not answer:
        return
    for index in range(0, len(answer), chunk_size):
        yield answer[index : index + chunk_size]


def _authenticate(session: object, token: str | None, *, required_scope: str) -> AuthContext:
    return AuthService().authenticate_access_token(
        session,
        access_token=token or "",
        required_scope=required_scope,
    )


def _citation_data(citation: QueryCitation) -> CitationData:
    return CitationData(
        source_id=citation.source_id,
        doc_id=citation.doc_id,
        document_version_id=citation.document_version_id,
        title=citation.title,
        page_start=citation.page_start,
        page_end=citation.page_end,
        score=citation.score,
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _request_id() -> str:
    request_context = get_request_context()
    return request_context.request_id if request_context else "req_unknown"


def _trace_id() -> str:
    request_context = get_request_context()
    return request_context.trace_id if request_context else "trace_unknown"


def _auth_error_response(exc: AuthServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _query_error_response(exc: QueryServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _database_error_response(exc: SQLAlchemyError, *, stage: str) -> JSONResponse:
    original = getattr(exc, "orig", None) or exc.__cause__
    return JSONResponse(
        status_code=500,
        content={
            "request_id": _request_id(),
            "error_code": "QUERY_DATABASE_ERROR",
            "message": "query database operation failed",
            "stage": stage,
            "retryable": True,
            "details": {
                "database_error": {
                    "type": exc.__class__.__name__,
                    "driver": original.__class__.__name__ if original is not None else None,
                }
            },
        },
    )
