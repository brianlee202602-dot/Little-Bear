from __future__ import annotations

from types import SimpleNamespace

from app.modules.models import ModelGatewayChatClient, ModelGatewayRerankClient
from app.modules.query.runtime import build_query_service
from app.modules.retrieval import ModelCandidateReranker


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
    assert service.context_builder.max_chunks == 4
    assert service.context_builder.max_chars == 1800
    assert "secret://llm" in secrets
    assert "secret://rerank" in secrets


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
