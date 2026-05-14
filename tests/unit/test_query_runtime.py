from __future__ import annotations

from types import SimpleNamespace

from app.modules.models import ModelGatewayChatClient
from app.modules.query.runtime import build_query_service


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
    assert service.answer_service.temperature == 0.2
    assert service.answer_service.max_tokens == 512
    assert "secret://llm" in secrets


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
            },
        },
        "model": {
            "embedding_model": "bge-m3",
            "embedding_dimension": 2,
            "embedding_normalize": True,
            "llm_model": "qwen3-4b",
        },
        "timeout": {
            "embedding_ms": 3000,
            "vector_search_ms": 3000,
        },
        "llm": {
            "temperature": 0.2,
            "max_tokens": 512,
            "total_timeout_ms": 12000,
        },
    }
