"""普通查询路由。"""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, Header
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.presenters.query import query_response as _query_response
from app.api.routes.query_shared import (
    _auth_error_response,
    _authenticate,
    _database_error_response,
    _extract_bearer_token,
    _query_error_response,
    _request_id,
    _trace_id,
    structured_error_response,
)
from app.api.schemas.query import QueryRequest, QueryResponse
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.query.conversations import (
    QueryConversationService,
    QueryConversationWriteContext,
)
from app.modules.query.errors import QueryServiceError
from app.modules.query.runtime import build_query_service
from app.modules.query.schemas import QueryResult

router = APIRouter(prefix="/internal/v1", tags=["query"])


@router.post("/queries", response_model=QueryResponse)
async def create_query(
    payload: QueryRequest,
    authorization: str | None = Header(default=None),
) -> QueryResponse | JSONResponse:
    result_or_error = execute_query(payload, authorization=authorization, stage="query_create")
    if isinstance(result_or_error, JSONResponse):
        return result_or_error
    return _query_response(result_or_error)


def execute_query(
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
                result = attach_conversation(result, conversation_context)
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
        return structured_error_response(
            _request_id(),
            "QUERY_RESULT_MISSING",
            "query result is missing",
            stage=stage,
            status_code=500,
            retryable=True,
        )
    return result


def attach_conversation(
    result: QueryResult,
    conversation_context: QueryConversationWriteContext,
) -> QueryResult:
    return replace(
        result,
        conversation_id=conversation_context.conversation_id,
        message_id=conversation_context.assistant_message_id,
    )


_execute_query = execute_query
_attach_conversation = attach_conversation
