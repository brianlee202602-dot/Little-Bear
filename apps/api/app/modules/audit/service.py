"""Audit Service facade。

审计日志、查询日志、模型调用日志的读取实现分别由 reader 承担；这里保留
原 public API，避免路由和外部调用方在结构拆分时被迫同步修改。
"""

from __future__ import annotations

from app.modules.audit.audit_log_reader import AuditLogReader
from app.modules.audit.model_call_log_reader import ModelCallLogReader
from app.modules.audit.query_log_reader import QueryLogReader
from app.modules.audit.schemas import (
    AuditLog,
    AuditLogList,
    ModelCallLog,
    ModelCallLogList,
    QueryLog,
    QueryLogList,
)
from sqlalchemy.orm import Session


class AuditService:
    """审计读取 facade，兼容历史调用入口。"""

    def __init__(
        self,
        *,
        audit_log_reader: AuditLogReader | None = None,
        query_log_reader: QueryLogReader | None = None,
        model_call_log_reader: ModelCallLogReader | None = None,
    ) -> None:
        self.audit_log_reader = audit_log_reader or AuditLogReader()
        self.query_log_reader = query_log_reader or QueryLogReader()
        self.model_call_log_reader = model_call_log_reader or ModelCallLogReader()

    def list_audit_logs(
        self,
        session: Session,
        *,
        page: int,
        page_size: int,
        filters: dict[str, str | None] | None = None,
    ) -> AuditLogList:
        return self.audit_log_reader.list_audit_logs(
            session,
            page=page,
            page_size=page_size,
            filters=filters,
        )

    def get_audit_log(self, session: Session, audit_id: str) -> AuditLog:
        return self.audit_log_reader.get_audit_log(session, audit_id)

    def list_query_logs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        filters: dict[str, str | bool | None] | None = None,
    ) -> QueryLogList:
        return self.query_log_reader.list_query_logs(
            session,
            enterprise_id=enterprise_id,
            page=page,
            page_size=page_size,
            filters=filters,
        )

    def get_query_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        query_log_id: str,
    ) -> QueryLog:
        return self.query_log_reader.get_query_log(
            session,
            enterprise_id=enterprise_id,
            query_log_id=query_log_id,
        )

    def list_model_call_logs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        filters: dict[str, str | bool | None] | None = None,
    ) -> ModelCallLogList:
        return self.model_call_log_reader.list_model_call_logs(
            session,
            enterprise_id=enterprise_id,
            page=page,
            page_size=page_size,
            filters=filters,
        )

    def get_model_call_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        model_call_log_id: str,
    ) -> ModelCallLog:
        return self.model_call_log_reader.get_model_call_log(
            session,
            enterprise_id=enterprise_id,
            model_call_log_id=model_call_log_id,
        )
