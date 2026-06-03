"""查询 SSE 流式路由。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import replace

from fastapi import APIRouter, Header
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse, StreamingResponse

from app.api.presenters.query import citation_data as _citation_data
from app.api.presenters.query import public_debug_id as _public_debug_id
from app.api.presenters.query import query_scope_data as _query_scope_data
from app.api.routes.query_execute import attach_conversation
from app.api.routes.query_shared import (
    _auth_error_response,
    _authenticate,
    _database_error_response,
    _extract_bearer_token,
    _query_error_response,
    _request_id,
    _trace_id,
)
from app.api.schemas.query import QueryRequest
from app.db.session import session_scope
from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.auth.errors import AuthServiceError
from app.modules.query.conversations import QueryConversationService
from app.modules.query.errors import QueryServiceError
from app.modules.query.runtime import build_query_service
from app.modules.query.schemas import QueryResult
from app.modules.query.service import QueryService, QueryStreamPlan

router = APIRouter(prefix="/internal/v1", tags=["query"])


@router.post("/query-streams", response_model=None)
async def create_query_stream(
    payload: QueryRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse | JSONResponse:
    stream_or_error = prepare_query_stream(payload, authorization=authorization)
    if isinstance(stream_or_error, JSONResponse):
        return stream_or_error
    if isinstance(stream_or_error, QueryResult):
        return StreamingResponse(
            query_sse_events(stream_or_error),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    service, plan = stream_or_error
    return StreamingResponse(
        query_stream_sse_events(service, plan),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def prepare_query_stream(
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
                    history=[message.model_dump() for message in payload.history],
                )
                QueryConversationService().update_conversation_kbs(
                    session,
                    conversation_id=conversation_context.conversation_id,
                    kb_ids=result.kb_ids,
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
                return attach_conversation(result, conversation_context)
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
                history=[message.model_dump() for message in payload.history],
            )
            QueryConversationService().update_conversation_kbs(
                session,
                conversation_id=conversation_context.conversation_id,
                kb_ids=plan.normalized_kb_ids,
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


def query_sse_events(result: QueryResult) -> Iterable[str]:
    yield sse_event(
        "metadata",
        {
            "debug_id": _public_debug_id(result.request_id, result.trace_id) or "dbg_unknown",
            "conversation_id": result.conversation_id,
            "message_id": result.message_id,
            "confidence": result.confidence,
            "degraded": result.degraded,
            "degrade_reason": result.degrade_reason,
            "query_scope": _query_scope_data(result).model_dump(),
        },
    )
    for token in stream_tokens(result.answer):
        yield sse_event("token", {"delta": token})
    for citation in result.citations:
        yield sse_event("citation", _citation_data(citation).model_dump())
    yield sse_event(
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
            "query_scope": _query_scope_data(result).model_dump(),
        },
    )


def query_stream_sse_events(service: QueryService, plan: QueryStreamPlan) -> Iterable[str]:
    yield sse_event(
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
            "query_scope": query_scope_from_plan(plan),
        },
    )
    if plan.mode == "answer":
        try:
            runner = service.answer_service.stream(query_context=plan.query_context)
            for token in runner.stream_tokens():
                yield sse_event("token", {"delta": token})
            answer_result = runner.result or AnswerGenerationResult(
                answer="",
                degraded=True,
                degrade_reason="llm_stream_result_missing",
            )
        except Exception as exc:
            answer_result = stream_error_answer_result(exc)
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
            mark_stream_message_failed(
                message_id=plan.message_id,
                message=getattr(exc, "message", "query stream finalization failed"),
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                degrade_reason=getattr(exc, "error_code", "QUERY_STREAM_FINALIZE_FAILED"),
            )
        yield sse_event(
            "error",
            {
                "debug_id": _public_debug_id(plan.request_id, plan.trace_id) or "dbg_unknown",
                "error_code": getattr(exc, "error_code", "QUERY_STREAM_FINALIZE_FAILED"),
                "message": getattr(exc, "message", "query stream finalization failed"),
            },
        )
        return
    except Exception as exc:
        if plan.message_id:
            mark_stream_message_failed(
                message_id=plan.message_id,
                message="query stream finalization failed",
                request_id=plan.request_id,
                trace_id=plan.trace_id,
                degrade_reason="QUERY_STREAM_FINALIZE_FAILED",
            )
        yield sse_event(
            "error",
            {
                "debug_id": _public_debug_id(plan.request_id, plan.trace_id) or "dbg_unknown",
                "error_code": "QUERY_STREAM_FINALIZE_FAILED",
                "message": "query stream finalization failed",
                "details": {"error_type": exc.__class__.__name__},
            },
        )
        return

    for citation in result.citations:
        yield sse_event("citation", _citation_data(citation).model_dump())
    yield sse_event(
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
            "query_scope": _query_scope_data(result).model_dump(),
        },
    )


def mark_stream_message_failed(
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


def stream_error_answer_result(exc: Exception) -> AnswerGenerationResult:
    error_code = getattr(exc, "error_code", None)
    if not isinstance(error_code, str) or not error_code:
        error_code = "LLM_PROVIDER_UNAVAILABLE"
    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message:
        raw_message = str(exc).strip()
        message = (
            f"{exc.__class__.__name__}: {raw_message}"
            if raw_message
            else exc.__class__.__name__
        )
    return AnswerGenerationResult(
        answer="",
        degraded=True,
        degrade_reason=error_code,
        model_call_attempted=True,
        error_message=message,
    )


def sse_event(event_name: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"


def query_scope_from_plan(plan: QueryStreamPlan) -> dict[str, object]:
    return {
        "mode": plan.query_scope_mode,
        "resolved_kb_count": len(plan.normalized_kb_ids),
    }


def stream_tokens(answer: str, *, chunk_size: int = 24) -> Iterable[str]:
    if not answer:
        return
    for index in range(0, len(answer), chunk_size):
        yield answer[index : index + chunk_size]


_prepare_query_stream = prepare_query_stream
_query_sse_events = query_sse_events
_query_stream_sse_events = query_stream_sse_events
_mark_stream_message_failed = mark_stream_message_failed
_stream_error_answer_result = stream_error_answer_result
_sse_event = sse_event
_stream_tokens = stream_tokens
