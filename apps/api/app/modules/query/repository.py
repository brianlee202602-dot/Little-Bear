"""Read repository for query retrieval workflows."""

from __future__ import annotations

from dataclasses import replace

from app.modules.permissions.schemas import PermissionFilter
from app.modules.query.schemas import (
    ActiveIndexVersion,
    QueryFilterClause,
    _CurrentCandidateFacts,
)
from app.modules.query.utils import (
    _candidate_from_mapping,
    _database_error,
    _optional_int,
)
from app.modules.retrieval import RetrievalCandidate
from app.shared.json_utils import json_int
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class QueryRepository:
    """Centralized SQL reads used by query retrieval."""

    def load_active_config_version(self, session: Session) -> int:
        try:
            row = session.execute(
                text(
                    """
                    SELECT value_json
                    FROM system_state
                    WHERE key = 'active_config_version'
                    LIMIT 1
                    """
                )
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_CONFIG_UNAVAILABLE",
                "active config version cannot be loaded",
                exc,
            ) from exc
        version = json_int(row._mapping["value_json"], "version") if row else None
        if version is None:
            from app.modules.query.errors import QueryServiceError

            raise QueryServiceError(
                "QUERY_CONFIG_UNAVAILABLE",
                "active config version is missing",
                status_code=503,
                retryable=True,
            )
        return version

    def load_active_index_versions(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_ids: tuple[str, ...],
    ) -> tuple[ActiveIndexVersion, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS index_version_id,
                        collection_name
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
                "QUERY_INDEX_UNAVAILABLE",
                "active index versions cannot be loaded",
                exc,
            ) from exc
        return tuple(
            ActiveIndexVersion(
                id=str(row._mapping["index_version_id"]),
                collection_name=str(row._mapping["collection_name"]),
            )
            for row in rows
        )

    def keyword_search(
        self,
        session: Session,
        *,
        permission_filter: PermissionFilter,
        query_text: str,
        filter_clause: QueryFilterClause,
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        params = dict(permission_filter.params)
        params.update(filter_clause.params)
        params.update(
            {
                "query_text": query_text,
                "like_query": f"%{query_text}%",
                "limit": limit,
            }
        )
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        kie.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        c.id::text AS chunk_id,
                        d.title,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.lifecycle_status AS document_lifecycle_status,
                        d.index_status AS document_index_status,
                        c.status AS chunk_status,
                        kie.visibility_state,
                        iv.id::text AS index_version_id,
                        LEAST(
                            kie.indexed_permission_version,
                            cir.indexed_permission_version
                        ) AS indexed_permission_version,
                        c.page_start,
                        c.page_end,
                        GREATEST(
                            ts_rank_cd(kie.search_tsv, plainto_tsquery('simple', :query_text)),
                            CASE WHEN kie.search_text ILIKE :like_query THEN 0.05 ELSE 0 END
                        )::float AS score
                    FROM keyword_index_entries kie
                    JOIN chunks c ON c.id = kie.chunk_id
                    JOIN documents d ON d.id = kie.document_id
                    JOIN index_versions iv ON iv.id = kie.index_version_id
                    JOIN chunk_index_refs cir
                      ON cir.keyword_id = kie.id
                     AND cir.chunk_id = c.id
                     AND cir.index_version_id = iv.id
                    WHERE {permission_filter.keyword_where_sql}
                      AND iv.status = 'active'
                      AND (
                          kie.search_tsv @@ plainto_tsquery('simple', :query_text)
                          OR kie.search_text ILIKE :like_query
                      )
                      {filter_clause.sql}
                    ORDER BY score DESC, c.ordinal ASC
                    LIMIT :limit
                    """
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_KEYWORD_SEARCH_FAILED",
                "keyword search failed",
                exc,
            ) from exc
        return tuple(
            _candidate_from_mapping(dict(row._mapping), source="keyword", rank=rank)
            for rank, row in enumerate(rows, start=1)
        )

    def load_current_candidate_facts(
        self,
        session: Session,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> dict[tuple[str, str], _CurrentCandidateFacts]:
        if not candidates:
            return {}
        chunk_ids = [candidate.chunk_id for candidate in candidates]
        index_version_ids = [candidate.index_version_id for candidate in candidates]
        try:
            rows = session.execute(
                text(
                    """
                    WITH requested AS (
                        SELECT *
                        FROM unnest(
                            CAST(:chunk_ids AS uuid[]),
                            CAST(:index_version_ids AS uuid[])
                        ) AS item(chunk_id, index_version_id)
                    )
                    SELECT
                        c.id::text AS chunk_id,
                        d.enterprise_id::text AS enterprise_id,
                        d.kb_id::text AS kb_id,
                        d.id::text AS document_id,
                        c.document_version_id::text AS document_version_id,
                        d.title,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.lifecycle_status AS document_lifecycle_status,
                        d.index_status AS document_index_status,
                        c.status AS chunk_status,
                        cir.visibility_state,
                        iv.id::text AS index_version_id,
                        cir.indexed_permission_version,
                        c.page_start,
                        c.page_end,
                        EXISTS (
                            SELECT 1
                            FROM access_blocks ab
                            WHERE ab.enterprise_id = d.enterprise_id
                              AND (
                                  (ab.resource_type = 'knowledge_base'
                                      AND ab.resource_id = d.kb_id)
                                  OR (ab.resource_type = 'folder'
                                      AND ab.resource_id = d.folder_id)
                                  OR (ab.resource_type = 'document'
                                      AND ab.resource_id = d.id)
                                  OR (ab.resource_type = 'chunk'
                                      AND ab.resource_id = c.id)
                              )
                              AND ab.status = 'active'
                              AND (ab.expires_at IS NULL OR ab.expires_at > now())
                        ) AS access_blocked
                    FROM requested r
                    JOIN chunks c
                      ON c.id = r.chunk_id
                     AND c.deleted_at IS NULL
                    JOIN documents d
                      ON d.id = c.document_id
                     AND d.deleted_at IS NULL
                    JOIN index_versions iv
                      ON iv.id = r.index_version_id
                     AND iv.document_id = d.id
                     AND iv.document_version_id = c.document_version_id
                     AND iv.status = 'active'
                    JOIN chunk_index_refs cir
                      ON cir.chunk_id = c.id
                     AND cir.index_version_id = iv.id
                    """
                ),
                {"chunk_ids": chunk_ids, "index_version_ids": index_version_ids},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_CANDIDATE_METADATA_UNAVAILABLE",
                "query candidate metadata cannot be loaded",
                exc,
            ) from exc
        by_candidate = {
            (candidate.chunk_id, candidate.index_version_id): candidate
            for candidate in candidates
        }
        facts: dict[tuple[str, str], _CurrentCandidateFacts] = {}
        for row in rows:
            mapping = row._mapping
            key = (str(mapping["chunk_id"]), str(mapping["index_version_id"]))
            original = by_candidate.get(key)
            if original is None:
                continue
            facts[key] = _CurrentCandidateFacts(
                candidate=replace(
                    original,
                    enterprise_id=str(mapping["enterprise_id"]),
                    kb_id=str(mapping["kb_id"]),
                    document_id=str(mapping["document_id"]),
                    document_version_id=str(mapping["document_version_id"]),
                    title=str(mapping["title"]),
                    owner_department_id=str(mapping["owner_department_id"]),
                    visibility=str(mapping["visibility"]),
                    document_lifecycle_status=str(mapping["document_lifecycle_status"]),
                    document_index_status=str(mapping["document_index_status"]),
                    chunk_status=str(mapping["chunk_status"]),
                    visibility_state=str(mapping["visibility_state"]),
                    index_version_id=str(mapping["index_version_id"]),
                    indexed_permission_version=int(mapping["indexed_permission_version"]),
                    page_start=_optional_int(mapping["page_start"]),
                    page_end=_optional_int(mapping["page_end"]),
                ),
                access_blocked=bool(mapping["access_blocked"]),
            )
        return facts

    def load_rerank_texts(
        self,
        session: Session,
        *,
        chunk_ids: tuple[str, ...],
    ) -> dict[str, str]:
        if not chunk_ids:
            return {}
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        id::text AS chunk_id,
                        text_preview
                    FROM chunks
                    WHERE id = ANY(CAST(:chunk_ids AS uuid[]))
                      AND deleted_at IS NULL
                    """
                ),
                {"chunk_ids": list(chunk_ids)},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "QUERY_RERANK_INPUT_UNAVAILABLE",
                "rerank input chunks cannot be loaded",
                exc,
            ) from exc
        return {
            str(row._mapping["chunk_id"]): str(row._mapping["text_preview"] or "")
            for row in rows
        }
