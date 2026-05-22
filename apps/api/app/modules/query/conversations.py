"""普通用户查询会话持久化服务。

该服务只负责用户查询工作区的会话窗口和消息落库。RAG 诊断事实仍在
query_logs / model_call_logs 中，二者不要混用。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import QueryCitation
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class QueryConversationSummary:
    id: str
    title: str
    status: str
    kb_ids: tuple[str, ...]
    last_message_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class QueryMessage:
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["running", "done", "error", "cancelled"]
    citations: tuple[QueryCitation, ...]
    confidence: Literal["low", "medium", "high"] | None
    degraded: bool
    degrade_reason: str | None
    request_id: str | None
    trace_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class QueryConversationDetail:
    conversation: QueryConversationSummary
    messages: tuple[QueryMessage, ...]


@dataclass(frozen=True)
class QueryConversationList:
    items: tuple[QueryConversationSummary, ...]
    total: int


@dataclass(frozen=True)
class QueryConversationWriteContext:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str


class QueryConversationService:
    """提供当前登录用户自己的查询会话读写能力。"""

    def list_conversations(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> QueryConversationList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        params = {
            "enterprise_id": enterprise_id,
            "user_id": user_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS id,
                        title,
                        status,
                        kb_ids,
                        last_message_at,
                        created_at,
                        updated_at
                    FROM query_conversations
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    ORDER BY COALESCE(last_message_at, updated_at, created_at) DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM query_conversations
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_CONVERSATION_LIST_FAILED",
                "query conversations cannot be listed",
                exc,
            ) from exc

        return QueryConversationList(
            items=tuple(_conversation_summary_from_mapping(dict(row._mapping)) for row in rows),
            total=int(total_row._mapping["total"]),
        )

    def create_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        title: str,
        kb_ids: tuple[str, ...],
    ) -> QueryConversationSummary:
        conversation_id = str(uuid.uuid4())
        normalized_title = _normalize_title(title)
        try:
            row = session.execute(
                text(
                    """
                    INSERT INTO query_conversations(
                        id, enterprise_id, user_id, title, status, kb_ids,
                        last_message_at
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid),
                        CAST(:user_id AS uuid), :title, 'active',
                        CAST(:kb_ids AS uuid[]), now()
                    )
                    RETURNING
                        id::text AS id,
                        title,
                        status,
                        kb_ids,
                        last_message_at,
                        created_at,
                        updated_at
                    """
                ),
                {
                    "id": conversation_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "title": normalized_title,
                    "kb_ids": list(kb_ids),
                },
            ).one()
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_CONVERSATION_CREATE_FAILED",
                "query conversation cannot be created",
                exc,
            ) from exc
        return _conversation_summary_from_mapping(dict(row._mapping))

    def get_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> QueryConversationDetail:
        conversation = self._load_owned_active_conversation(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS id,
                        conversation_id::text AS conversation_id,
                        role,
                        content,
                        status,
                        citations_json,
                        confidence,
                        degraded,
                        degrade_reason,
                        request_id,
                        trace_id,
                        created_at,
                        updated_at
                    FROM query_messages
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND conversation_id = CAST(:conversation_id AS uuid)
                    ORDER BY created_at ASC
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                },
            ).all()
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_CONVERSATION_READ_FAILED",
                "query conversation cannot be read",
                exc,
            ) from exc
        return QueryConversationDetail(
            conversation=conversation,
            messages=tuple(_message_from_mapping(dict(row._mapping)) for row in rows),
        )

    def delete_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> None:
        try:
            row = session.execute(
                text(
                    """
                    UPDATE query_conversations
                    SET status = 'deleted', deleted_at = now(), updated_at = now()
                    WHERE id = CAST(:conversation_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    RETURNING id::text AS id
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                },
            ).one_or_none()
            if row is not None:
                return
            owned_deleted = session.execute(
                text(
                    """
                    SELECT id
                    FROM query_conversations
                    WHERE id = CAST(:conversation_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'deleted'
                    LIMIT 1
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                },
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_CONVERSATION_DELETE_FAILED",
                "query conversation cannot be deleted",
                exc,
            ) from exc
        if owned_deleted is not None:
            return
        raise _conversation_not_found(conversation_id)

    def prepare_query_messages(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str | None,
        kb_ids: tuple[str, ...],
        query_text: str,
        request_id: str,
        trace_id: str,
    ) -> QueryConversationWriteContext:
        if conversation_id:
            conversation = self._load_owned_active_conversation(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        else:
            conversation = self.create_conversation(
                session,
                enterprise_id=enterprise_id,
                user_id=user_id,
                title=query_text,
                kb_ids=kb_ids,
            )
        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        try:
            session.execute(
                text(
                    """
                    UPDATE query_conversations
                    SET kb_ids = CAST(:kb_ids AS uuid[]),
                        last_message_at = now(),
                        updated_at = now()
                    WHERE id = CAST(:conversation_id AS uuid)
                    """
                ),
                {"conversation_id": conversation.id, "kb_ids": list(kb_ids)},
            )
            session.execute(
                text(
                    """
                    INSERT INTO query_messages(
                        id, conversation_id, enterprise_id, user_id, role, content,
                        status, citations_json, confidence, degraded, degrade_reason,
                        request_id, trace_id
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:conversation_id AS uuid),
                        CAST(:enterprise_id AS uuid), CAST(:user_id AS uuid),
                        'user', :content, 'done', '[]'::jsonb, NULL, false, NULL,
                        :request_id, :trace_id
                    )
                    """
                ),
                {
                    "id": user_message_id,
                    "conversation_id": conversation.id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "content": query_text,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            )
            session.execute(
                text(
                    """
                    INSERT INTO query_messages(
                        id, conversation_id, enterprise_id, user_id, role, content,
                        status, citations_json, confidence, degraded, degrade_reason,
                        request_id, trace_id
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:conversation_id AS uuid),
                        CAST(:enterprise_id AS uuid), CAST(:user_id AS uuid),
                        'assistant', '', 'running', '[]'::jsonb, NULL, false, NULL,
                        :request_id, :trace_id
                    )
                    """
                ),
                {
                    "id": assistant_message_id,
                    "conversation_id": conversation.id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            )
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_MESSAGE_CREATE_FAILED",
                "query conversation messages cannot be created",
                exc,
            ) from exc
        return QueryConversationWriteContext(
            conversation_id=conversation.id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )

    def complete_assistant_message(
        self,
        session: Session,
        *,
        message_id: str,
        answer: str,
        citations: tuple[QueryCitation, ...],
        confidence: Literal["low", "medium", "high"],
        degraded: bool,
        degrade_reason: str | None,
        request_id: str,
        trace_id: str,
    ) -> None:
        self._finish_assistant_message(
            session,
            message_id=message_id,
            content=answer,
            status="done",
            citations=citations,
            confidence=confidence,
            degraded=degraded,
            degrade_reason=degrade_reason,
            request_id=request_id,
            trace_id=trace_id,
        )

    def fail_assistant_message(
        self,
        session: Session,
        *,
        message_id: str,
        message: str,
        status: Literal["error", "cancelled"] = "error",
        request_id: str,
        trace_id: str,
        degrade_reason: str | None = None,
    ) -> None:
        self._finish_assistant_message(
            session,
            message_id=message_id,
            content=message,
            status=status,
            citations=(),
            confidence=None,
            degraded=True,
            degrade_reason=degrade_reason or message,
            request_id=request_id,
            trace_id=trace_id,
        )

    def _load_owned_active_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> QueryConversationSummary:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS id,
                        title,
                        status,
                        kb_ids,
                        last_message_at,
                        created_at,
                        updated_at
                    FROM query_conversations
                    WHERE id = CAST(:conversation_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                },
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_CONVERSATION_READ_FAILED",
                "query conversation cannot be read",
                exc,
            ) from exc
        if row is None:
            raise _conversation_not_found(conversation_id)
        return _conversation_summary_from_mapping(dict(row._mapping))

    def _finish_assistant_message(
        self,
        session: Session,
        *,
        message_id: str,
        content: str,
        status: Literal["done", "error", "cancelled"],
        citations: tuple[QueryCitation, ...],
        confidence: Literal["low", "medium", "high"] | None,
        degraded: bool,
        degrade_reason: str | None,
        request_id: str,
        trace_id: str,
    ) -> None:
        try:
            row = session.execute(
                text(
                    """
                    UPDATE query_messages
                    SET content = :content,
                        status = :status,
                        citations_json = CAST(:citations_json AS jsonb),
                        confidence = :confidence,
                        degraded = :degraded,
                        degrade_reason = :degrade_reason,
                        request_id = :request_id,
                        trace_id = :trace_id,
                        updated_at = now()
                    WHERE id = CAST(:message_id AS uuid)
                      AND role = 'assistant'
                    RETURNING conversation_id::text AS conversation_id
                    """
                ),
                {
                    "message_id": message_id,
                    "content": content,
                    "status": status,
                    "citations_json": _citations_json(citations),
                    "confidence": confidence,
                    "degraded": degraded,
                    "degrade_reason": degrade_reason,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            ).one_or_none()
            if row is None:
                raise QueryServiceError(
                    "QUERY_MESSAGE_NOT_FOUND",
                    "query assistant message does not exist",
                    status_code=404,
                    details={"message_id": message_id},
                )
            conversation_id = str(row._mapping["conversation_id"])
            session.execute(
                text(
                    """
                    UPDATE query_conversations
                    SET last_message_at = now(), updated_at = now()
                    WHERE id = CAST(:conversation_id AS uuid)
                    """
                ),
                {"conversation_id": conversation_id},
            )
        except SQLAlchemyError as exc:
            raise _conversation_database_error(
                "QUERY_MESSAGE_UPDATE_FAILED",
                "query assistant message cannot be updated",
                exc,
            ) from exc


def _conversation_summary_from_mapping(row: dict[str, object]) -> QueryConversationSummary:
    return QueryConversationSummary(
        id=str(row["id"]),
        title=str(row["title"]),
        status=str(row["status"]),
        kb_ids=tuple(str(item) for item in row.get("kb_ids") or ()),
        last_message_at=_datetime_or_none(row.get("last_message_at")),
        created_at=_datetime_or_none(row.get("created_at")),
        updated_at=_datetime_or_none(row.get("updated_at")),
    )


def _message_from_mapping(row: dict[str, object]) -> QueryMessage:
    return QueryMessage(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        role="user" if row["role"] == "user" else "assistant",
        content=str(row["content"]),
        status=_message_status(row["status"]),
        citations=_citations_from_json(row.get("citations_json")),
        confidence=_confidence_or_none(row.get("confidence")),
        degraded=bool(row["degraded"]),
        degrade_reason=row["degrade_reason"] if isinstance(row["degrade_reason"], str) else None,
        request_id=row["request_id"] if isinstance(row["request_id"], str) else None,
        trace_id=row["trace_id"] if isinstance(row["trace_id"], str) else None,
        created_at=_datetime_or_none(row.get("created_at")),
        updated_at=_datetime_or_none(row.get("updated_at")),
    )


def _citations_json(citations: tuple[QueryCitation, ...]) -> str:
    return json.dumps(
        [
            {
                "source_id": citation.source_id,
                "doc_id": citation.doc_id,
                "document_version_id": citation.document_version_id,
                "title": citation.title,
                "page_start": citation.page_start,
                "page_end": citation.page_end,
                "score": citation.score,
            }
            for citation in citations
        ],
        ensure_ascii=False,
    )


def _citations_from_json(value: object) -> tuple[QueryCitation, ...]:
    if not isinstance(value, list):
        return ()
    citations: list[QueryCitation] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            citations.append(
                QueryCitation(
                    source_id=str(item["source_id"]),
                    doc_id=str(item["doc_id"]),
                    document_version_id=str(item["document_version_id"]),
                    title=str(item["title"]),
                    page_start=int(item["page_start"]),
                    page_end=int(item["page_end"]),
                    score=float(item.get("score", 0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(citations)


def _normalize_title(value: str) -> str:
    title = " ".join(value.strip().split())
    if not title:
        return "新对话"
    return f"{title[:28]}..." if len(title) > 28 else title


def _message_status(value: object) -> Literal["running", "done", "error", "cancelled"]:
    if value in {"running", "done", "error", "cancelled"}:
        return value  # type: ignore[return-value]
    return "done"


def _confidence_or_none(value: object) -> Literal["low", "medium", "high"] | None:
    if value in {"low", "medium", "high"}:
        return value  # type: ignore[return-value]
    return None


def _datetime_or_none(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _conversation_not_found(conversation_id: str) -> QueryServiceError:
    return QueryServiceError(
        "QUERY_CONVERSATION_NOT_FOUND",
        "query conversation does not exist",
        status_code=404,
        details={"conversation_id": conversation_id},
    )


def _conversation_database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> QueryServiceError:
    return QueryServiceError(
        error_code,
        message,
        status_code=500,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
