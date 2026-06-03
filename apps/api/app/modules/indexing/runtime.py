"""Indexing Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.adapters import (
    QdrantVectorIndexWriter,
    VectorStoreDraftPoint,
    VectorStoreEmbeddingError,
    VectorStorePayloadUpdate,
)
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.schemas import DraftVectorPoint, VectorPayloadUpdate
from app.modules.indexing.service import (
    DEFAULT_COLLECTION,
    DEFAULT_MODEL_VERSION,
    IndexingService,
)
from app.modules.models import ModelClientError, ModelGatewayEmbeddingClient
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.json_utils import as_dict, json_bool, json_int, json_str
from sqlalchemy.orm import Session


class _VectorStoreEmbeddingClientAdapter:
    def __init__(self, client: ModelGatewayEmbeddingClient) -> None:
        self.client = client

    def embed_query(self, query_text: str) -> list[float]:
        try:
            return self.client.embed_query(query_text)
        except ModelClientError as exc:
            raise VectorStoreEmbeddingError(exc.error_code, exc.message) from exc

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            return self.client.embed_texts(texts)
        except ModelClientError as exc:
            raise VectorStoreEmbeddingError(exc.error_code, exc.message) from exc


class _QdrantVectorIndexWriterAdapter:
    def __init__(self, writer: QdrantVectorIndexWriter) -> None:
        self.writer = writer

    @property
    def embedding_client(self) -> ModelGatewayEmbeddingClient:
        return self.writer.embedding_client.client

    @property
    def timeout_seconds(self) -> float:
        return self.writer.timeout_seconds

    def upsert_draft_points(self, points: tuple[DraftVectorPoint, ...]) -> None:
        self.writer.upsert_draft_points(
            tuple(
                VectorStoreDraftPoint(
                    collection_name=point.collection_name,
                    vector_id=point.vector_id,
                    text=point.text,
                    payload=point.payload,
                )
                for point in points
            )
        )

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        self.writer.activate_points(
            collection_name=collection_name,
            vector_ids=vector_ids,
            permission_version=permission_version,
        )

    def update_payloads(self, updates: tuple[VectorPayloadUpdate, ...]) -> None:
        self.writer.update_payloads(
            tuple(
                VectorStorePayloadUpdate(
                    collection_name=update.collection_name,
                    vector_id=update.vector_id,
                    payload=update.payload,
                )
                for update in updates
            )
        )

    def delete_points(self, *, collection_name: str, vector_ids: tuple[str, ...]) -> None:
        self.writer.delete_points(collection_name=collection_name, vector_ids=vector_ids)


def build_indexing_service(session: Session) -> IndexingService:
    """按 active_config 组装带真实 VectorStore writer 的 IndexingService。"""

    try:
        snapshot = ConfigService().load_active_config(session, validate_schema=False)
    except ConfigServiceError as exc:
        raise IndexingServiceError(
            "INDEX_RUNTIME_CONFIG_UNAVAILABLE",
            "active config cannot be loaded for indexing runtime",
            status_code=503,
            retryable=True,
            details={"source_error_code": exc.error_code, "source_details": exc.details},
        ) from exc
    return _build_indexing_service(session, snapshot.config)


def _build_indexing_service(session: Session, config: dict[str, Any]) -> IndexingService:
    vector_store = as_dict(config.get("vector_store"))
    model_gateway = as_dict(config.get("model_gateway"))
    model_config = as_dict(config.get("model"))
    timeout_config = as_dict(config.get("timeout"))

    providers = as_dict(model_gateway.get("providers"))
    embedding_provider = as_dict(providers.get("embedding"))

    qdrant_base_url = json_str(vector_store, "qdrant_base_url")
    embedding_base_url = json_str(embedding_provider, "base_url")
    embedding_model = json_str(model_config, "embedding_model")
    dimension = json_int(model_config, "embedding_dimension")

    missing = []
    if not qdrant_base_url:
        missing.append("vector_store.qdrant_base_url")
    if not embedding_base_url:
        missing.append("model_gateway.providers.embedding.base_url")
    if not embedding_model:
        missing.append("model.embedding_model")
    if dimension is None or dimension <= 0:
        missing.append("model.embedding_dimension")
    if missing:
        raise IndexingServiceError(
            "INDEX_RUNTIME_CONFIG_INCOMPLETE",
            "active config is incomplete for indexing runtime",
            status_code=503,
            retryable=True,
            details={"missing": missing},
        )

    gateway_auth_ref = json_str(model_gateway, "auth_token_ref")
    provider_auth_ref = json_str(embedding_provider, "auth_token_ref") or gateway_auth_ref
    embedding_client = ModelGatewayEmbeddingClient(
        base_url=embedding_base_url,
        path=_embedding_path(embedding_provider),
        provider_type=json_str(embedding_provider, "type", default="http") or "http",
        model=embedding_model,
        auth_token=_secret_value(session, provider_auth_ref),
        timeout_seconds=_timeout_seconds(
            json_int(timeout_config, "embedding_ms"),
            default_ms=3000,
            min_ms=3000,
        ),
        expected_dimension=dimension,
        normalize=json_bool(model_config, "embedding_normalize", default=False),
    )
    vector_writer = _QdrantVectorIndexWriterAdapter(
        QdrantVectorIndexWriter(
            base_url=qdrant_base_url,
            api_key=_secret_value(session, json_str(vector_store, "api_key_ref")),
            embedding_client=_VectorStoreEmbeddingClientAdapter(embedding_client),
            timeout_seconds=_timeout_seconds(
                json_int(timeout_config, "vector_search_ms"),
                default_ms=3000,
                min_ms=3000,
            ),
            embedding_batch_size=_embedding_batch_size(config),
        )
    )
    return IndexingService(
        embedding_model=embedding_model,
        model_version=json_str(model_config, "embedding_version", default=DEFAULT_MODEL_VERSION)
        or DEFAULT_MODEL_VERSION,
        dimension=dimension,
        collection_name=json_str(
            vector_store,
            "collection_prefix",
            default=DEFAULT_COLLECTION,
        )
        or DEFAULT_COLLECTION,
        vector_index_writer=vector_writer,
    )


def _embedding_path(provider: dict[str, Any]) -> str:
    configured = json_str(provider, "embeddings_path")
    if configured:
        return configured
    provider_type = json_str(provider, "type", default="http")
    return "/embed" if provider_type == "tei" else "/v1/embeddings"


def _embedding_batch_size(config: dict[str, Any]) -> int:
    import_config = as_dict(config.get("import"))
    return max(json_int(import_config, "embedding_batch_size") or 16, 1)


def _secret_value(session: Session, secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    try:
        return SecretStoreService().get_secret_value(session, secret_ref=secret_ref)
    except SecretStoreError as exc:
        raise IndexingServiceError(
            "INDEX_SECRET_UNAVAILABLE",
            "secret required by indexing runtime cannot be read",
            status_code=503,
            retryable=True,
            details={"secret_ref": secret_ref},
        ) from exc


def _timeout_seconds(timeout_ms: int | None, *, default_ms: int, min_ms: int = 1) -> float:
    return max(timeout_ms or default_ms, min_ms) / 1000
