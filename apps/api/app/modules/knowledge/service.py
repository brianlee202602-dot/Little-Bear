"""普通用户知识库浏览服务。"""

from __future__ import annotations

from typing import Any

from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.knowledge.schemas import (
    AccessibleChunk,
    AccessibleDocument,
    AccessibleDocumentList,
    AccessibleKnowledgeBase,
    AccessibleKnowledgeBaseList,
)
from app.modules.permissions import PermissionService, PermissionServiceError
from app.modules.permissions.schemas import PermissionContext
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class KnowledgeService:
    def __init__(self, *, permission_service: PermissionService | None = None) -> None:
        self.permission_service = permission_service or PermissionService()

    def list_knowledge_bases(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> AccessibleKnowledgeBaseList:
        context = self._permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope="knowledge_base:read",
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions = [
            "enterprise_id = CAST(:enterprise_id AS uuid)",
            "deleted_at IS NULL",
            "status = 'active'",
        ]
        params: dict[str, Any] = {
            "enterprise_id": context.enterprise_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if keyword:
            conditions.append("name ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status and status != "active":
            conditions.append("FALSE")
        resource_sql = _knowledge_base_visibility_sql(context, params)
        if resource_sql:
            conditions.append(resource_sql)
        where_sql = " AND ".join(conditions)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS kb_id,
                        name,
                        status,
                        owner_department_id::text AS owner_department_id,
                        default_visibility,
                        config_scope_id,
                        policy_version
                    FROM knowledge_bases
                    WHERE {where_sql}
                    ORDER BY updated_at DESC, name
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
                "KNOWLEDGE_BASES_UNAVAILABLE",
                "knowledge bases cannot be read",
                exc,
            ) from exc
        return AccessibleKnowledgeBaseList(
            items=[_knowledge_base_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_documents(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> AccessibleDocumentList:
        context = self._permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope="document:read",
        )
        active_index_ids = self._load_active_index_versions(
            session,
            enterprise_id=context.enterprise_id,
            kb_ids=(kb_id,),
        )
        if not active_index_ids:
            return AccessibleDocumentList(items=[], total=0)
        permission_filter = self.permission_service.build_filter(
            context,
            kb_ids=(kb_id,),
            active_index_version_ids=active_index_ids,
            required_scope="document:read",
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        params = dict(permission_filter.params)
        params.update({"limit": page_size, "offset": (page - 1) * page_size})
        filters: list[str] = []
        if keyword:
            filters.append("d.title ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status and status != "active":
            filters.append("FALSE")
        filter_sql = "".join(f"\n                      AND {condition}" for condition in filters)

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT DISTINCT
                        d.id::text AS document_id,
                        d.kb_id::text AS kb_id,
                        d.folder_id::text AS folder_id,
                        d.title,
                        d.lifecycle_status,
                        d.index_status,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.current_version_id::text AS current_version_id
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    JOIN chunk_index_refs cir ON cir.chunk_id = c.id
                    WHERE {permission_filter.metadata_where_sql}
                      {filter_sql}
                    ORDER BY d.title, document_id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    f"""
                    SELECT count(DISTINCT d.id) AS total
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    JOIN chunk_index_refs cir ON cir.chunk_id = c.id
                    WHERE {permission_filter.metadata_where_sql}
                      {filter_sql}
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_DOCUMENTS_UNAVAILABLE",
                "documents cannot be read",
                exc,
            ) from exc
        return AccessibleDocumentList(
            items=[_document_from_mapping(row._mapping) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def list_document_chunks(
        self,
        session: Session,
        *,
        user_id: str,
        enterprise_id: str,
        document_id: str,
        request_id: str | None = None,
    ) -> tuple[AccessibleChunk, ...]:
        context = self._permission_context(
            session,
            user_id=user_id,
            enterprise_id=enterprise_id,
            request_id=request_id,
            required_scope="document:read",
        )
        document_kb_id = self._load_document_kb_id(
            session,
            enterprise_id=context.enterprise_id,
            document_id=document_id,
        )
        active_index_ids = self._load_active_index_versions(
            session,
            enterprise_id=context.enterprise_id,
            kb_ids=(document_kb_id,),
        )
        if not active_index_ids:
            return ()
        permission_filter = self.permission_service.build_filter(
            context,
            kb_ids=(document_kb_id,),
            active_index_version_ids=active_index_ids,
            required_scope="document:read",
        )
        params = dict(permission_filter.params)
        params["document_id"] = document_id
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT DISTINCT
                        c.id::text AS chunk_id,
                        c.document_id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        c.text_preview,
                        c.page_start,
                        c.page_end,
                        c.status,
                        c.ordinal
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    JOIN chunk_index_refs cir ON cir.chunk_id = c.id
                    WHERE {permission_filter.metadata_where_sql}
                      AND d.id = CAST(:document_id AS uuid)
                    ORDER BY c.ordinal, chunk_id
                    """
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_CHUNKS_UNAVAILABLE",
                "document chunks cannot be read",
                exc,
            ) from exc
        return tuple(_chunk_from_mapping(row._mapping) for row in rows)

    def _permission_context(
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

    def _load_active_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT id::text AS index_version_id
                    FROM index_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = ANY(CAST(:kb_ids AS uuid[]))
                      AND status = 'active'
                    ORDER BY activated_at DESC NULLS LAST, id
                    """
                ),
                {"enterprise_id": enterprise_id, "kb_ids": list(kb_ids)},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_INDEX_UNAVAILABLE",
                "active index versions cannot be read",
                exc,
            ) from exc
        return tuple(str(row._mapping["index_version_id"]) for row in rows)

    def _load_document_kb_id(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_id: str,
    ) -> str:
        try:
            row = session.execute(
                text(
                    """
                    SELECT kb_id::text AS kb_id
                    FROM documents
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND id = CAST(:document_id AS uuid)
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id, "document_id": document_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_DOCUMENT_UNAVAILABLE",
                "document cannot be read",
                exc,
            ) from exc
        if row is None:
            raise KnowledgeServiceError(
                "KNOWLEDGE_DOCUMENT_NOT_FOUND",
                "document is not found",
                status_code=404,
                details={"document_id": document_id},
            )
        return str(row._mapping["kb_id"])


def _knowledge_base_visibility_sql(
    context: PermissionContext,
    params: dict[str, Any],
) -> str:
    if context.has_scope("knowledge_base:manage"):
        return ""
    conditions = ["default_visibility = 'enterprise'"]
    if context.department_ids:
        conditions.append("owner_department_id = ANY(CAST(:department_ids AS uuid[]))")
        params["department_ids"] = list(context.department_ids)
    scoped_kb_ids = tuple(
        role.scope_id
        for role in context.roles
        if role.scope_type == "knowledge_base" and role.scope_id
    )
    if scoped_kb_ids:
        conditions.append("id = ANY(CAST(:scoped_kb_ids AS uuid[]))")
        params["scoped_kb_ids"] = list(scoped_kb_ids)
    return f"({' OR '.join(conditions)})"


def _knowledge_base_from_mapping(row: Any) -> AccessibleKnowledgeBase:
    return AccessibleKnowledgeBase(
        id=str(row["kb_id"]),
        name=str(row["name"]),
        status=str(row["status"]),
        owner_department_id=str(row["owner_department_id"]),
        default_visibility=str(row["default_visibility"]),
        config_scope_id=_optional_str(row.get("config_scope_id")),
        policy_version=int(row["policy_version"]),
    )


def _document_from_mapping(row: Any) -> AccessibleDocument:
    return AccessibleDocument(
        id=str(row["document_id"]),
        kb_id=str(row["kb_id"]),
        folder_id=_optional_str(row.get("folder_id")),
        title=str(row["title"]),
        lifecycle_status=str(row["lifecycle_status"]),
        index_status=str(row["index_status"]),
        owner_department_id=str(row["owner_department_id"]),
        visibility=str(row["visibility"]),
        current_version_id=_optional_str(row.get("current_version_id")),
    )


def _chunk_from_mapping(row: Any) -> AccessibleChunk:
    return AccessibleChunk(
        id=str(row["chunk_id"]),
        document_id=str(row["document_id"]),
        document_version_id=str(row["document_version_id"]),
        text_preview=str(row["text_preview"]),
        page_start=_optional_int(row.get("page_start")),
        page_end=_optional_int(row.get("page_end")),
        status=str(row["status"]),
    )


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _database_error(
    error_code: str,
    message: str,
    exc: SQLAlchemyError,
) -> KnowledgeServiceError:
    return KnowledgeServiceError(
        error_code,
        message,
        status_code=503,
        retryable=True,
        details={"error_type": exc.__class__.__name__},
    )
