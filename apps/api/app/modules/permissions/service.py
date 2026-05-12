"""Permission Service P0 核心实现。

本服务把用户身份、部门、角色和文档可见性收敛成统一权限上下文，并生成向量检索、
关键词检索和元数据查询可以复用的过滤条件。查询候选进入上下文前也必须复用这里的
gate，避免只在召回后做松散过滤。
"""

from __future__ import annotations

import json
from typing import Any

from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.schemas import (
    CandidateGateResult,
    CandidateMetadata,
    PermissionContext,
    PermissionDepartment,
    PermissionFilter,
    PermissionRole,
)
from app.shared.json_utils import stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

BASE_USER_SCOPES = ("auth:session", "auth:password:update:self")
SUPPORTED_VISIBILITIES = {"department", "enterprise"}
UNSUPPORTED_POLICY_KEYS = {
    "user_ids",
    "project_ids",
    "group_ids",
    "custom_org_ids",
    "acl_entries",
    "allow_users",
    "deny_users",
    "recursive_departments",
    "include_child_departments",
    "include_parent_departments",
}


class PermissionService:
    """构建权限上下文、检索过滤条件和候选准入判定。"""

    def build_context(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str | None = None,
        request_id: str | None = None,
    ) -> PermissionContext:
        user_row = self._load_user(session, user_id=user_id, enterprise_id=enterprise_id)
        user = user_row
        if user["status"] != "active":
            raise PermissionServiceError(
                "PERM_DENIED",
                "user is not active",
                details={"user_id": user_id, "status": user["status"]},
            )

        versions = self._load_enterprise_versions(session, enterprise_id=user["enterprise_id"])
        departments = self._load_departments(
            session,
            user_id=user_id,
            enterprise_id=user["enterprise_id"],
        )
        roles = self._load_roles(session, user_id=user_id, enterprise_id=user["enterprise_id"])
        scopes = _merge_scopes(roles)
        department_ids = tuple(department.id for department in departments)
        filter_hash = _permission_filter_hash(
            enterprise_id=user["enterprise_id"],
            user_id=user_id,
            department_ids=department_ids,
            scopes=scopes,
            permission_version=versions["permission_version"],
            org_version=versions["org_version"],
        )
        return PermissionContext(
            enterprise_id=user["enterprise_id"],
            user_id=user_id,
            username=user["username"],
            status=user["status"],
            department_ids=department_ids,
            departments=departments,
            roles=roles,
            scopes=scopes,
            permission_version=versions["permission_version"],
            org_version=versions["org_version"],
            permission_filter_hash=filter_hash,
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
        fail_closed_on_stale_index: bool = True,
    ) -> PermissionFilter:
        if required_scope:
            self.require_scope(context, required_scope)

        normalized_kb_ids = _normalize_ids(kb_ids or ())
        normalized_index_ids = _normalize_ids(active_index_version_ids or ())
        params: dict[str, Any] = {
            "enterprise_id": context.enterprise_id,
            "department_ids": list(context.department_ids),
            "permission_version": context.permission_version,
        }
        if normalized_kb_ids:
            params["kb_ids"] = list(normalized_kb_ids)
        if normalized_index_ids:
            params["active_index_version_ids"] = list(normalized_index_ids)

        return PermissionFilter(
            enterprise_id=context.enterprise_id,
            department_ids=context.department_ids,
            kb_ids=normalized_kb_ids,
            active_index_version_ids=normalized_index_ids,
            permission_version=context.permission_version,
            permission_filter_hash=context.permission_filter_hash,
            qdrant_filter=_build_qdrant_filter(
                context,
                kb_ids=normalized_kb_ids,
                active_index_version_ids=normalized_index_ids,
                fail_closed_on_stale_index=fail_closed_on_stale_index,
            ),
            keyword_where_sql=_build_keyword_where_sql(
                has_departments=bool(context.department_ids),
                has_kb_filter=bool(normalized_kb_ids),
                has_index_filter=bool(normalized_index_ids),
                fail_closed_on_stale_index=fail_closed_on_stale_index,
            ),
            metadata_where_sql=_build_metadata_where_sql(
                has_departments=bool(context.department_ids),
                has_kb_filter=bool(normalized_kb_ids),
                has_index_filter=bool(normalized_index_ids),
                fail_closed_on_stale_index=fail_closed_on_stale_index,
            ),
            params=params,
        )

    def validate_visibility_policy(self, policy: dict[str, Any]) -> None:
        unsupported = sorted(UNSUPPORTED_POLICY_KEYS.intersection(policy))
        if unsupported:
            raise PermissionServiceError(
                "UNSUPPORTED_PERMISSION_POLICY",
                "P0 permission policy only supports visibility and owner_department_id",
                status_code=400,
                details={"unsupported_keys": unsupported},
            )
        visibility = policy.get("visibility")
        if visibility not in SUPPORTED_VISIBILITIES:
            raise PermissionServiceError(
                "PERM_VISIBILITY_INVALID",
                "document visibility must be department or enterprise",
                status_code=400,
                details={"visibility": visibility},
            )
        owner_department_id = policy.get("owner_department_id")
        if visibility == "department" and not owner_department_id:
            raise PermissionServiceError(
                "PERM_POLICY_INVALID",
                "department visibility requires owner_department_id",
                status_code=400,
            )

    def build_permission_snapshot_payload(
        self,
        *,
        owner_department_id: str,
        visibility: str,
        permission_version: int,
        policy_version: int,
    ) -> dict[str, Any]:
        self.validate_visibility_policy(
            {"owner_department_id": owner_department_id, "visibility": visibility}
        )
        payload = {
            "owner_department_id": owner_department_id,
            "visibility": visibility,
            "permission_version": permission_version,
            "policy_version": policy_version,
        }
        return {
            "payload": payload,
            "payload_hash": stable_json_hash(payload),
        }

    def gate_candidate(
        self,
        context: PermissionContext,
        candidate: CandidateMetadata,
        *,
        allowed_kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
    ) -> CandidateGateResult:
        allowed_kbs = set(_normalize_ids(allowed_kb_ids or ()))
        active_indexes = set(_normalize_ids(active_index_version_ids or ()))

        if candidate.enterprise_id != context.enterprise_id:
            return _gate_denied(
                "PERM_DENIED",
                "candidate enterprise does not match permission context",
                enterprise_id=candidate.enterprise_id,
            )
        if candidate.access_blocked:
            return _gate_denied("PERM_ACCESS_BLOCKED", "candidate has active access block")
        if allowed_kbs and candidate.kb_id not in allowed_kbs:
            return _gate_denied("PERM_DENIED", "candidate knowledge base is outside request scope")
        if active_indexes and candidate.index_version_id not in active_indexes:
            return _gate_denied("PERM_VERSION_STALE", "candidate index version is not active")
        if candidate.visibility_state != "active":
            return _gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate visibility state is not active",
                visibility_state=candidate.visibility_state,
            )
        if candidate.document_lifecycle_status != "active":
            return _gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate document is not active",
                document_lifecycle_status=candidate.document_lifecycle_status,
            )
        if candidate.document_index_status != "indexed":
            return _gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate document is not indexed",
                document_index_status=candidate.document_index_status,
            )
        if candidate.chunk_status != "active":
            return _gate_denied(
                "PERM_ACCESS_BLOCKED",
                "candidate chunk is not active",
                chunk_status=candidate.chunk_status,
            )
        if (
            candidate.indexed_permission_version is not None
            and candidate.indexed_permission_version < context.permission_version
        ):
            return _gate_denied(
                "PERM_VERSION_STALE",
                "candidate indexed permission version is stale",
                indexed_permission_version=candidate.indexed_permission_version,
                permission_version=context.permission_version,
            )
        if candidate.visibility == "enterprise":
            return CandidateGateResult(allowed=True, reason="enterprise_visible")
        if candidate.visibility == "department":
            if candidate.owner_department_id in context.department_ids:
                return CandidateGateResult(allowed=True, reason="department_visible")
            return _gate_denied(
                "PERM_DENIED",
                "candidate owner department is not accessible",
                owner_department_id=candidate.owner_department_id,
            )
        return _gate_denied(
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

    def _load_user(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str | None,
    ) -> dict[str, Any]:
        conditions = ["id = CAST(:user_id AS uuid)", "deleted_at IS NULL"]
        params = {"user_id": user_id}
        if enterprise_id is not None:
            conditions.append("enterprise_id = CAST(:enterprise_id AS uuid)")
            params["enterprise_id"] = enterprise_id
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS user_id,
                        enterprise_id::text AS enterprise_id,
                        username,
                        status
                    FROM users
                    WHERE {" AND ".join(conditions)}
                    LIMIT 1
                    """
                ),
                params,
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission user context cannot be loaded",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "PERM_DENIED",
                "user is not found",
                details={"user_id": user_id},
            )
        return dict(row._mapping)

    def _load_enterprise_versions(self, session: Session, *, enterprise_id: str) -> dict[str, int]:
        try:
            row = session.execute(
                text(
                    """
                    SELECT org_version, permission_version
                    FROM enterprises
                    WHERE id = CAST(:enterprise_id AS uuid)
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission versions cannot be loaded",
                exc,
            ) from exc
        if row is None:
            raise PermissionServiceError(
                "PERM_DENIED",
                "enterprise is not active",
                details={"enterprise_id": enterprise_id},
            )
        return {
            "org_version": int(row._mapping["org_version"]),
            "permission_version": int(row._mapping["permission_version"]),
        }

    def _load_departments(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
    ) -> tuple[PermissionDepartment, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS department_id,
                        d.code,
                        d.name,
                        udm.is_primary
                    FROM user_department_memberships udm
                    JOIN departments d ON d.id = udm.department_id
                    WHERE udm.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND udm.user_id = CAST(:user_id AS uuid)
                      AND udm.status = 'active'
                      AND d.status = 'active'
                      AND d.deleted_at IS NULL
                    ORDER BY udm.is_primary DESC, d.code
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission departments cannot be loaded",
                exc,
            ) from exc
        return tuple(
            PermissionDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                is_primary=bool(row._mapping["is_primary"]),
            )
            for row in rows
        )

    def _load_roles(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
    ) -> tuple[PermissionRole, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        r.id::text AS role_id,
                        r.code,
                        r.name,
                        rb.scope_type,
                        rb.scope_id::text AS scope_id,
                        r.scopes
                    FROM role_bindings rb
                    JOIN roles r ON r.id = rb.role_id
                    WHERE rb.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND rb.user_id = CAST(:user_id AS uuid)
                      AND rb.status = 'active'
                      AND r.status = 'active'
                    ORDER BY r.code, rb.scope_type, rb.scope_id
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "PERM_CONTEXT_UNAVAILABLE",
                "permission roles cannot be loaded",
                exc,
            ) from exc
        return tuple(
            PermissionRole(
                id=row._mapping["role_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                scope_type=row._mapping["scope_type"],
                scope_id=row._mapping["scope_id"],
                scopes=_normalize_scopes(row._mapping["scopes"]),
            )
            for row in rows
        )


def _build_qdrant_filter(
    context: PermissionContext,
    *,
    kb_ids: tuple[str, ...],
    active_index_version_ids: tuple[str, ...],
    fail_closed_on_stale_index: bool,
) -> dict[str, Any]:
    must: list[dict[str, Any]] = [
        {"key": "enterprise_id", "match": {"value": context.enterprise_id}},
        {"key": "visibility_state", "match": {"value": "active"}},
        {"key": "document_status", "match": {"value": "active"}},
        {"key": "document_index_status", "match": {"value": "indexed"}},
        {"key": "chunk_status", "match": {"value": "active"}},
        {"key": "is_deleted", "match": {"value": False}},
    ]
    if kb_ids:
        must.append({"key": "kb_id", "match": {"any": list(kb_ids)}})
    if active_index_version_ids:
        must.append({"key": "index_version_id", "match": {"any": list(active_index_version_ids)}})
    if fail_closed_on_stale_index:
        must.append({"key": "permission_version", "range": {"gte": context.permission_version}})

    visibility_should: list[dict[str, Any]] = [
        {"key": "visibility", "match": {"value": "enterprise"}},
    ]
    if context.department_ids:
        visibility_should.append(
            {
                "must": [
                    {"key": "visibility", "match": {"value": "department"}},
                    {
                        "key": "owner_department_id",
                        "match": {"any": list(context.department_ids)},
                    },
                ]
            }
        )
    return {"must": must, "should": visibility_should, "must_not": []}


def _build_keyword_where_sql(
    *,
    has_departments: bool,
    has_kb_filter: bool,
    has_index_filter: bool,
    fail_closed_on_stale_index: bool,
) -> str:
    conditions = [
        "kie.enterprise_id = CAST(:enterprise_id AS uuid)",
        "kie.visibility_state = 'active'",
        "d.lifecycle_status = 'active'",
        "d.index_status = 'indexed'",
        "c.status = 'active'",
        "cir.visibility_state = 'active'",
    ]
    if has_kb_filter:
        conditions.append("d.kb_id = ANY(CAST(:kb_ids AS uuid[]))")
    if has_index_filter:
        conditions.append("kie.index_version_id = ANY(CAST(:active_index_version_ids AS uuid[]))")
    if fail_closed_on_stale_index:
        conditions.append("kie.indexed_permission_version >= :permission_version")
        conditions.append("cir.indexed_permission_version >= :permission_version")
    conditions.append(_visibility_sql("kie", has_departments=has_departments))
    conditions.append(_access_block_not_exists_sql("d.id"))
    return "\nAND ".join(conditions)


def _build_metadata_where_sql(
    *,
    has_departments: bool,
    has_kb_filter: bool,
    has_index_filter: bool,
    fail_closed_on_stale_index: bool,
) -> str:
    conditions = [
        "d.enterprise_id = CAST(:enterprise_id AS uuid)",
        "d.lifecycle_status = 'active'",
        "d.index_status = 'indexed'",
        "c.status = 'active'",
        "cir.visibility_state = 'active'",
    ]
    if has_kb_filter:
        conditions.append("d.kb_id = ANY(CAST(:kb_ids AS uuid[]))")
    if has_index_filter:
        conditions.append("cir.index_version_id = ANY(CAST(:active_index_version_ids AS uuid[]))")
    if fail_closed_on_stale_index:
        conditions.append("cir.indexed_permission_version >= :permission_version")
    conditions.append(_visibility_sql("d", has_departments=has_departments))
    conditions.append(_access_block_not_exists_sql("d.id"))
    return "\nAND ".join(conditions)


def _visibility_sql(alias: str, *, has_departments: bool) -> str:
    department_clause = (
        f"({alias}.visibility = 'department' "
        f"AND {alias}.owner_department_id = ANY(CAST(:department_ids AS uuid[])))"
        if has_departments
        else "FALSE"
    )
    return f"({alias}.visibility = 'enterprise' OR {department_clause})"


def _access_block_not_exists_sql(resource_expr: str) -> str:
    return f"""
NOT EXISTS (
    SELECT 1
    FROM access_blocks ab
    WHERE ab.enterprise_id = CAST(:enterprise_id AS uuid)
      AND (
          (ab.resource_type = 'knowledge_base' AND ab.resource_id = d.kb_id)
          OR (ab.resource_type = 'folder' AND ab.resource_id = d.folder_id)
          OR (ab.resource_type = 'document' AND ab.resource_id = {resource_expr})
          OR (ab.resource_type = 'chunk' AND ab.resource_id = c.id)
      )
      AND ab.status = 'active'
      AND (ab.expires_at IS NULL OR ab.expires_at > now())
)
""".strip()


def _merge_scopes(roles: tuple[PermissionRole, ...]) -> tuple[str, ...]:
    scopes = set(BASE_USER_SCOPES)
    for role in roles:
        scopes.update(role.scopes)
    return tuple(sorted(scopes))


def _permission_filter_hash(
    *,
    enterprise_id: str,
    user_id: str,
    department_ids: tuple[str, ...],
    scopes: tuple[str, ...],
    permission_version: int,
    org_version: int,
) -> str:
    return stable_json_hash(
        {
            "enterprise_id": enterprise_id,
            "user_id": user_id,
            "department_ids": sorted(department_ids),
            "scopes": sorted(scopes),
            "permission_version": permission_version,
            "org_version": org_version,
        }
    )


def _normalize_ids(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


def _normalize_scopes(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return (value,)
        return _normalize_scopes(parsed)
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted({str(item) for item in value if str(item)}))
    return ()


def _gate_denied(error_code: str, reason: str, **details: Any) -> CandidateGateResult:
    return CandidateGateResult(
        allowed=False,
        reason=reason,
        error_code=error_code,
        details=details,
    )


def _database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> PermissionServiceError:
    return PermissionServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
