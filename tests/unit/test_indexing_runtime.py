from __future__ import annotations

from types import SimpleNamespace

from app.modules.indexing.runtime import build_indexing_service


def test_build_indexing_service_uses_indexing_timeout_floor(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.indexing.runtime.ConfigService.load_active_config",
        lambda *_args, **_kwargs: SimpleNamespace(config=_active_config()),
    )

    service = build_indexing_service(object())

    writer = service.vector_index_writer
    assert writer.embedding_client.timeout_seconds == 3.0
    assert writer.timeout_seconds == 3.0


def _active_config() -> dict[str, object]:
    return {
        "vector_store": {
            "qdrant_base_url": "https://qdrant.example",
            "collection_prefix": "little_bear_p0",
        },
        "model_gateway": {
            "providers": {
                "embedding": {
                    "type": "tei",
                    "base_url": "https://embedding.example",
                    "embeddings_path": "/v1/embeddings",
                },
            },
        },
        "model": {
            "embedding_model": "bge-m3",
            "embedding_dimension": 768,
            "embedding_normalize": True,
        },
        "timeout": {
            "embedding_ms": 500,
            "vector_search_ms": 500,
        },
    }
