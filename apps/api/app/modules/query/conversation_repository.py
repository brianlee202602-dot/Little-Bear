"""查询会话 SQL 仓储。"""

from __future__ import annotations

import uuid
from typing import Literal

from app.modules.query.conversation_mappers import (
    citations_json,
    conversation_database_error,
    conversation_summary_from_mapping,
    message_from_mapping,
    normalize_title,
)
from app.modules.query.conversation_models import QueryConversationSummary, QueryMessage
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import QueryCitation
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class QueryConversationRepository:
    """集中查询会话和消息的 SQL 读写。"""

    def list_conversations(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[tuple[QueryConversationSummary, ...], int]:
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
            raise conversation_database_error(
                "QUERY_CONVERSATION_LIST_FAILED",
                "query conversations cannot be listed",
                exc,
            ) from exc
        return (
            tuple(conversation_summary_from_mapping(dict(row._mapping)) for row in rows),
            int(total_row._mapping["total"]),
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
        normalized_title = normalize_title(title)
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
            raise conversation_database_error(
                "QUERY_CONVERSATION_CREATE_FAILED",
                "query conversation cannot be created",
                exc,
            ) from exc
        return conversation_summary_from_mapping(dict(row._mapping))

    def load_owned_active_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> QueryConversationSummary | None:
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
            raise conversation_database_error(
                "QUERY_CONVERSATION_READ_FAILED",
                "query conversation cannot be read",
                exc,
            ) from exc
        return conversation_summary_from_mapping(dict(row._mapping)) if row is not None else None

    def list_messages(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
        page: int,
        page_size: int,
    ) -> tuple[tuple[QueryMessage, ...], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        try:
            rows = session.execute(
                text(
                    """
                    SELECT *
                    FROM (
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
                        ORDER BY created_at DESC, id DESC
                        LIMIT :limit OFFSET :offset
                    ) latest_messages
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM query_messages
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND user_id = CAST(:user_id AS uuid)
                      AND conversation_id = CAST(:conversation_id AS uuid)
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                },
            ).one()
        except SQLAlchemyError as exc:
            raise conversation_database_error(
                "QUERY_CONVERSATION_READ_FAILED",
                "query conversation cannot be read",
                exc,
            ) from exc
        return (
            tuple(message_from_mapping(dict(row._mapping)) for row in rows),
            int(total_row._mapping["total"]),
        )

    def delete_conversation(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        conversation_id: str,
    ) -> Literal["deleted", "already_deleted", "not_found"]:
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
                return "deleted"
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
            raise conversation_database_error(
                "QUERY_CONVERSATION_DELETE_FAILED",
                "query conversation cannot be deleted",
                exc,
            ) from exc
        return "already_deleted" if owned_deleted is not None else "not_found"

    def touch_conversation_kbs(
        self,
        session: Session,
        *,
        conversation_id: str,
        kb_ids: tuple[str, ...],
    ) -> None:
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
                {"conversation_id": conversation_id, "kb_ids": list(kb_ids)},
            )
        except SQLAlchemyError as exc:
            raise conversation_database_error(
                "QUERY_MESSAGE_CREATE_FAILED",
                "query conversation messages cannot be created",
                exc,
            ) from exc

    def insert_user_message(
        self,
        session: Session,
        *,
        message_id: str,
        conversation_id: str,
        enterprise_id: str,
        user_id: str,
        content: str,
        request_id: str,
        trace_id: str,
    ) -> None:
        try:
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
                    "id": message_id,
                    "conversation_id": conversation_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "content": content,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            )
        except SQLAlchemyError as exc:
            raise conversation_database_error(
                "QUERY_MESSAGE_CREATE_FAILED",
                "query conversation messages cannot be created",
                exc,
            ) from exc

    def insert_assistant_placeholder(
        self,
        session: Session,
        *,
        message_id: str,
        conversation_id: str,
        enterprise_id: str,
        user_id: str,
        request_id: str,
        trace_id: str,
    ) -> None:
        try:
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
                    "id": message_id,
                    "conversation_id": conversation_id,
                    "enterprise_id": enterprise_id,
                    "user_id": user_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            )
        except SQLAlchemyError as exc:
            raise conversation_database_error(
                "QUERY_MESSAGE_CREATE_FAILED",
                "query conversation messages cannot be created",
                exc,
            ) from exc

    def finish_assistant_message(
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
    ) -> str:
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
                    "citations_json": citations_json(citations),
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
            self.touch_conversation(session, conversation_id=conversation_id)
        except SQLAlchemyError as exc:
            raise conversation_database_error(
                "QUERY_MESSAGE_UPDATE_FAILED",
                "query assistant message cannot be updated",
                exc,
            ) from exc
        return conversation_id

    def touch_conversation(self, session: Session, *, conversation_id: str) -> None:
        try:
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
            raise conversation_database_error(
                "QUERY_MESSAGE_UPDATE_FAILED",
                "query assistant message cannot be updated",
                exc,
            ) from exc

