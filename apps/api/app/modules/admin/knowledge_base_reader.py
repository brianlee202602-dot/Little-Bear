"""Knowledge-base administration read service."""

# ruff: noqa: F401

from __future__ import annotations

import uuid
from typing import Any

from app.modules.admin.access_control import (
    AdminActorContext,
    actor_can_manage_all_knowledge_bases,
    actor_kb_manage_acl_sql,
)
from app.modules.admin.errors import AdminServiceError
from app.modules.admin.events import _knowledge_base_update_event
from app.modules.admin.mappers import (
    _knowledge_base_list_item_from_mapping,
    _knowledge_base_option_from_mapping,
)
from app.modules.admin.policies import (
    _kb_access_rule_key,
    _kb_visibility_expands,
    _kb_visibility_policy_visibility,
    _normalize_kb_access_rules,
    _validate_kb_visibility,
    _validate_visibility,
)
from app.modules.admin.schemas import (
    AdminAcceptedResult,
    AdminKnowledgeBase,
    AdminKnowledgeBaseAccessRule,
    AdminKnowledgeBaseAccessRuleInput,
    AdminKnowledgeBaseList,
    AdminKnowledgeBaseOptionList,
)
from app.modules.admin.utils import _database_error
from app.modules.permissions.errors import PermissionServiceError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


class AdminKnowledgeBaseReader:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_knowledge_bases(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminKnowledgeBaseList:
        """读取知识库列表摘要，不返回访问规则和内部策略字段。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "knowledge_bases.enterprise_id = CAST(:enterprise_id AS uuid)",
            "knowledge_bases.deleted_at IS NULL",
            "knowledge_bases.status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("knowledge_bases.name ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("knowledge_bases.status = :status")
            params["status"] = status
        if actor_context and not actor_can_manage_all_knowledge_bases(actor_context):
            resource_conditions: list[str] = []
            if actor_context.department_ids:
                resource_conditions.append(
                    "knowledge_bases.owner_department_id = "
                    "ANY(CAST(:actor_department_ids AS uuid[]))"
                )
                params["actor_department_ids"] = list(actor_context.department_ids)
            if actor_context.knowledge_base_ids:
                resource_conditions.append(
                    "knowledge_bases.id = ANY(CAST(:actor_kb_ids AS uuid[]))"
                )
                params["actor_kb_ids"] = list(actor_context.knowledge_base_ids)
            acl_condition = actor_kb_manage_acl_sql(
                actor_context,
                params,
                kb_id_expr="knowledge_bases.id",
            )
            if acl_condition:
                resource_conditions.append(acl_condition)
            if resource_conditions:
                conditions.append(f"({' OR '.join(resource_conditions)})")
            else:
                conditions.append("FALSE")
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        knowledge_bases.id::text AS kb_id,
                        knowledge_bases.name,
                        knowledge_bases.status,
                        knowledge_bases.owner_department_id::text AS owner_department_id,
                        knowledge_bases.kb_visibility,
                        knowledge_bases.default_document_visibility,
                        knowledge_bases.default_document_owner_department_id::text
                            AS default_document_owner_department_id,
                        owner_department.name AS owner_department_name,
                        default_document_owner_department.name
                            AS default_document_owner_department_name
                    FROM knowledge_bases
                    LEFT JOIN departments owner_department
                      ON owner_department.id = knowledge_bases.owner_department_id
                     AND owner_department.enterprise_id = knowledge_bases.enterprise_id
                     AND owner_department.deleted_at IS NULL
                    LEFT JOIN departments default_document_owner_department
                      ON default_document_owner_department.id =
                         knowledge_bases.default_document_owner_department_id
                     AND default_document_owner_department.enterprise_id =
                         knowledge_bases.enterprise_id
                     AND default_document_owner_department.deleted_at IS NULL
                    WHERE {where_sql}
                    ORDER BY knowledge_bases.updated_at DESC, knowledge_bases.name
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM knowledge_bases WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASES_UNAVAILABLE",
                "knowledge bases cannot be read",
                exc,
            ) from exc
        return AdminKnowledgeBaseList(
            items=[_knowledge_base_list_item_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_knowledge_base_options(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        actor_context: AdminActorContext | None = None,
    ) -> AdminKnowledgeBaseOptionList:
        """读取知识库选择器选项，避免下拉框复用完整知识库详情 DTO。"""

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "knowledge_bases.enterprise_id = CAST(:enterprise_id AS uuid)",
            "knowledge_bases.deleted_at IS NULL",
            "knowledge_bases.status != 'deleted'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("knowledge_bases.name ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status:
            conditions.append("knowledge_bases.status = :status")
            params["status"] = status
        if actor_context and not actor_can_manage_all_knowledge_bases(actor_context):
            resource_conditions: list[str] = []
            if actor_context.department_ids:
                resource_conditions.append(
                    "knowledge_bases.owner_department_id = "
                    "ANY(CAST(:actor_department_ids AS uuid[]))"
                )
                params["actor_department_ids"] = list(actor_context.department_ids)
            if actor_context.knowledge_base_ids:
                resource_conditions.append(
                    "knowledge_bases.id = ANY(CAST(:actor_kb_ids AS uuid[]))"
                )
                params["actor_kb_ids"] = list(actor_context.knowledge_base_ids)
            acl_condition = actor_kb_manage_acl_sql(
                actor_context,
                params,
                kb_id_expr="knowledge_bases.id",
            )
            if acl_condition:
                resource_conditions.append(acl_condition)
            if resource_conditions:
                conditions.append(f"({' OR '.join(resource_conditions)})")
            else:
                conditions.append("FALSE")
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        knowledge_bases.id::text AS kb_id,
                        knowledge_bases.name,
                        knowledge_bases.status
                    FROM knowledge_bases
                    WHERE {where_sql}
                    ORDER BY knowledge_bases.updated_at DESC, knowledge_bases.name
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM knowledge_bases WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASE_OPTIONS_UNAVAILABLE",
                "knowledge base options cannot be read",
                exc,
            ) from exc
        return AdminKnowledgeBaseOptionList(
            items=[_knowledge_base_option_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_knowledge_base(
        self,
        session: Session,
        kb_id: str,
        *,
        enterprise_id: str,
        actor_context: AdminActorContext | None = None,
    ) -> AdminKnowledgeBase:
        """读取单个知识库详情，并按知识库级授权限制可管理范围。"""

        knowledge_base = self._core_service._load_knowledge_base(
            session,
            kb_id,
            enterprise_id=enterprise_id,
        )
        self._core_service._ensure_actor_can_access_knowledge_base(
            actor_context,
            knowledge_base,
        )
        return knowledge_base

