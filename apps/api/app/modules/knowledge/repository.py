"""SQL repository for user-facing knowledge browsing."""

from __future__ import annotations

from typing import Any

from app.modules.knowledge.errors import KnowledgeServiceError
from app.modules.knowledge.mappers import (
    _chunk_from_mapping,
    _database_error,
    _document_from_mapping,
    _document_list_item_from_mapping,
    _document_version_from_mapping,
    _folder_from_mapping,
    _knowledge_base_from_mapping,
    _knowledge_base_visibility_sql,
)
from app.modules.knowledge.schemas import (
    AccessibleChunk,
    AccessibleDocument,
    AccessibleDocumentListItem,
    AccessibleDocumentVersion,
    AccessibleFolder,
    AccessibleKnowledgeBase,
)
from app.modules.permissions.schemas import PermissionContext, PermissionFilter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class KnowledgeRepository:
    """Centralized read queries for knowledge browsing."""

    def list_knowledge_bases(
        self,
        session: Session,
        *,
        context: PermissionContext,
        page: int,
        page_size: int,
        keyword: str | None,
        status: str | None,
    ) -> tuple[list[AccessibleKnowledgeBase], int]:
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
                        status
                    FROM knowledge_bases kb
                    WHERE {where_sql}
                    ORDER BY updated_at DESC, name
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM knowledge_bases kb WHERE {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_BASES_UNAVAILABLE",
                "knowledge bases cannot be read",
                exc,
            ) from exc
        return [_knowledge_base_from_mapping(row._mapping) for row in rows], int(
            total_row._mapping["total"]
        )

    def get_knowledge_base(
        self,
        session: Session,
        *,
        context: PermissionContext,
        kb_id: str,
    ) -> AccessibleKnowledgeBase | None:
        params: dict[str, Any] = {"enterprise_id": context.enterprise_id, "kb_id": kb_id}
        access_sql = _knowledge_base_visibility_sql(context, params)
        conditions = [
            "kb.enterprise_id = CAST(:enterprise_id AS uuid)",
            "kb.id = CAST(:kb_id AS uuid)",
            "kb.deleted_at IS NULL",
            "kb.status = 'active'",
        ]
        if access_sql:
            conditions.append(access_sql)
        where_sql = " AND ".join(conditions)
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        kb.id::text AS kb_id,
                        kb.name,
                        kb.status
                    FROM knowledge_bases kb
                    WHERE {where_sql}
                    LIMIT 1
                    """
                ),
                params,
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_BASE_UNAVAILABLE",
                "knowledge base cannot be read",
                exc,
            ) from exc
        return _knowledge_base_from_mapping(row._mapping) if row is not None else None

    def list_folders(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[AccessibleFolder], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        params = {
            "enterprise_id": enterprise_id,
            "kb_id": kb_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS folder_id,
                        kb_id::text AS kb_id,
                        parent_id::text AS parent_id,
                        name,
                        status
                    FROM folders
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = CAST(:kb_id AS uuid)
                      AND deleted_at IS NULL
                      AND status = 'active'
                    ORDER BY path, name, id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM folders
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND kb_id = CAST(:kb_id AS uuid)
                      AND deleted_at IS NULL
                      AND status = 'active'
                    """
                ),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_FOLDERS_UNAVAILABLE",
                "folders cannot be read",
                exc,
            ) from exc
        return [_folder_from_mapping(row._mapping) for row in rows], int(
            total_row._mapping["total"]
        )

    def list_documents(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        page: int,
        page_size: int,
        keyword: str | None,
        status: str | None,
    ) -> tuple[list[AccessibleDocumentListItem], int]:
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
                        d.title,
                        d.lifecycle_status,
                        d.index_status,
                        d.updated_at
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    JOIN chunk_index_refs cir ON cir.chunk_id = c.id
                    WHERE {permission_filter.metadata_where_sql}
                      {filter_sql}
                    ORDER BY d.updated_at DESC, d.title, document_id
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
        return [_document_list_item_from_mapping(row._mapping) for row in rows], int(
            total_row._mapping["total"]
        )

    def get_document(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        document_id: str,
    ) -> AccessibleDocument | None:
        params = dict(permission_filter.params)
        params["document_id"] = document_id
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT DISTINCT
                        d.id::text AS document_id,
                        d.title,
                        d.lifecycle_status,
                        d.index_status,
                        d.updated_at
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    JOIN chunk_index_refs cir ON cir.chunk_id = c.id
                    WHERE {permission_filter.metadata_where_sql}
                      AND d.id = CAST(:document_id AS uuid)
                    LIMIT 1
                    """
                ),
                params,
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_DOCUMENT_UNAVAILABLE",
                "document cannot be read",
                exc,
            ) from exc
        return _document_from_mapping(row._mapping) if row is not None else None

    def list_document_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[AccessibleDocumentVersion], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS version_id,
                        document_id::text AS document_id,
                        version_no,
                        status
                    FROM document_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:document_id AS uuid)
                    ORDER BY version_no DESC, created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "enterprise_id": enterprise_id,
                    "document_id": document_id,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            ).all()
            total_row = session.execute(
                text(
                    """
                    SELECT count(*) AS total
                    FROM document_versions
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND document_id = CAST(:document_id AS uuid)
                    """
                ),
                {"enterprise_id": enterprise_id, "document_id": document_id},
            ).one()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_DOCUMENT_VERSIONS_UNAVAILABLE",
                "document versions cannot be read",
                exc,
            ) from exc
        return [_document_version_from_mapping(row._mapping) for row in rows], int(
            total_row._mapping["total"]
        )

    def list_document_chunks(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        document_id: str,
        page: int,
        page_size: int,
        keyword: str | None,
        status: str | None,
    ) -> tuple[list[AccessibleChunk], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        params = dict(permission_filter.params)
        params.update(
            {
                "document_id": document_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            }
        )
        filters: list[str] = ["d.id = CAST(:document_id AS uuid)"]
        if keyword:
            filters.append("c.text_preview ILIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"
        if status and status != "active":
            filters.append("FALSE")
        filter_sql = "".join(f"\n                      AND {condition}" for condition in filters)
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
                      {filter_sql}
                    ORDER BY c.ordinal, chunk_id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(
                    f"""
                    SELECT count(DISTINCT c.id) AS total
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
                "KNOWLEDGE_CHUNKS_UNAVAILABLE",
                "document chunks cannot be read",
                exc,
            ) from exc
        return [_chunk_from_mapping(row._mapping) for row in rows], int(
            total_row._mapping["total"]
        )

    def get_document_source_row(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        document_id: str,
        source_id: str,
    ) -> Any | None:
        params = dict(permission_filter.params)
        params.update({"document_id": document_id, "source_id": source_id})
        try:
            return session.execute(
                text(
                    f"""
                    SELECT DISTINCT
                        c.id::text AS chunk_id,
                        c.document_id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        c.text_object_key,
                        c.text_preview,
                        c.heading_path,
                        c.source_offsets,
                        c.page_start,
                        c.page_end,
                        c.status,
                        c.ordinal,
                        d.title
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    JOIN chunk_index_refs cir ON cir.chunk_id = c.id
                    WHERE {permission_filter.metadata_where_sql}
                      AND d.id = CAST(:document_id AS uuid)
                      AND c.id = CAST(:source_id AS uuid)
                    LIMIT 1
                    """
                ),
                params,
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "KNOWLEDGE_SOURCE_UNAVAILABLE",
                "source cannot be read",
                exc,
            ) from exc

    def load_active_index_versions(
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

    def load_document_kb_id(
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
