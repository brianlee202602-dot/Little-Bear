"""Query Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.adapters import QdrantVectorRetriever
from app.modules.config.service import ConfigService
from app.modules.models import ModelGatewayEmbeddingClient
from app.modules.query.service import QueryService
from app.modules.retrieval import UnavailableVectorRetriever
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.json_utils import as_dict, json_bool, json_int, json_str
from sqlalchemy.orm import Session


def build_query_service(session: Session) -> QueryService:
    """按 active_config 组装 QueryService。

    配置、Secret 或 adapter 初始化失败时只降级向量召回，不阻断关键词检索闭环。
    """

    try:
        snapshot = ConfigService().load_active_config(session, validate_schema=False)
        vector_retriever = _build_vector_retriever(session, snapshot.config)
    except Exception:
        vector_retriever = UnavailableVectorRetriever(reason="vector_runtime_config_unavailable")
    return QueryService(vector_retriever=vector_retriever)


def _build_vector_retriever(session: Session, config: dict[str, Any]):
    vector_store = as_dict(config.get("vector_store"))
    model_gateway = as_dict(config.get("model_gateway"))
    model_config = as_dict(config.get("model"))
    timeout_config = as_dict(config.get("timeout"))

    qdrant_base_url = json_str(vector_store, "qdrant_base_url")
    providers = as_dict(model_gateway.get("providers"))
    embedding_provider = as_dict(providers.get("embedding"))
    embedding_base_url = json_str(embedding_provider, "base_url")
    embedding_model = json_str(model_config, "embedding_model")
    if not qdrant_base_url or not embedding_base_url or not embedding_model:
        return UnavailableVectorRetriever(reason="vector_runtime_config_incomplete")

    gateway_auth_ref = json_str(model_gateway, "auth_token_ref")
    provider_auth_ref = json_str(embedding_provider, "auth_token_ref") or gateway_auth_ref
    embedding_client = ModelGatewayEmbeddingClient(
        base_url=embedding_base_url,
        path=_embedding_path(embedding_provider),
        provider_type=json_str(embedding_provider, "type", default="http") or "http",
        model=embedding_model,
        auth_token=_secret_value(session, provider_auth_ref),
        timeout_seconds=_timeout_seconds(json_int(timeout_config, "embedding_ms"), default_ms=3000),
        expected_dimension=json_int(model_config, "embedding_dimension"),
        normalize=json_bool(model_config, "embedding_normalize", default=False),
    )
    return QdrantVectorRetriever(
        base_url=qdrant_base_url,
        api_key=_secret_value(session, json_str(vector_store, "api_key_ref")),
        embedding_client=embedding_client,
        timeout_seconds=_timeout_seconds(
            json_int(timeout_config, "vector_search_ms"),
            default_ms=3000,
        ),
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
    except SecretStoreError:
        return None


def _timeout_seconds(timeout_ms: int | None, *, default_ms: int) -> float:
    return max(timeout_ms or default_ms, 1) / 1000
