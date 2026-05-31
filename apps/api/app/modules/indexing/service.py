"""Indexing Service facade."""

from __future__ import annotations

from typing import Any

from app.modules.audit import AuditWriter
from app.modules.indexing.cleanup_service import IndexCleanupService
from app.modules.indexing.draft_service import DraftIndexService
from app.modules.indexing.permission_payload_service import PermissionPayloadRefreshService
from app.modules.indexing.publish_service import IndexPublishService
from app.modules.indexing.writers import NoopVectorIndexWriter, VectorIndexWriter
from sqlalchemy.orm import Session

DEFAULT_EMBEDDING_MODEL = "p0-placeholder-embedding"
DEFAULT_MODEL_VERSION = "p0"
DEFAULT_DIMENSION = 0
DEFAULT_COLLECTION = "little_bear_p0"


class IndexingService:
    """Facade for indexing draft, publish, cleanup and permission refresh workflows."""

    def __init__(
        self,
        *,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        model_version: str = DEFAULT_MODEL_VERSION,
        dimension: int = DEFAULT_DIMENSION,
        collection_name: str = DEFAULT_COLLECTION,
        vector_index_writer: VectorIndexWriter | None = None,
    ) -> None:
        self.embedding_model = embedding_model
        self.model_version = model_version
        self.dimension = dimension
        self.collection_name = collection_name
        self.vector_index_writer = vector_index_writer or NoopVectorIndexWriter()
        self.draft_service = DraftIndexService(self)
        self.publish_service = IndexPublishService(self)
        self.cleanup_service = IndexCleanupService(self)
        self.permission_payload_service = PermissionPayloadRefreshService(self)

    def create_draft_indexes(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
        embedding_model: str | None = None,
        model_version: str | None = None,
        dimension: int | None = None,
        collection_name: str | None = None,
    ) -> list[str]:
        return self.draft_service.create_draft_indexes(
            session,
            request_json=request_json,
            embedding_model=embedding_model,
            model_version=model_version,
            dimension=dimension,
            collection_name=collection_name,
        )

    def write_draft_indexes(self, session: Session, *, request_json: dict[str, Any]) -> list[str]:
        return self.draft_service.write_draft_indexes(session, request_json=request_json)

    def publish_ready_indexes(self, session: Session, *, request_json: dict[str, Any]) -> list[str]:
        return self.publish_service.publish_ready_indexes(session, request_json=request_json)

    def cleanup_pending_delete_indexes(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> dict[str, int]:
        return self.cleanup_service.cleanup_pending_delete_indexes(
            session,
            request_json=request_json,
        )

    def refresh_permission_payloads(
        self,
        session: Session,
        *,
        request_json: dict[str, Any],
    ) -> dict[str, int]:
        return self.permission_payload_service.refresh_permission_payloads(
            session,
            request_json=request_json,
        )

    def _insert_audit_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        event_name: str,
        resource_id: str,
        summary: dict[str, Any],
    ) -> None:
        AuditWriter().write(
            session,
            enterprise_id=enterprise_id,
            event_name=event_name,
            actor_type="system",
            actor_id="indexing",
            resource_type="document",
            resource_id=resource_id,
            action="index",
            result="success",
            risk_level="low",
            summary=summary,
        )


__all__ = [
    "DEFAULT_COLLECTION",
    "DEFAULT_DIMENSION",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_MODEL_VERSION",
    "IndexingService",
    "NoopVectorIndexWriter",
    "VectorIndexWriter",
]
