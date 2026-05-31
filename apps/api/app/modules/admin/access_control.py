"""管理后台访问控制 helper。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.admin.errors import AdminServiceError
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AdminActorContext:
    """管理后台操作者的最小权限上下文。"""

    user_id: str
    scopes: tuple[str, ...]
    department_ids: tuple[str, ...] = ()
    role_ids: tuple[str, ...] = ()
    knowledge_base_ids: tuple[str, ...] = ()
    can_manage_all_knowledge_bases: bool = False


@dataclass(frozen=True)
class RoleBindingInput:
    role_id: str
    scope_type: str
    scope_id: str | None = None


class AdminAccessControlMixin:
    """Compatibility mixin exposing historical AdminService access helpers."""

    def _ensure_actor_can_access_user(
        self,
        session: Session,
        actor_context: AdminActorContext | None,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> None:
        ensure_actor_can_access_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def _ensure_actor_can_manage_user(
        self,
        session: Session,
        actor_context: AdminActorContext | None,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> None:
        ensure_actor_can_manage_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def _ensure_actor_can_create_user_departments(
        self,
        actor_context: AdminActorContext | None,
        departments: list[Any],
    ) -> None:
        ensure_actor_can_create_user_departments(actor_context, departments)

    def _ensure_actor_can_manage_departments(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        ensure_actor_can_manage_departments(actor_context)

    def _ensure_actor_can_manage_knowledge_bases(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        ensure_actor_can_manage_knowledge_bases(actor_context)

    def _ensure_actor_can_manage_folders(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        ensure_actor_can_manage_folders(actor_context)

    def _ensure_actor_can_manage_documents(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        ensure_actor_can_manage_documents(actor_context)

    def _ensure_actor_can_index_documents(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        ensure_actor_can_index_documents(actor_context)

    def _ensure_actor_can_manage_permissions(
        self,
        actor_context: AdminActorContext | None,
    ) -> None:
        ensure_actor_can_manage_permissions(actor_context)

    def _ensure_actor_can_manage_kb_owner(
        self,
        actor_context: AdminActorContext | None,
        owner_department_id: str,
    ) -> None:
        ensure_actor_can_manage_kb_owner(actor_context, owner_department_id)

    def _ensure_actor_can_access_knowledge_base(
        self,
        actor_context: AdminActorContext | None,
        knowledge_base: Any,
    ) -> None:
        ensure_actor_can_access_knowledge_base(actor_context, knowledge_base)

    def _ensure_actor_can_manage_document_owner(
        self,
        actor_context: AdminActorContext | None,
        *,
        kb_id: str,
        owner_department_id: str,
    ) -> None:
        ensure_actor_can_manage_document_owner(
            actor_context,
            kb_id=kb_id,
            owner_department_id=owner_department_id,
        )

    def _ensure_actor_can_manage_role_target_user(
        self,
        session: Session,
        actor_context: AdminActorContext | None,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> None:
        ensure_actor_can_manage_role_target_user(
            session,
            actor_context,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def _ensure_actor_can_grant_roles(
        self,
        actor_context: AdminActorContext | None,
        roles: list[Any],
    ) -> None:
        ensure_actor_can_grant_roles(actor_context, roles)

    def _ensure_actor_can_manage_role_scope(
        self,
        actor_context: AdminActorContext | None,
        *,
        role: Any,
        scope_type: str,
        scope_id: str | None,
    ) -> None:
        ensure_actor_can_manage_role_scope(
            actor_context,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
        )


def ensure_actor_can_access_user(
    session: Session,
    actor_context: Any | None,
    *,
    enterprise_id: str,
    user_id: str,
) -> None:
    if actor_context is None or actor_can_access_all_users(actor_context):
        return
    row = session.execute(
        text(
            """
            SELECT 1
            FROM user_department_memberships actor_udm
            JOIN user_department_memberships target_udm
              ON target_udm.department_id = actor_udm.department_id
            WHERE actor_udm.user_id = CAST(:actor_user_id AS uuid)
              AND actor_udm.enterprise_id = CAST(:enterprise_id AS uuid)
              AND actor_udm.status = 'active'
              AND target_udm.user_id = CAST(:target_user_id AS uuid)
              AND target_udm.enterprise_id = CAST(:enterprise_id AS uuid)
              AND target_udm.status = 'active'
            LIMIT 1
            """
        ),
        {
            "actor_user_id": actor_context.user_id,
            "target_user_id": user_id,
            "enterprise_id": enterprise_id,
        },
    ).one_or_none()
    if row is None:
        raise AdminServiceError(
            "ADMIN_RESOURCE_FORBIDDEN",
            "target user is outside actor management scope",
            status_code=403,
        )


def ensure_actor_can_manage_user(
    session: Session,
    actor_context: Any | None,
    *,
    enterprise_id: str,
    user_id: str,
) -> None:
    if actor_context is None:
        return
    ensure_scope(actor_context, "user:manage", "user management requires user:manage")
    ensure_actor_can_access_user(
        session,
        actor_context,
        enterprise_id=enterprise_id,
        user_id=user_id,
    )


def ensure_actor_can_create_user_departments(
    actor_context: Any | None,
    departments: list[Any],
) -> None:
    if actor_context is None:
        return
    ensure_scope(actor_context, "user:manage", "user creation requires user:manage")
    if actor_can_access_all_users(actor_context):
        return
    actor_department_ids = set(actor_context.department_ids)
    outside_department_ids = [
        department.id for department in departments if department.id not in actor_department_ids
    ]
    if outside_department_ids:
        raise AdminServiceError(
            "ADMIN_RESOURCE_FORBIDDEN",
            "user can only be created in actor departments",
            status_code=403,
            details={"department_ids": outside_department_ids},
        )


def ensure_actor_can_manage_departments(actor_context: Any | None) -> None:
    ensure_scope_if_actor(
        actor_context,
        "org:manage",
        "department management requires org:manage",
    )


def ensure_actor_can_manage_knowledge_bases(actor_context: Any | None) -> None:
    ensure_scope_if_actor(
        actor_context,
        "knowledge_base:manage",
        "knowledge base management requires knowledge_base:manage",
    )


def ensure_actor_can_manage_folders(actor_context: Any | None) -> None:
    ensure_scope_if_actor(
        actor_context,
        "folder:manage",
        "folder management requires folder:manage",
    )


def ensure_actor_can_manage_documents(actor_context: Any | None) -> None:
    ensure_scope_if_actor(
        actor_context,
        "document:manage",
        "document management requires document:manage",
    )


def ensure_actor_can_index_documents(actor_context: Any | None) -> None:
    ensure_scope_if_actor(
        actor_context,
        "document:index",
        "document indexing requires document:index",
    )


def ensure_actor_can_manage_permissions(actor_context: Any | None) -> None:
    ensure_scope_if_actor(
        actor_context,
        "permission:manage",
        "permission management requires permission:manage",
    )


def ensure_actor_can_manage_kb_owner(
    actor_context: Any | None,
    owner_department_id: str,
) -> None:
    if actor_context is None or actor_can_manage_all_knowledge_bases(actor_context):
        return
    if owner_department_id in actor_context.department_ids:
        return
    raise AdminServiceError(
        "ADMIN_RESOURCE_FORBIDDEN",
        "knowledge base owner department is outside actor management scope",
        status_code=403,
        details={"owner_department_id": owner_department_id},
    )


def ensure_actor_can_access_knowledge_base(
    actor_context: Any | None,
    knowledge_base: Any,
) -> None:
    if actor_context is None or actor_can_manage_all_knowledge_bases(actor_context):
        return
    if actor_has_knowledge_base_scope(actor_context, knowledge_base.id):
        return
    if knowledge_base.owner_department_id in actor_context.department_ids:
        return
    if actor_has_kb_access_rule(actor_context, knowledge_base.access_rules, "manage"):
        return
    raise AdminServiceError(
        "ADMIN_RESOURCE_FORBIDDEN",
        "knowledge base is outside actor management scope",
        status_code=403,
        details={"kb_id": knowledge_base.id},
    )


def ensure_actor_can_manage_document_owner(
    actor_context: Any | None,
    *,
    kb_id: str,
    owner_department_id: str,
) -> None:
    if actor_context is None or actor_can_manage_all_knowledge_bases(actor_context):
        return
    if actor_has_knowledge_base_scope(actor_context, kb_id):
        return
    if owner_department_id in actor_context.department_ids:
        return
    raise AdminServiceError(
        "ADMIN_RESOURCE_FORBIDDEN",
        "document owner department is outside actor management scope",
        status_code=403,
        details={"kb_id": kb_id, "owner_department_id": owner_department_id},
    )


def ensure_actor_can_manage_role_target_user(
    session: Session,
    actor_context: Any | None,
    *,
    enterprise_id: str,
    user_id: str,
) -> None:
    if actor_context is None:
        return
    missing = [
        scope
        for scope in ("role:manage", "user:manage")
        if not has_scope(actor_context.scopes, scope)
    ]
    if missing:
        raise AdminServiceError(
            "ADMIN_SCOPE_REQUIRED",
            "role binding management requires role:manage and user:manage",
            status_code=403,
            details={"required_scopes": missing},
        )
    ensure_actor_can_access_user(
        session,
        actor_context,
        enterprise_id=enterprise_id,
        user_id=user_id,
    )


def ensure_actor_can_grant_roles(actor_context: Any | None, roles: list[Any]) -> None:
    if actor_context is None or not roles:
        return
    ensure_scope(actor_context, "role:manage", "explicit role grants require role:manage")


def ensure_actor_can_manage_role_scope(
    actor_context: Any | None,
    *,
    role: Any,
    scope_type: str,
    scope_id: str | None,
) -> None:
    if actor_context is None or actor_can_manage_all_role_scopes(actor_context):
        return
    if scope_type == "department" and scope_id in actor_context.department_ids:
        return
    if scope_type == "knowledge_base" and actor_has_knowledge_base_scope(
        actor_context,
        scope_id,
    ):
        return
    raise AdminServiceError(
        "ADMIN_RESOURCE_FORBIDDEN",
        "role binding scope is outside actor management scope",
        status_code=403,
        details={"role_code": role.code, "scope_type": scope_type, "scope_id": scope_id},
    )


def ensure_scope_if_actor(actor_context: Any | None, required_scope: str, message: str) -> None:
    if actor_context is None:
        return
    ensure_scope(actor_context, required_scope, message)


def ensure_scope(actor_context: Any, required_scope: str, message: str) -> None:
    if has_scope(actor_context.scopes, required_scope):
        return
    raise AdminServiceError(
        "ADMIN_SCOPE_REQUIRED",
        message,
        status_code=403,
        details={"required_scope": required_scope},
    )


def has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes


def actor_can_access_all_users(actor_context: Any) -> bool:
    return "*" in actor_context.scopes or "user:*" in actor_context.scopes


def actor_can_manage_all_role_scopes(actor_context: Any) -> bool:
    return (
        "*" in actor_context.scopes
        or "role:*" in actor_context.scopes
        or "role:manage" in actor_context.scopes
    )


def actor_can_manage_all_knowledge_bases(actor_context: Any) -> bool:
    return bool(actor_context.can_manage_all_knowledge_bases)


def actor_has_knowledge_base_scope(actor_context: Any, kb_id: str | None) -> bool:
    if kb_id is None:
        return False
    return kb_id in actor_context.knowledge_base_ids


def actor_has_kb_access_rule(
    actor_context: Any,
    access_rules: Any,
    permission: str,
) -> bool:
    implied_permissions = {permission}
    if permission in {"discover", "query"}:
        implied_permissions.add("manage")
    for rule in access_rules:
        if rule.permission not in implied_permissions:
            continue
        if rule.subject_type == "user" and rule.subject_id == actor_context.user_id:
            return True
        if rule.subject_type == "department" and rule.subject_id in actor_context.department_ids:
            return True
        if rule.subject_type == "role" and rule.subject_id in actor_context.role_ids:
            return True
    return False


def permission_admin_actor_context(
    actor_context: AdminActorContext | None,
) -> AdminActorContext | None:
    if actor_context is None:
        return None
    scopes = set(actor_context.scopes)
    scopes.update({"document:manage", "knowledge_base:manage"})
    return AdminActorContext(
        user_id=actor_context.user_id,
        scopes=tuple(sorted(scopes)),
        department_ids=actor_context.department_ids,
        role_ids=actor_context.role_ids,
        knowledge_base_ids=actor_context.knowledge_base_ids,
        can_manage_all_knowledge_bases=True,
    )


def actor_kb_manage_acl_sql(
    actor_context: AdminActorContext,
    params: dict[str, Any],
    *,
    kb_id_expr: str,
) -> str:
    subject_conditions = [
        "(kba.subject_type = 'user' AND kba.subject_id = CAST(:actor_user_id AS uuid))"
    ]
    params["actor_user_id"] = actor_context.user_id
    if actor_context.department_ids:
        subject_conditions.append(
            "(kba.subject_type = 'department' "
            "AND kba.subject_id = ANY(CAST(:actor_department_ids AS uuid[])))"
        )
        params["actor_department_ids"] = list(actor_context.department_ids)
    if actor_context.role_ids:
        subject_conditions.append(
            "(kba.subject_type = 'role' "
            "AND kba.subject_id = ANY(CAST(:actor_role_ids AS uuid[])))"
        )
        params["actor_role_ids"] = list(actor_context.role_ids)
    return f"""
EXISTS (
    SELECT 1
    FROM knowledge_base_accesses kba
    WHERE kba.enterprise_id = CAST(:enterprise_id AS uuid)
      AND kba.kb_id = {kb_id_expr}
      AND kba.status = 'active'
      AND kba.permission = 'manage'
      AND ({' OR '.join(subject_conditions)})
)
""".strip()
