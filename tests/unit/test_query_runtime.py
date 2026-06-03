from __future__ import annotations

from types import SimpleNamespace

from app.modules.models import ModelGatewayChatClient, ModelGatewayRerankClient
from app.modules.query.runtime import build_query_service
from app.modules.retrieval import ModelCandidateReranker
from app.modules.storage.service import InMemoryObjectStorage


def test_build_query_service_wires_llm_provider_from_active_config(monkeypatch) -> None:
    secrets: list[str] = []

    monkeypatch.setattr(
        "app.modules.query.runtime.ConfigService.load_active_config",
        lambda *_args, **_kwargs: SimpleNamespace(config=_active_config()),
    )

    def _get_secret(_self, _session, *, secret_ref: str) -> str:
        secrets.append(secret_ref)
        return f"value-for-{secret_ref}"

    monkeypatch.setattr(
        "app.modules.query.runtime.SecretStoreService.get_secret_value",
        _get_secret,
    )

    service = build_query_service(object())

    chat_client = service.answer_service.chat_client
    assert isinstance(chat_client, ModelGatewayChatClient)
    assert chat_client.base_url == "https://llm.example"
    assert chat_client.path == "/v1/chat/completions"
    assert chat_client.model == "qwen3-4b"
    assert chat_client.auth_token == "value-for-secret://llm"
    assert chat_client.timeout_seconds == 12.0
    assert chat_client.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    assert service.answer_service.temperature == 0.2
    assert service.answer_service.max_tokens == 512
    assert isinstance(service.candidate_reranker, ModelCandidateReranker)
    rerank_client = service.candidate_reranker.rerank_client
    assert isinstance(rerank_client, ModelGatewayRerankClient)
    assert rerank_client.base_url == "https://rerank.example"
    assert rerank_client.path == "/rerank"
    assert rerank_client.model == "bge-reranker"
    assert rerank_client.auth_token == "value-for-secret://rerank"
    assert rerank_client.timeout_seconds == 0.7
    assert service.rerank_input_top_k == 20
    assert service.rerank_min_score == 0.05
    assert service.context_builder.max_chunks == 4
    assert service.context_builder.max_chars == 6000
    assert service.context_builder.max_context_tokens == 900
    assert "secret://llm" in secrets
    assert "secret://rerank" in secrets


def test_build_query_service_wires_context_chunk_text_reader(monkeypatch) -> None:
    storage = InMemoryObjectStorage({"chunks/doc_1/chunk_1.txt": "完整正文".encode()})

    monkeypatch.setattr(
        "app.modules.query.runtime.ConfigService.load_active_config",
        lambda *_args, **_kwargs: SimpleNamespace(config=_active_config()),
    )
    monkeypatch.setattr(
        "app.modules.query.runtime.SecretStoreService.get_secret_value",
        lambda _self, _session, *, secret_ref: f"value-for-{secret_ref}",
    )
    monkeypatch.setattr(
        "app.modules.query.runtime.build_object_storage_from_config",
        lambda *_args, **_kwargs: storage,
    )

    service = build_query_service(object())

    reader = service.context_builder.chunk_text_reader
    assert reader is not None
    assert reader.read_text(object_key="chunks/doc_1/chunk_1.txt") == "完整正文"


def test_build_query_service_falls_back_to_default_model_secret_refs(monkeypatch) -> None:
    secrets: list[str] = []
    config = _active_config()
    model_gateway = config["model_gateway"]
    assert isinstance(model_gateway, dict)
    model_gateway["auth_token_ref"] = None
    providers = model_gateway["providers"]
    assert isinstance(providers, dict)
    for provider in providers.values():
        assert isinstance(provider, dict)
        provider["auth_token_ref"] = None

    monkeypatch.setattr(
        "app.modules.query.runtime.ConfigService.load_active_config",
        lambda *_args, **_kwargs: SimpleNamespace(config=config),
    )

    def _get_secret(_self, _session, *, secret_ref: str) -> str:
        secrets.append(secret_ref)
        return f"value-for-{secret_ref}"

    monkeypatch.setattr(
        "app.modules.query.runtime.SecretStoreService.get_secret_value",
        _get_secret,
    )

    service = build_query_service(object())

    assert service.answer_service.chat_client is not None
    assert service.answer_service.chat_client.auth_token == (
        "value-for-secret://rag/model/llm-api-key"
    )
    assert "secret://rag/model/embedding-api-key" in secrets
    assert "secret://rag/model/rerank-api-key" in secrets
    assert "secret://rag/model/llm-api-key" in secrets


