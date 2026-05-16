from __future__ import annotations

import json
import math

import pytest
from app.modules.models import ModelClientError, ModelGatewayEmbeddingClient


class _Response:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_embedding_client_parses_openai_compatible_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response({"data": [{"embedding": [3.0, 4.0]}]})

    monkeypatch.setattr("app.modules.models.embeddings.urlopen", _urlopen)

    vector = ModelGatewayEmbeddingClient(
        base_url="https://model.example",
        path="/v1/embeddings",
        provider_type="openai_compatible",
        model="bge-m3",
        auth_token="token",
        timeout_seconds=1.5,
        expected_dimension=2,
        normalize=True,
    ).embed_query("员工手册")

    assert captured["url"] == "https://model.example/v1/embeddings"
    assert captured["timeout"] == 1.5
    assert captured["body"] == {"model": "bge-m3", "input": ["员工手册"]}
    assert math.isclose(vector[0], 0.6)
    assert math.isclose(vector[1], 0.8)


def test_embedding_client_rejects_dimension_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.models.embeddings.urlopen",
        lambda *_args, **_kwargs: _Response([[1.0, 2.0]]),
    )

    with pytest.raises(ModelClientError) as exc_info:
        ModelGatewayEmbeddingClient(
            base_url="https://model.example",
            path="/embed",
            provider_type="tei",
            model="bge-m3",
            expected_dimension=3,
        ).embed_query("员工手册")

    assert exc_info.value.error_code == "EMBEDDING_DIMENSION_MISMATCH"


def test_embedding_client_batches_tei_embeddings(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response([[1.0, 0.0], [0.0, 2.0]])

    monkeypatch.setattr("app.modules.models.embeddings.urlopen", _urlopen)

    vectors = ModelGatewayEmbeddingClient(
        base_url="https://model.example",
        path="/embed",
        provider_type="tei",
        model="bge-m3",
        expected_dimension=2,
        normalize=True,
    ).embed_texts(["第一段", "第二段"])

    assert captured["url"] == "https://model.example/embed"
    assert captured["body"] == {"inputs": ["第一段", "第二段"]}
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


def test_embedding_client_uses_openai_payload_for_tei_v1_embeddings_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response({"data": [{"embedding": [1.0, 0.0]}]})

    monkeypatch.setattr("app.modules.models.embeddings.urlopen", _urlopen)

    vectors = ModelGatewayEmbeddingClient(
        base_url="https://model.example",
        path="/v1/embeddings",
        provider_type="tei",
        model="bge-m3",
        expected_dimension=2,
    ).embed_texts(["第一段"])

    assert captured["url"] == "https://model.example/v1/embeddings"
    assert captured["body"] == {"model": "bge-m3", "input": ["第一段"]}
    assert vectors == [[1.0, 0.0]]
