"""Permission guard for knowledge browsing."""

from __future__ import annotations

from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.permissions import PermissionService, PermissionServiceError
from app.modules.permissions.schemas import PermissionContext
from sqlalchemy.orm import Session


class KnowledgeAccessGuard:
    """Translate permission service failures to knowledge-domain errors."""

    def __init__(self, permission_service: PermissionService | None = None) -> None:
        self.permission_service = permission_service or PermissionService()

    def permission_context(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        request_id: str | None,
        required_scope: str,
    ) -> PermissionContext:
        try:
            context = self.permission_service.build_context(
                session,
                user_id=user_id,
                enterprise_id=enterprise_id,
                request_id=request_id,
            )
            self.permission_service.require_scope(context, required_scope)
            return context
        except PermissionServiceError as exc:
            raise KnowledgeServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def ensure_queryable_knowledge_base(
        self,
        session: Session,
        context: PermissionContext,
        *,
        kb_id: str,
    ) -> None:
        try:
            self.permission_service.require_queryable_knowledge_bases(
                session,
                context,
                kb_ids=(kb_id,),
                required_scope="document:read",
            )
        except PermissionServiceError as exc:
            raise KnowledgeServiceError(
                exc.error_code,
                "knowledge base is not accessible",
                status_code=404 if exc.status_code == 404 else exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc
