"""Query Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.adapters import QdrantVectorRetriever
from app.modules.answer import AnswerService
from app.modules.config.service import ConfigService
from app.modules.context.service import (
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_MAX_CONTEXT_CHUNKS,
    ContextBuilder,
)
from app.modules.models import (
    ModelGatewayChatClient,
    ModelGatewayEmbeddingClient,
    ModelGatewayRerankClient,
)
from app.modules.query.service import QueryService
from app.modules.retrieval import (
    ModelCandidateReranker,
    NoopCandidateReranker,
    UnavailableVectorRetriever,
)
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.json_utils import as_dict, json_bool, json_int, json_str
from sqlalchemy.orm import Session


def build_query_service(session: Session) -> QueryService:
    """按 active_config 组装 QueryService。

    配置、Secret 或 adapter 初始化失败时降级可选模型能力，不阻断关键词检索闭环。
    """

    try:
        snapshot = ConfigService().load_active_config(session, validate_schema=False)
        config = snapshot.config
    except Exception:
        return QueryService(
            vector_retriever=UnavailableVectorRetriever(
                reason="vector_runtime_config_unavailable"
            ),
            answer_service=AnswerService(),
        )
    try:
        vector_retriever = _build_vector_retriever(session, config)
    except Exception:
        vector_retriever = UnavailableVectorRetriever(reason="vector_runtime_config_unavailable")
    try:
        answer_service = _build_answer_service(session, config)
    except Exception:
        answer_service = AnswerService()
    try:
        candidate_reranker = _build_candidate_reranker(session, config)
    except Exception:
        candidate_reranker = NoopCandidateReranker()
    return QueryService(
        vector_retriever=vector_retriever,
        candidate_reranker=candidate_reranker,
        rerank_input_top_k=_rerank_input_top_k(config),
        context_builder=_build_context_builder(config),
        answer_service=answer_service,
    )


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


def _build_answer_service(session: Session, config: dict[str, Any]) -> AnswerService:
    model_gateway = as_dict(config.get("model_gateway"))
    model_config = as_dict(config.get("model"))
    llm_config = as_dict(config.get("llm"))
    providers = as_dict(model_gateway.get("providers"))
    llm_provider = as_dict(providers.get("llm"))

    llm_base_url = json_str(llm_provider, "base_url")
    llm_model = json_str(model_config, "llm_model")
    if not llm_base_url or not llm_model:
        return AnswerService()

    gateway_auth_ref = json_str(model_gateway, "auth_token_ref")
    provider_auth_ref = json_str(llm_provider, "auth_token_ref") or gateway_auth_ref
    chat_client = ModelGatewayChatClient(
        base_url=llm_base_url,
        path=_chat_completions_path(llm_provider),
        model=llm_model,
        auth_token=_secret_value(session, provider_auth_ref),
        timeout_seconds=_timeout_seconds(
            json_int(llm_config, "total_timeout_ms"),
            default_ms=20000,
        ),
        extra_body=as_dict(llm_config.get("openai_extra_body")) or None,
    )
    return AnswerService(
        chat_client=chat_client,
        temperature=_json_float(llm_config, "temperature", default=0.1),
        max_tokens=json_int(llm_config, "max_tokens") or 800,
    )


def _build_candidate_reranker(session: Session, config: dict[str, Any]):
    model_gateway = as_dict(config.get("model_gateway"))
    model_config = as_dict(config.get("model"))
    timeout_config = as_dict(config.get("timeout"))
    providers = as_dict(model_gateway.get("providers"))
    rerank_provider = as_dict(providers.get("rerank"))

    rerank_base_url = json_str(rerank_provider, "base_url")
    rerank_model = json_str(model_config, "rerank_model")
    if not rerank_base_url or not rerank_model:
        return NoopCandidateReranker()

    gateway_auth_ref = json_str(model_gateway, "auth_token_ref")
    provider_auth_ref = json_str(rerank_provider, "auth_token_ref") or gateway_auth_ref
    rerank_client = ModelGatewayRerankClient(
        base_url=rerank_base_url,
        path=_rerank_path(rerank_provider),
        provider_type=json_str(rerank_provider, "type", default="http") or "http",
        model=rerank_model,
        auth_token=_secret_value(session, provider_auth_ref),
        timeout_seconds=_timeout_seconds(
            json_int(timeout_config, "rerank_ms"),
            default_ms=800,
        ),
    )
    return ModelCandidateReranker(rerank_client=rerank_client)


def _chat_completions_path(provider: dict[str, Any]) -> str:
    return json_str(provider, "chat_completions_path") or "/v1/chat/completions"


def _rerank_path(provider: dict[str, Any]) -> str:
    return json_str(provider, "rerank_path") or "/rerank"


def _rerank_input_top_k(config: dict[str, Any]) -> int:
    retrieval_config = as_dict(config.get("retrieval"))
    return json_int(retrieval_config, "rerank_input_top_k") or 20


def _build_context_builder(config: dict[str, Any]) -> ContextBuilder:
    retrieval_config = as_dict(config.get("retrieval"))
    max_chunks = json_int(retrieval_config, "final_context_top_k") or DEFAULT_MAX_CONTEXT_CHUNKS
    max_context_tokens = json_int(retrieval_config, "max_context_tokens")
    if max_context_tokens is None:
        max_chars = DEFAULT_MAX_CONTEXT_CHARS
    else:
        # P0 没有接入各模型 tokenizer，这里用保守字符预算近似 token 预算。
        max_chars = min(DEFAULT_MAX_CONTEXT_CHARS, max_context_tokens * 2)
    return ContextBuilder(max_chunks=max_chunks, max_chars=max_chars)


def _secret_value(session: Session, secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    try:
        return SecretStoreService().get_secret_value(session, secret_ref=secret_ref)
    except SecretStoreError:
        return None


def _timeout_seconds(timeout_ms: int | None, *, default_ms: int) -> float:
    return max(timeout_ms or default_ms, 1) / 1000


def _json_float(value_json: Any, key: str, *, default: float) -> float:
    if not isinstance(value_json, dict):
        return default
    value = value_json.get(key)
    if isinstance(value, int | float):
        return float(value)
    return default
