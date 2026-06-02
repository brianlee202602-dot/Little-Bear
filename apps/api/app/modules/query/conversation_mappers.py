"""查询会话映射、序列化和错误转换。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from app.modules.query.conversation_models import QueryConversationSummary, QueryMessage
from app.modules.query.errors import QueryServiceError
from app.modules.query.schemas import QueryCitation
from sqlalchemy.exc import SQLAlchemyError


def conversation_summary_from_mapping(row: dict[str, object]) -> QueryConversationSummary:
    return QueryConversationSummary(
        id=str(row["id"]),
        title=str(row["title"]),
        status=str(row["status"]),
        kb_ids=tuple(str(item) for item in row.get("kb_ids") or ()),
        last_message_at=datetime_or_none(row.get("last_message_at")),
        created_at=datetime_or_none(row.get("created_at")),
        updated_at=datetime_or_none(row.get("updated_at")),
    )


def message_from_mapping(row: dict[str, object]) -> QueryMessage:
    return QueryMessage(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        role="user" if row["role"] == "user" else "assistant",
        content=str(row["content"]),
        status=message_status(row["status"]),
        citations=citations_from_json(row.get("citations_json")),
        confidence=confidence_or_none(row.get("confidence")),
        degraded=bool(row["degraded"]),
        degrade_reason=row["degrade_reason"] if isinstance(row["degrade_reason"], str) else None,
        request_id=row["request_id"] if isinstance(row["request_id"], str) else None,
        trace_id=row["trace_id"] if isinstance(row["trace_id"], str) else None,
        created_at=datetime_or_none(row.get("created_at")),
        updated_at=datetime_or_none(row.get("updated_at")),
    )


def citations_json(citations: tuple[QueryCitation, ...]) -> str:
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


def citations_from_json(value: object) -> tuple[QueryCitation, ...]:
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


def normalize_title(value: str) -> str:
    title = " ".join(value.strip().split())
    if not title:
        return "新对话"
    return f"{title[:28]}..." if len(title) > 28 else title


def message_status(value: object) -> Literal["running", "done", "error", "cancelled"]:
    if value in {"running", "done", "error", "cancelled"}:
        return value  # type: ignore[return-value]
    return "done"


def confidence_or_none(value: object) -> Literal["low", "medium", "high"] | None:
    if value in {"low", "medium", "high"}:
        return value  # type: ignore[return-value]
    return None


def datetime_or_none(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def conversation_not_found(conversation_id: str) -> QueryServiceError:
    return QueryServiceError(
        "QUERY_CONVERSATION_NOT_FOUND",
        "query conversation does not exist",
        status_code=404,
        details={"conversation_id": conversation_id},
    )


def conversation_database_error(
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

