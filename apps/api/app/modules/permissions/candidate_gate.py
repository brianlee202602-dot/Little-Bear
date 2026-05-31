"""检索候选准入判定。"""

from __future__ import annotations

from typing import Any

from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.filter_builder import normalize_ids
from app.modules.permissions.schemas import (
    CandidateGateResult,
    CandidateMetadata,
    PermissionContext,
)


class PermissionCandidateGate:
    """对召回候选做最终权限 gate。"""

    def gate_candidate(
        self,
        context: PermissionContext,
        candidate: CandidateMetadata,
        *,
        allowed_kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
    ) -> CandidateGateResult:
        allowed_kbs = set(normalize_ids(allowed_kb_ids or ()))
        active_indexes = set(normalize_ids(active_index_version_ids or ()))

        if candidate.enterprise_id != context.enterprise_id:
            return gate_denied(
                "PERM_DENIED",
                "candidate enterprise does not match permission context",
                enterprise_id=candidate.enterprise_id,
            )
        if candidate.access_blocked:
            return gate_denied("PERM_ACCESS_BLOCKED", "candidate has active access block")
        if allowed_kbs and candidate.kb_id not in allowed_kbs:
            return gate_denied("PERM_DENIED", "candidate knowledge base is outside request scope")
        if active_indexes and candidate.index_version_id not in active_indexes:
            return gate_denied("PERM_VERSION_STALE", "candidate index version is not active")
        if candidate.visibility_state != "active":
            return gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate visibility state is not active",
                visibility_state=candidate.visibility_state,
            )
        if candidate.document_lifecycle_status != "active":
            return gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate document is not active",
                document_lifecycle_status=candidate.document_lifecycle_status,
            )
        if candidate.document_index_status != "indexed":
            return gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate document is not indexed",
                document_index_status=candidate.document_index_status,
            )
        if candidate.chunk_status != "active":
            return gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate chunk is not active",
                chunk_status=candidate.chunk_status,
            )
        if candidate.visibility == "enterprise":
            return CandidateGateResult(allowed=True, reason="enterprise_visible")
        if candidate.visibility == "department":
            if candidate.owner_department_id in context.department_ids:
                return CandidateGateResult(allowed=True, reason="department_visible")
            return gate_denied(
                "PERM_DENIED",
                "candidate owner department is not accessible",
                owner_department_id=candidate.owner_department_id,
            )
        return gate_denied(
            "PERM_VISIBILITY_INVALID",
            "candidate visibility is invalid",
            visibility=candidate.visibility,
        )

    def assert_candidate_allowed(
        self,
        context: PermissionContext,
        candidate: CandidateMetadata,
        *,
        allowed_kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        result = self.gate_candidate(
            context,
            candidate,
            allowed_kb_ids=allowed_kb_ids,
            active_index_version_ids=active_index_version_ids,
        )
        if not result.allowed:
            raise PermissionServiceError(
                result.error_code or "PERM_DENIED",
                result.reason,
                details=result.details,
            )


def gate_denied(error_code: str, reason: str, **details: Any) -> CandidateGateResult:
    return CandidateGateResult(
        allowed=False,
        reason=reason,
        error_code=error_code,
        details=details,
    )
