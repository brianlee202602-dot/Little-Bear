"""查询 API。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import replace

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse, Response, StreamingResponse

from app.api.schemas.query import (
    CitationData,
    QueryConversationCreateRequest,
    QueryConversationData,
    QueryConversationListResponse,
    QueryConversationResponse,
    QueryMessageData,
    QueryRequest,
    QueryResponse,
)
from app.db.session import session_scope
from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.modules.query.conversations import (
    QueryConversationDetail,
    QueryConversationService,
    QueryConversationSummary,
    QueryConversationWriteContext,
    QueryMessage,
)
from app.modules.query.errors import QueryServiceError
from app.modules.query.runtime import build_query_service
from app.modules.query.schemas import QueryCitation, QueryResult
from app.modules.query.service import QueryService, QueryStreamPlan
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["query"])
DEFAULT_CONVERSATION_MESSAGE_PAGE_SIZE = 50


@router.get("/query-conversations", response_model=QueryConversationListResponse)
async def list_query_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> QueryConversationListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            result = QueryConversationService().list_conversations(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=auth_context.user.id,
                page=page,
                page_size=page_size,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_conversation_list_auth")
    except QueryServiceError as exc:
        return _query_error_response(exc, stage="query_conversation_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_conversation_list")
    return QueryConversationListResponse(
        request_id=_request_id(),
        data=[_conversation_data(item) for item in result.items],
        pagination={"page": page, "page_size": page_size, "total": result.total},
    )


@router.post("/query-conversations", response_model=QueryConversationResponse)
async def create_query_conversation(
    payload: QueryConversationCreateRequest,
    authorization: str | None = Header(default=None),
) -> QueryConversationResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            conversation = QueryConversationService().create_conversation(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=auth_context.user.id,
                title=payload.title or "新对话",
                kb_ids=tuple(payload.kb_ids),
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_conversation_create_auth")
    except QueryServiceError as exc:
        return _query_error_response(exc, stage="query_conversation_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_conversation_create")
    return QueryConversationResponse(
        request_id=_request_id(),
        data=_conversation_data(conversation),
        messages=[],
        messages_pagination={
            "page": 1,
            "page_size": DEFAULT_CONVERSATION_MESSAGE_PAGE_SIZE,
            "total": 0,
        },
    )


@router.get(
    "/query-conversations/{conversation_id}",
    response_model=QueryConversationResponse,
)
async def get_query_conversation(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_CONVERSATION_MESSAGE_PAGE_SIZE, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> QueryConversationResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            detail = QueryConversationService().get_conversation(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=auth_context.user.id,
                conversation_id=conversation_id,
                page=page,
                page_size=page_size,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_conversation_get_auth")
    except QueryServiceError as exc:
        return _query_error_response(exc, stage="query_conversation_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_conversation_get")
    return _conversation_response(detail)


@router.delete(
    "/query-conversations/{conversation_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_query_conversation(
    conversation_id: str,
    authorization: str | None = Header(default=None),
) -> Response | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            QueryConversationService().delete_conversation(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=auth_context.user.id,
                conversation_id=conversation_id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_conversation_delete_auth")
    except QueryServiceError as exc:
        return _query_error_response(exc, stage="query_conversation_delete")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_conversation_delete")
    return Response(status_code=204)


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
    stream_or_error = _prepare_query_stream(payload, authorization=authorization)
    if isinstance(stream_or_error, JSONResponse):
        return stream_or_error
    if isinstance(stream_or_error, QueryResult):
        return StreamingResponse(
            _query_sse_events(stream_or_error),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    service, plan = stream_or_error
    return StreamingResponse(
        _query_stream_sse_events(service, plan),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _prepare_query_stream(
    payload: QueryRequest,
    *,
    authorization: str | None,
) -> tuple[QueryService, QueryStreamPlan] | QueryResult | JSONResponse:
    token = _extract_bearer_token(authorization)
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            service = build_query_service(session)
            request_id = _request_id()
            trace_id = _trace_id()
            conversation_context = QueryConversationService().prepare_query_messages(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=auth_context.user.id,
                conversation_id=payload.conversation_id,
                kb_ids=tuple(payload.kb_ids),
                query_text=payload.query,
                request_id=request_id,
                trace_id=trace_id,
            )
            if not hasattr(service, "create_query_stream_plan"):
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
                    request_id=request_id,
                    trace_id=trace_id,
                )
                QueryConversationService().complete_assistant_message(
                    session,
                    message_id=conversation_context.assistant_message_id,
                    answer=result.answer,
                    citations=result.citations,
                    confidence=result.confidence,
                    degraded=result.degraded,
                    degrade_reason=result.degrade_reason,
                    request_id=result.request_id,
                    trace_id=result.trace_id,
                )
                return _attach_conversation(result, conversation_context)
            plan = service.create_query_stream_plan(
                session,
                user_id=auth_context.user.id,
                enterprise_id=auth_context.user.enterprise_id,
                kb_ids=payload.kb_ids,
                query_text=payload.query,
                mode=payload.mode,
                filters=payload.filters,
                top_k=payload.top_k,
                include_sources=payload.include_sources,
                request_id=request_id,
                trace_id=trace_id,
            )
            plan = replace(
                plan,
                conversation_id=conversation_context.conversation_id,
                message_id=conversation_context.assistant_message_id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="query_stream_auth")
    except QueryServiceError as exc:
        return _query_error_response(exc, stage="query_stream")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="query_stream")
    return service, plan


def _execute_query(
    payload: QueryRequest,
    *,
    authorization: str | None,
    stage: str,
) -> QueryResult | JSONResponse:
    token = _extract_bearer_token(authorization)
    query_error: QueryServiceError | None = None
    conversation_context: QueryConversationWriteContext | None = None
    result = None
    try:
        with session_scope() as session:
            auth_context = _authenticate(session, token, required_scope="rag:query")
            service = build_query_service(session)
            request_id = _request_id()
            trace_id = _trace_id()
            conversation_context = QueryConversationService().prepare_query_messages(
                session,
                enterprise_id=auth_context.user.enterprise_id,
                user_id=auth_context.user.id,
                conversation_id=payload.conversation_id,
                kb_ids=tuple(payload.kb_ids),
                query_text=payload.query,
                request_id=request_id,
                trace_id=trace_id,
            )
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
                    request_id=request_id,
                    trace_id=trace_id,
                )
                QueryConversationService().complete_assistant_message(
                    session,
                    message_id=conversation_context.assistant_message_id,
                    answer=result.answer,
                    citations=result.citations,
                    confidence=result.confidence,
                    degraded=result.degraded,
                    degrade_reason=result.degrade_reason,
                    request_id=result.request_id,
                    trace_id=result.trace_id,
                )
                result = _attach_conversation(result, conversation_context)
            except QueryServiceError as exc:
                if exc.retryable:
                    raise
                QueryConversationService().fail_assistant_message(
                    session,
                    message_id=conversation_context.assistant_message_id,
                    message=exc.message,
                    request_id=request_id,
                    trace_id=trace_id,
                    degrade_reason=exc.error_code,
                )
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
        debug_id=_public_debug_id(result.request_id, result.trace_id) or "dbg_unknown",
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        answer=result.answer,
        citations=[_citation_data(citation) for citation in result.citations],
        confidence=result.confidence,
        degraded=result.degraded,
        degrade_reason=result.degrade_reason,
    )


def _query_sse_events(result: QueryResult) -> Iterable[str]:
    yield _sse_event(
        "metadata",
        {
            "debug_id": _public_debug_id(result.request_id, result.trace_id) or "dbg_unknown",
            "conversation_id": result.conversation_id,
            "message_id": result.message_id,
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
            "debug_id": _public_debug_id(result.request_id, result.trace_id) or "dbg_unknown",
            "conversation_id": result.conversation_id,
            "message_id": result.message_id,
            "answer": result.answer,
            "citations": [
                _citation_data(citation).model_dump() for citation in result.citations
            ],
            "confidence": result.confidence,
            "degraded": result.degraded,
            "degrade_reason": result.degrade_reason,
        },
    )


def _query_stream_sse_events(service: QueryService, plan: QueryStreamPlan) -> Iterable[str]:
    yield _sse_event(
        "metadata",
        {
            "debug_id": _public_debug_id(plan.request_id, plan.trace_id) or "dbg_unknown",
            "conversation_id": plan.conversation_id,
            "message_id": plan.message_id,
            "confidence": plan.confidence,
            "degraded": bool(plan.pre_degrade_reasons),
            "degrade_reason": ";".join(plan.pre_degrade_reasons)
            if plan.pre_degrade_reasons
            else None,
            "streaming": plan.mode == "answer",
        },
    )
    if plan.mode == "answer":
        runner = service.answer_service.stream(query_context=plan.query_context)
        for token in runner.stream_tokens():
            yield _sse_event("token", {"delta": token})
        answer_result = runner.result or AnswerGenerationResult(
            answer="",
            degraded=True,
            degrade_reason="llm_stream_result_missing",
        )
    else:
        answer_result = AnswerGenerationResult(answer="", degraded=False, degrade_reason=None)

    try:
        with session_scope() as session:
            result = service.finalize_query_stream(
                session,
                plan=plan,
                answer_result=answer_result,
            )
            if plan.message_id:
                QueryConversationService().complete_assistant_message(
                    session,
                    message_id=plan.message_id,
                    answer=result.answer,
                    citations=result.citations,
                    confidence=result.confidence,
                    degraded=result.degraded,
                    degrade_reason=result.degrade_reason,
                    request_id=result.request_id,
                    trace_id=result.trace_id,
                )
            if plan.conversation_id or plan.message_id:
                result = replace(
                    result,
                    conversation_id=plan.conversation_id,
                    message_id=plan.message_id,
                )
    except (QueryServiceError, SQLAlchemyError) as exc:
        if plan.message_id:
            _mark_stream_message_failed(
                message_id=plan.message_id,
                message=getattr(exc, "message", "query stream finalization failed"),
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                degrade_reason=getattr(exc, "error_code", "QUERY_STREAM_FINALIZE_FAILED"),
            )
        yield _sse_event(
            "error",
            {
                "debug_id": _public_debug_id(plan.request_id, plan.trace_id) or "dbg_unknown",
                "error_code": getattr(exc, "error_code", "QUERY_STREAM_FINALIZE_FAILED"),
                "message": getattr(exc, "message", "query stream finalization failed"),
            },
        )
        return

    for citation in result.citations:
        yield _sse_event("citation", _citation_data(citation).model_dump())
    yield _sse_event(
        "done",
        {
            "debug_id": _public_debug_id(result.request_id, result.trace_id) or "dbg_unknown",
            "conversation_id": result.conversation_id,
            "message_id": result.message_id,
            "answer": result.answer,
            "citations": [
                _citation_data(citation).model_dump() for citation in result.citations
            ],
            "confidence": result.confidence,
            "degraded": result.degraded,
            "degrade_reason": result.degrade_reason,
        },
    )


def _attach_conversation(
    result: QueryResult,
    conversation_context: QueryConversationWriteContext,
) -> QueryResult:
    return replace(
        result,
        conversation_id=conversation_context.conversation_id,
        message_id=conversation_context.assistant_message_id,
    )


def _mark_stream_message_failed(
    *,
    message_id: str,
    message: str,
    request_id: str,
    trace_id: str,
    degrade_reason: str,
) -> None:
    try:
        with session_scope() as session:
            QueryConversationService().fail_assistant_message(
                session,
                message_id=message_id,
                message=message,
                request_id=request_id,
                trace_id=trace_id,
                degrade_reason=degrade_reason,
            )
    except Exception:
        # SSE 错误事件仍要尽量返回，消息状态补偿失败不能覆盖原始查询错误。
        return


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


def _conversation_response(detail: QueryConversationDetail) -> QueryConversationResponse:
    return QueryConversationResponse(
        request_id=_request_id(),
        data=_conversation_data(detail.conversation),
        messages=[_message_data(message) for message in detail.messages],
        messages_pagination={
            "page": detail.message_page,
            "page_size": detail.message_page_size,
            "total": detail.message_total,
        },
    )


def _conversation_data(conversation: QueryConversationSummary) -> QueryConversationData:
    return QueryConversationData(
        id=conversation.id,
        title=conversation.title,
        status="active" if conversation.status == "active" else "deleted",
        kb_ids=list(conversation.kb_ids),
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_data(message: QueryMessage) -> QueryMessageData:
    return QueryMessageData(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        status=message.status,
        citations=[_citation_data(citation) for citation in message.citations],
        confidence=message.confidence,
        degraded=message.degraded,
        degrade_reason=message.degrade_reason,
        debug_id=_public_debug_id(message.request_id, message.trace_id),
        created_at=message.created_at,
        updated_at=message.updated_at,
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


def _public_debug_id(*values: str | None) -> str | None:
    seed = "|".join(value for value in values if value)
    if not seed:
        return None
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"dbg_{digest}"


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
