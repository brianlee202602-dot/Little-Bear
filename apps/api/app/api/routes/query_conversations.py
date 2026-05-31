"""查询会话路由。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse, Response

from app.api.presenters.query import (
    conversation_data as _conversation_data,
)
from app.api.presenters.query import (
    conversation_response as _conversation_response,
)
from app.api.routes.query_shared import (
    DEFAULT_CONVERSATION_MESSAGE_PAGE_SIZE,
    _auth_error_response,
    _authenticate,
    _database_error_response,
    _extract_bearer_token,
    _query_error_response,
    _request_id,
)
from app.api.schemas.query import (
    QueryConversationCreateRequest,
    QueryConversationListResponse,
    QueryConversationResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.query.conversations import QueryConversationService
from app.modules.query.errors import QueryServiceError

router = APIRouter(prefix="/internal/v1", tags=["query"])


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
    return _conversation_response(detail, request_id=_request_id())


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