def test_build_query_service_wires_optional_query_rewrite_llm(monkeypatch) -> None:
    config = _active_config()
    retrieval = config["retrieval"]
    assert isinstance(retrieval, dict)
    retrieval["query_rewrite_use_llm"] = True
    retrieval["query_rewrite_max_queries"] = 5
    retrieval["query_rewrite_recent_messages"] = 4
    retrieval["query_rewrite_max_tokens"] = 256
    timeout = config["timeout"]
    assert isinstance(timeout, dict)
    timeout["query_rewrite_ms"] = 1400

    monkeypatch.setattr(
        "app.modules.query.runtime.ConfigService.load_active_config",
        lambda *_args, **_kwargs: SimpleNamespace(config=config),
    )
    monkeypatch.setattr(
        "app.modules.query.runtime.SecretStoreService.get_secret_value",
        lambda _self, _session, *, secret_ref: f"value-for-{secret_ref}",
    )

    service = build_query_service(object())

    rewrite_service = service.query_rewrite_service
    rewrite_client = rewrite_service.chat_client
    assert isinstance(rewrite_client, ModelGatewayChatClient)
    assert rewrite_client.base_url == "https://llm.example"
    assert rewrite_client.timeout_seconds == 1.4
    assert rewrite_service.max_queries == 5
    assert rewrite_service.recent_messages == 4
    assert rewrite_service.max_tokens == 256


def test_build_query_service_uses_legacy_rewrite_enabled_as_rewrite_fallback(
    monkeypatch,
) -> None:
    config = _active_config()
    retrieval = config["retrieval"]
    assert isinstance(retrieval, dict)
    retrieval["rewrite_enabled"] = False
    retrieval.pop("query_rewrite_enabled", None)

    monkeypatch.setattr(
        "app.modules.query.runtime.ConfigService.load_active_config",
        lambda *_args, **_kwargs: SimpleNamespace(config=config),
    )

    service = build_query_service(object())

    assert service.query_rewrite_service.enabled is False


def _active_config() -> dict[str, object]:
    return {
        "vector_store": {
            "qdrant_base_url": "https://qdrant.example",
            "api_key_ref": "secret://qdrant",
        },
        "model_gateway": {
            "auth_token_ref": "secret://gateway",
            "providers": {
                "embedding": {
                    "type": "openai_compatible",
                    "base_url": "https://embedding.example",
                    "embeddings_path": "/v1/embeddings",
                    "auth_token_ref": "secret://embedding",
                },
                "llm": {
                    "type": "openai_compatible",
                    "base_url": "https://llm.example",
                    "chat_completions_path": "/v1/chat/completions",
                    "auth_token_ref": "secret://llm",
                },
                "rerank": {
                    "type": "tei",
                    "base_url": "https://rerank.example",
                    "rerank_path": "/rerank",
                    "auth_token_ref": "secret://rerank",
                },
            },
        },
        "model": {
            "embedding_model": "bge-m3",
            "embedding_dimension": 2,
            "embedding_normalize": True,
            "llm_model": "qwen3-4b",
            "rerank_model": "bge-reranker",
        },
        "timeout": {
            "embedding_ms": 3000,
            "vector_search_ms": 3000,
            "rerank_ms": 700,
        },
        "retrieval": {
            "rerank_input_top_k": 20,
            "rerank_min_score": 0.05,
            "final_context_top_k": 4,
            "max_context_tokens": 900,
        },
        "llm": {
            "temperature": 0.2,
            "max_tokens": 512,
            "total_timeout_ms": 12000,
            "openai_extra_body": {
                "chat_template_kwargs": {"enable_thinking": False},
            },
        },
    }
