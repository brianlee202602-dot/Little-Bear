"""Query log, model-call log, and audit writer."""

from __future__ import annotations

import json
import uuid

from app.modules.answer.schemas import AnswerGenerationResult
from app.modules.audit import AuditWriter
from app.modules.query.schemas import _QueryAuditEvent
from app.modules.query.utils import _database_error, _query_hash
from app.modules.retrieval import RetrievalModelCall
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class QueryLogWriter:
    """Persist query execution logs and related model/audit records."""

    def insert_denied_query_log(
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
        self.insert_query_log(
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
            model_route_hash=None,
            latency_ms=latency_ms,
            candidate_count=0,
            citation_count=0,
            error_code=error_code,
        )

    def insert_query_log(
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
        model_route_hash: str | None,
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
                        :model_route_hash, :latency_ms, :candidate_count, :citation_count,
                        :error_code
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
                    "model_route_hash": model_route_hash,
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

    def insert_model_call_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        config_version: int,
        caller: str,
        answer_result: AnswerGenerationResult,
    ) -> None:
        status = "success" if not answer_result.degraded else "failed"
        try:
            session.execute(
                text(
                    """
                    INSERT INTO model_call_logs(
                        id, enterprise_id, request_id, trace_id, config_version,
                        caller, model_type, model_name, model_version, model_route_hash,
                        status, degraded, latency_ms, token_usage_json, prompt_hash,
                        input_hash, output_hash, error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, :config_version, :caller, :model_type, :model_name,
                        :model_version, :model_route_hash, :status, :degraded, :latency_ms,
                        CAST(:token_usage_json AS jsonb), :prompt_hash, :input_hash,
                        :output_hash, :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "config_version": config_version,
                    "caller": caller,
                    "model_type": answer_result.model_type,
                    "model_name": answer_result.model_name or "unknown",
                    "model_version": answer_result.model_version,
                    "model_route_hash": answer_result.model_route_hash or "unknown",
                    "status": status,
                    "degraded": answer_result.degraded,
                    "latency_ms": answer_result.latency_ms or 0,
                    "token_usage_json": json.dumps(
                        answer_result.token_usage,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if answer_result.token_usage is not None
                    else None,
                    "prompt_hash": answer_result.prompt_hash,
                    "input_hash": answer_result.input_hash,
                    "output_hash": answer_result.output_hash,
                    "error_code": answer_result.degrade_reason if answer_result.degraded else None,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_MODEL_CALL_LOG_WRITE_FAILED",
                "model call log cannot be written",
                exc,
            ) from exc

    def insert_retrieval_model_call_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        config_version: int,
        caller: str,
        model_call: RetrievalModelCall,
    ) -> None:
        try:
            session.execute(
                text(
                    """
                    INSERT INTO model_call_logs(
                        id, enterprise_id, request_id, trace_id, config_version,
                        caller, model_type, model_name, model_version, model_route_hash,
                        status, degraded, latency_ms, token_usage_json, prompt_hash,
                        input_hash, output_hash, error_code
                    )
                    VALUES (
                        CAST(:id AS uuid), CAST(:enterprise_id AS uuid), :request_id,
                        :trace_id, :config_version, :caller, :model_type, :model_name,
                        :model_version, :model_route_hash, :status, :degraded, :latency_ms,
                        CAST(:token_usage_json AS jsonb), :prompt_hash, :input_hash,
                        :output_hash, :error_code
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "enterprise_id": enterprise_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "config_version": config_version,
                    "caller": caller,
                    "model_type": model_call.model_type,
                    "model_name": model_call.model_name or "unknown",
                    "model_version": model_call.model_version,
                    "model_route_hash": model_call.model_route_hash or "unknown",
                    "status": model_call.status,
                    "degraded": model_call.degraded,
                    "latency_ms": model_call.latency_ms,
                    "token_usage_json": json.dumps(
                        model_call.token_usage,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if model_call.token_usage is not None
                    else None,
                    "prompt_hash": model_call.prompt_hash,
                    "input_hash": model_call.input_hash,
                    "output_hash": model_call.output_hash,
                    "error_code": model_call.error_code,
                },
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_MODEL_CALL_LOG_WRITE_FAILED",
                "model call log cannot be written",
                exc,
            ) from exc

    def insert_query_audit_log(
        self,
        session: Session,
        *,
        request_id: str,
        trace_id: str,
        enterprise_id: str,
        user_id: str,
        config_version: int,
        permission_version: int,
        index_version_hash: str | None,
        event: _QueryAuditEvent,
    ) -> None:
        try:
            AuditWriter().write(
                session,
                enterprise_id=enterprise_id,
                request_id=request_id,
                trace_id=trace_id,
                event_name=event.event_name,
                actor_type="user",
                actor_id=user_id,
                resource_type="query",
                resource_id=request_id,
                action="query",
                result=event.result,
                risk_level=event.risk_level,
                config_version=config_version,
                permission_version=permission_version,
                index_version_hash=index_version_hash,
                summary=event.summary,
                error_code=event.error_code,
            )
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_AUDIT_LOG_WRITE_FAILED",
                "query audit log cannot be written",
                exc,
            ) from exc
