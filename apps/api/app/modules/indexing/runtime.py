"""Indexing Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.adapters import QdrantVectorIndexWriter
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.indexing.errors import IndexingServiceError
from app.modules.indexing.service import (
    DEFAULT_COLLECTION,
    DEFAULT_MODEL_VERSION,
    IndexingService,
)
from app.modules.models import ModelGatewayEmbeddingClient
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.json_utils import as_dict, json_bool, json_int, json_str
from sqlalchemy.orm import Session


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
        timeout_seconds=_timeout_seconds(json_int(timeout_config, "embedding_ms"), default_ms=3000),
        expected_dimension=dimension,
        normalize=json_bool(model_config, "embedding_normalize", default=False),
    )
    vector_writer = QdrantVectorIndexWriter(
        base_url=qdrant_base_url,
        api_key=_secret_value(session, json_str(vector_store, "api_key_ref")),
        embedding_client=embedding_client,
        timeout_seconds=_timeout_seconds(
            json_int(timeout_config, "vector_search_ms"),
            default_ms=3000,
        ),
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


def _timeout_seconds(timeout_ms: int | None, *, default_ms: int) -> float:
    return max(timeout_ms or default_ms, 1) / 1000
