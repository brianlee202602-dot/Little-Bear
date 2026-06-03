"""Query Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.adapters import (
    QdrantVectorRetriever,
    VectorStoreCandidate,
    VectorStoreEmbeddingError,
    VectorStoreSearchFilter,
)
from app.modules.answer import AnswerService
from app.modules.config.service import ConfigService
from app.modules.context.service import (
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_MAX_CONTEXT_CHUNKS,
    ContextBuilder,
)
from app.modules.models import (
    ModelClientError,
    ModelGatewayChatClient,
    ModelGatewayEmbeddingClient,
    ModelGatewayRerankClient,
)
from app.modules.permissions.schemas import PermissionFilter
from app.modules.query.service import DEFAULT_RERANK_MIN_SCORE, QueryService
from app.modules.query_rewrite import QueryRewriteService
from app.modules.retrieval import (
    CandidateQualityGate,
    ModelCandidateReranker,
    NoopCandidateReranker,
    RetrievalCandidate,
    UnavailableVectorRetriever,
    VectorSearchResult,
)
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.storage.runtime import build_object_storage_from_config
from app.modules.storage.service import ObjectStorage
from app.shared.json_utils import as_dict, json_bool, json_int, json_str
from sqlalchemy.orm import Session

DEFAULT_MODEL_PROVIDER_SECRET_REFS = {
    "embedding": "secret://rag/model/embedding-api-key",
    "rerank": "secret://rag/model/rerank-api-key",
    "llm": "secret://rag/model/llm-api-key",
}


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


class _QdrantVectorRetrieverAdapter:
    def __init__(self, retriever: QdrantVectorRetriever) -> None:
        self.retriever = retriever

    def search(
        self,
        *,
        query_text: str,
        permission_filter: PermissionFilter,
        collection_names: tuple[str, ...],
        top_k: int,
    ) -> VectorSearchResult:
        result = self.retriever.search(
            query_text=query_text,
            permission_filter=VectorStoreSearchFilter(
                payload_filter=permission_filter.qdrant_filter,
            ),
            collection_names=collection_names,
            top_k=top_k,
        )
        return VectorSearchResult(
            candidates=tuple(_retrieval_candidate(candidate) for candidate in result.candidates),
            degraded=result.degraded,
            degrade_reason=result.degrade_reason,
        )


class _ObjectStorageChunkTextReader:
    """从对象存储读取 chunk 完整正文；失败时交由 ContextBuilder 回落 preview。"""

    def __init__(self, object_storage: ObjectStorage) -> None:
        self.object_storage = object_storage

    def read_text(self, *, object_key: str) -> str | None:
        try:
            content = self.object_storage.get_object(object_key=object_key)
        except (KeyError, OSError):
            return None
        return content.decode("utf-8", errors="replace")


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
    try:
        query_rewrite_service = _build_query_rewrite_service(session, config)
    except Exception:
        query_rewrite_service = QueryRewriteService()
    return QueryService(
        vector_retriever=vector_retriever,
        candidate_reranker=candidate_reranker,
        rerank_input_top_k=_rerank_input_top_k(config),
        rerank_min_score=_rerank_min_score(config),
        retrieval_weights=_retrieval_weights(config),
        candidate_quality_gate=_candidate_quality_gate(config),
        context_expand_neighbors=_context_expand_neighbors(config),
        context_builder=_build_context_builder(session, config),
        answer_service=answer_service,
        query_rewrite_service=query_rewrite_service,
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

    provider_auth_ref = _model_provider_auth_ref(model_gateway, embedding_provider, "embedding")
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
    return _QdrantVectorRetrieverAdapter(
        QdrantVectorRetriever(
            base_url=qdrant_base_url,
            api_key=_secret_value(session, json_str(vector_store, "api_key_ref")),
            embedding_client=_VectorStoreEmbeddingClientAdapter(embedding_client),
            timeout_seconds=_timeout_seconds(
                json_int(timeout_config, "vector_search_ms"),
                default_ms=3000,
            ),
        )
    )


def _embedding_path(provider: dict[str, Any]) -> str:
    configured = json_str(provider, "embeddings_path")
    if configured:
        return configured
    provider_type = json_str(provider, "type", default="http")
    return "/embed" if provider_type == "tei" else "/v1/embeddings"


def _retrieval_candidate(candidate: VectorStoreCandidate) -> RetrievalCandidate:
    return RetrievalCandidate(
        source="vector",
        enterprise_id=candidate.enterprise_id,
        kb_id=candidate.kb_id,
        document_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        chunk_id=candidate.chunk_id,
        title=candidate.title,
        owner_department_id=candidate.owner_department_id,
        visibility=candidate.visibility,
        document_lifecycle_status=candidate.document_lifecycle_status,
        document_index_status=candidate.document_index_status,
        chunk_status=candidate.chunk_status,
        visibility_state=candidate.visibility_state,
        index_version_id=candidate.index_version_id,
        indexed_permission_version=candidate.indexed_permission_version,
        page_start=candidate.page_start,
        page_end=candidate.page_end,
        rank=candidate.rank,
        score=candidate.score,
        source_score=candidate.score,
        embedding=candidate.embedding,
    )


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

    provider_auth_ref = _model_provider_auth_ref(model_gateway, llm_provider, "llm")
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

    provider_auth_ref = _model_provider_auth_ref(model_gateway, rerank_provider, "rerank")
    rerank_client = ModelGatewayRerankClient(
        base_url=rerank_base_url,
        path=_rerank_path(rerank_provider),
        provider_type=json_str(rerank_provider, "type", default="http") or "http",
        model=rerank_model,
        auth_token=_secret_value(session, provider_auth_ref),
        timeout_seconds=_timeout_seconds(
            json_int(timeout_config, "rerank_ms"),
            default_ms=3000,
        ),
    )
    return ModelCandidateReranker(rerank_client=rerank_client)


def _build_query_rewrite_service(session: Session, config: dict[str, Any]) -> QueryRewriteService:
    retrieval_config = as_dict(config.get("retrieval"))
    timeout_config = as_dict(config.get("timeout"))
    legacy_enabled = json_bool(retrieval_config, "rewrite_enabled", default=True)
    enabled = json_bool(
        retrieval_config,
        "query_rewrite_enabled",
        default=legacy_enabled,
    )
    use_llm = json_bool(retrieval_config, "query_rewrite_use_llm", default=False)
    max_queries = json_int(retrieval_config, "query_rewrite_max_queries") or 4
    recent_messages = json_int(retrieval_config, "query_rewrite_recent_messages") or 6
    use_conversation = json_bool(
        retrieval_config,
        "query_rewrite_use_conversation",
        default=True,
    )
    max_tokens = json_int(retrieval_config, "query_rewrite_max_tokens") or 512
    if not enabled or not use_llm:
        return QueryRewriteService(
            enabled=enabled,
            max_queries=max_queries,
            use_conversation=use_conversation,
            recent_messages=recent_messages,
            max_tokens=max_tokens,
        )

    model_gateway = as_dict(config.get("model_gateway"))
    model_config = as_dict(config.get("model"))
    providers = as_dict(model_gateway.get("providers"))
    llm_provider = as_dict(providers.get("llm"))
    llm_base_url = json_str(llm_provider, "base_url")
    llm_model = json_str(model_config, "llm_model")
    if not llm_base_url or not llm_model:
        return QueryRewriteService(
            enabled=enabled,
            max_queries=max_queries,
            use_conversation=use_conversation,
            recent_messages=recent_messages,
            max_tokens=max_tokens,
        )

    provider_auth_ref = _model_provider_auth_ref(model_gateway, llm_provider, "llm")
    chat_client = ModelGatewayChatClient(
        base_url=llm_base_url,
        path=_chat_completions_path(llm_provider),
        model=llm_model,
        auth_token=_secret_value(session, provider_auth_ref),
        timeout_seconds=_timeout_seconds(
            json_int(timeout_config, "query_rewrite_ms"),
            default_ms=3000,
        ),
        extra_body=as_dict(as_dict(config.get("llm")).get("openai_extra_body")) or None,
    )
    return QueryRewriteService(
        enabled=enabled,
        chat_client=chat_client,
        max_queries=max_queries,
        use_conversation=use_conversation,
        recent_messages=recent_messages,
        max_tokens=max_tokens,
    )


def _chat_completions_path(provider: dict[str, Any]) -> str:
    return json_str(provider, "chat_completions_path") or "/v1/chat/completions"


def _model_provider_auth_ref(
    model_gateway: dict[str, Any],
    provider: dict[str, Any],
    provider_name: str,
) -> str | None:
    return (
        json_str(provider, "auth_token_ref")
        or json_str(model_gateway, "auth_token_ref")
        or DEFAULT_MODEL_PROVIDER_SECRET_REFS.get(provider_name)
    )


def _rerank_path(provider: dict[str, Any]) -> str:
    return json_str(provider, "rerank_path") or "/rerank"


def _rerank_input_top_k(config: dict[str, Any]) -> int:
    retrieval_config = as_dict(config.get("retrieval"))
    return json_int(retrieval_config, "rerank_input_top_k") or 20


def _rerank_min_score(config: dict[str, Any]) -> float:
    retrieval_config = as_dict(config.get("retrieval"))
    return _json_float(
        retrieval_config,
        "rerank_min_score",
        default=DEFAULT_RERANK_MIN_SCORE,
    )


def _retrieval_weights(config: dict[str, Any]) -> dict[str, float]:
    retrieval_config = as_dict(config.get("retrieval"))
    fusion_params = as_dict(retrieval_config.get("fusion_params"))
    return {
        "keyword": _json_float(fusion_params, "keyword_weight", default=1.0),
        "vector": _json_float(fusion_params, "vector_weight", default=1.2),
        "original_query": _json_float(fusion_params, "original_query_weight", default=1.2),
        "rewrite_query": _json_float(fusion_params, "rewrite_query_weight", default=1.0),
    }


def _candidate_quality_gate(config: dict[str, Any]) -> CandidateQualityGate:
    retrieval_config = as_dict(config.get("retrieval"))
    fusion_params = as_dict(retrieval_config.get("fusion_params"))
    return CandidateQualityGate(
        min_fusion_score=_json_float(fusion_params, "min_fusion_score", default=0.01),
        min_source_score=_json_float(fusion_params, "min_source_score", default=0.02),
    )


def _context_expand_neighbors(config: dict[str, Any]) -> int:
    retrieval_config = as_dict(config.get("retrieval"))
    return max(json_int(retrieval_config, "context_expand_neighbors") or 0, 0)


def _build_context_builder(session: Session, config: dict[str, Any]) -> ContextBuilder:
    retrieval_config = as_dict(config.get("retrieval"))
    max_chunks = json_int(retrieval_config, "final_context_top_k") or DEFAULT_MAX_CONTEXT_CHUNKS
    max_context_tokens = json_int(retrieval_config, "max_context_tokens")
    return ContextBuilder(
        max_chunks=max_chunks,
        max_chars=DEFAULT_MAX_CONTEXT_CHARS,
        max_context_tokens=max_context_tokens,
        max_chunks_per_document=json_int(retrieval_config, "max_chunks_per_document") or 3,
        max_chunks_per_section=json_int(retrieval_config, "max_chunks_per_section") or 2,
        mmr_enabled=json_bool(retrieval_config, "mmr_enabled", default=True),
        mmr_lambda=_json_float(retrieval_config, "mmr_lambda", default=0.7),
        chunk_text_reader=_build_chunk_text_reader(session, config),
    )


def _build_chunk_text_reader(
    session: Session,
    config: dict[str, Any],
) -> _ObjectStorageChunkTextReader | None:
    try:
        object_storage = build_object_storage_from_config(session, config, required=False)
    except Exception:
        return None
    if object_storage is None:
        return None
    return _ObjectStorageChunkTextReader(object_storage)


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
