"""权限检索过滤条件构建。"""

from __future__ import annotations

from typing import Any

from app.modules.permissions.schemas import PermissionContext, PermissionFilter


class PermissionFilterBuilder:
    """构建向量、关键词和元数据检索可复用的权限过滤条件。"""

    def build_filter(
        self,
        context: PermissionContext,
        *,
        kb_ids: list[str] | tuple[str, ...] | None = None,
        active_index_version_ids: list[str] | tuple[str, ...] | None = None,
        fail_closed_on_stale_index: bool = False,
    ) -> PermissionFilter:
        normalized_kb_ids = normalize_ids(kb_ids or ())
        normalized_index_ids = normalize_ids(active_index_version_ids or ())
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
            qdrant_filter=build_qdrant_filter(
                context,
                kb_ids=normalized_kb_ids,
                active_index_version_ids=normalized_index_ids,
                fail_closed_on_stale_index=fail_closed_on_stale_index,
            ),
            keyword_where_sql=build_keyword_where_sql(
                has_departments=bool(context.department_ids),
                has_kb_filter=bool(normalized_kb_ids),
                has_index_filter=bool(normalized_index_ids),
                fail_closed_on_stale_index=fail_closed_on_stale_index,
            ),
            metadata_where_sql=build_metadata_where_sql(
                has_departments=bool(context.department_ids),
                has_kb_filter=bool(normalized_kb_ids),
                has_index_filter=bool(normalized_index_ids),
                fail_closed_on_stale_index=fail_closed_on_stale_index,
            ),
            params=params,
        )


def build_qdrant_filter(
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


def build_keyword_where_sql(
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
    conditions.append(visibility_sql("kie", has_departments=has_departments))
    conditions.append(access_block_not_exists_sql("d.id"))
    return "\nAND ".join(conditions)


def build_metadata_where_sql(
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
    conditions.append(visibility_sql("d", has_departments=has_departments))
    conditions.append(access_block_not_exists_sql("d.id"))
    return "\nAND ".join(conditions)


def visibility_sql(alias: str, *, has_departments: bool) -> str:
    department_clause = (
        f"({alias}.visibility = 'department' "
        f"AND {alias}.owner_department_id = ANY(CAST(:department_ids AS uuid[])))"
        if has_departments
        else "FALSE"
    )
    return f"({alias}.visibility = 'enterprise' OR {department_clause})"


def access_block_not_exists_sql(resource_expr: str) -> str:
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


def knowledge_base_access_where_sql(
    context: PermissionContext,
    params: dict[str, Any],
    *,
    permission: str,
    alias: str,
) -> str:
    if context.has_scope("knowledge_base:manage"):
        return "TRUE"
    implied_permissions = ["manage", permission] if permission != "manage" else ["manage"]
    params[f"{alias}_kb_access_permissions"] = implied_permissions
    subject_conditions = [
        f"(kba.subject_type = 'user' AND kba.subject_id = CAST(:{alias}_kb_access_user_id AS uuid))"
    ]
    params[f"{alias}_kb_access_user_id"] = context.user_id
    if context.department_ids:
        subject_conditions.append(
            f"(kba.subject_type = 'department' "
            f"AND kba.subject_id = ANY(CAST(:{alias}_kb_access_department_ids AS uuid[])))"
        )
        params[f"{alias}_kb_access_department_ids"] = list(context.department_ids)
    if context.role_ids:
        subject_conditions.append(
            f"(kba.subject_type = 'role' "
            f"AND kba.subject_id = ANY(CAST(:{alias}_kb_access_role_ids AS uuid[])))"
        )
        params[f"{alias}_kb_access_role_ids"] = list(context.role_ids)
    return f"""
(
    {alias}.kb_visibility = 'enterprise'
    OR EXISTS (
        SELECT 1
        FROM knowledge_base_accesses kba
        WHERE kba.enterprise_id = {alias}.enterprise_id
          AND kba.kb_id = {alias}.id
          AND kba.status = 'active'
          AND kba.permission = ANY(CAST(:{alias}_kb_access_permissions AS text[]))
          AND ({' OR '.join(subject_conditions)})
    )
)
""".strip()


def normalize_ids(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)
