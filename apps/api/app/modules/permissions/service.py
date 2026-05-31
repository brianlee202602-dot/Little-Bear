"""Permission Service facade。

对外保留统一入口；内部职责拆分为上下文加载、检索过滤构建、策略校验和候选准入。
"""

from __future__ import annotations

from typing import Any

from app.modules.permissions.candidate_gate import PermissionCandidateGate
from app.modules.permissions.context_loader import (
    PermissionContextLoader,
    permission_database_error,
)
from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.filter_builder import (
    PermissionFilterBuilder,
    knowledge_base_access_where_sql,
    normalize_ids,
)
from app.modules.permissions.policy_validator import PermissionPolicyValidator
from app.modules.permissions.schemas import (
    CandidateGateResult,
    CandidateMetadata,
    PermissionContext,
    PermissionFilter,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class PermissionService:
    """构建权限上下文、检索过滤条件和候选准入判定。"""

    def __init__(
        self,
        *,
        context_loader: PermissionContextLoader | None = None,
        filter_builder: PermissionFilterBuilder | None = None,
        policy_validator: PermissionPolicyValidator | None = None,
        candidate_gate: PermissionCandidateGate | None = None,
    ) -> None:
        self.context_loader = context_loader or PermissionContextLoader()
        self.filter_builder = filter_builder or PermissionFilterBuilder()
        self.policy_validator = policy_validator or PermissionPolicyValidator()
        self.candidate_gate = candidate_gate or PermissionCandidateGate()

    def build_context(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str | None = None,
        request_id: str | None = None,
    ) -> PermissionContext:
        return self.context_loader.build_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
        )

    def require_scope(self, context: PermissionContext, required_scope: str) -> None:
        if not context.has_scope(required_scope):
            raise PermissionServiceError(
                "PERM_SCOPE_MISSING",
                "current user does not include required scope",
                details={"required_scope": required_scope},
            )

    def build_filter(
        self,
        context: PermissionContext,
        *,
        kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
        required_scope: str | None = None,
        fail_closed_on_stale_index: bool = False,
    ) -> PermissionFilter:
        if required_scope:
            self.require_scope(context, required_scope)
        return self.filter_builder.build_filter(
            context,
            kb_ids=kb_ids,
            active_index_version_ids=active_index_version_ids,
            fail_closed_on_stale_index=fail_closed_on_stale_index,
        )

    def require_queryable_knowledge_bases(
        self,
        session: Session,
        context: PermissionContext,
        *,
        kb_ids: list[str] | tuple[str, ...],
        required_scope: str = "rag:query",
    ) -> tuple[str, ...]:
        self.require_scope(context, required_scope)
        normalized_kb_ids = normalize_ids(kb_ids)
        params: dict[str, Any] = {
            "enterprise_id": context.enterprise_id,
            "kb_ids": list(normalized_kb_ids),
        }
        access_sql = knowledge_base_access_where_sql(
            context,
            params,
            permission="query",
            alias="kb",
        )
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT kb.id::text AS kb_id
                    FROM knowledge_bases kb
                    WHERE kb.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb.id = ANY(CAST(:kb_ids AS uuid[]))
                      AND kb.deleted_at IS NULL
                      AND kb.status = 'active'
                      AND {access_sql}
                    """
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            raise permission_database_error(
                "PERM_KB_ACCESS_UNAVAILABLE",
                "knowledge base access cannot be verified",
                exc,
            ) from exc
        allowed = {str(row._mapping["kb_id"]) for row in rows}
        if len(allowed) != len(normalized_kb_ids):
            raise PermissionServiceError(
                "PERM_KB_DENIED",
                "knowledge base is not accessible",
                status_code=404,
                details={
                    "requested_count": len(normalized_kb_ids),
                    "allowed_count": len(allowed),
                },
            )
        return tuple(kb_id for kb_id in normalized_kb_ids if kb_id in allowed)

    def validate_visibility_policy(self, policy: dict[str, Any]) -> None:
        self.policy_validator.validate_visibility_policy(policy)

    def build_permission_snapshot_payload(
        self,
        *,
        owner_department_id: str,
        visibility: str,
        permission_version: int,
        policy_version: int,
    ) -> dict[str, Any]:
        return self.policy_validator.build_permission_snapshot_payload(
            owner_department_id=owner_department_id,
            visibility=visibility,
            permission_version=permission_version,
            policy_version=policy_version,
        )

    def gate_candidate(
        self,
        context: PermissionContext,
        candidate: CandidateMetadata,
        *,
        allowed_kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
    ) -> CandidateGateResult:
        return self.candidate_gate.gate_candidate(
            context,
            candidate,
            allowed_kb_ids=allowed_kb_ids,
            active_index_version_ids=active_index_version_ids,
        )

    def assert_candidate_allowed(
        self,
        context: PermissionContext,
        candidate: CandidateMetadata,
        *,
        allowed_kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.candidate_gate.assert_candidate_allowed(
            context,
            candidate,
            allowed_kb_ids=allowed_kb_ids,
            active_index_version_ids=active_index_version_ids,
        )


__all__ = ["PermissionService", "knowledge_base_access_where_sql"]
