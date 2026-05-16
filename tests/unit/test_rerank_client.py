from __future__ import annotations

import json

from app.modules.models import ModelGatewayRerankClient


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


def test_rerank_client_calls_tei_provider_and_sorts_scores(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(
            {
                "results": [
                    {"index": 1, "score": 0.2},
                    {"index": 0, "score": 0.9},
                ]
            }
        )

    monkeypatch.setattr("app.modules.models.rerank.urlopen", _urlopen)

    result = ModelGatewayRerankClient(
        base_url="https://model.example",
        path="/rerank",
        provider_type="tei",
        model="bge-reranker",
        auth_token="token",
        timeout_seconds=0.8,
    ).rerank(
        query_text="员工手册",
        texts=("第一段", "第二段"),
        top_k=2,
    )

    assert captured["url"] == "https://model.example/rerank"
    assert captured["timeout"] == 0.8
    assert captured["body"] == {
        "query": "员工手册",
        "texts": ["第一段", "第二段"],
        "raw_scores": False,
        "return_text": False,
        "truncate": True,
    }
    assert [item.index for item in result.items] == [0, 1]
    assert [item.score for item in result.items] == [0.9, 0.2]
    assert result.input_hash
    assert result.output_hash


def test_rerank_client_parses_openai_style_numeric_scores(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response({"data": [0.1, 0.8]})

    monkeypatch.setattr("app.modules.models.rerank.urlopen", _urlopen)

    result = ModelGatewayRerankClient(
        base_url="https://model.example",
        path="/v1/rerank",
        provider_type="openai_compatible",
        model="rerank-v1",
    ).rerank(
        query_text="员工手册",
        texts=("第一段", "第二段"),
        top_k=1,
    )

    assert captured["body"] == {
        "model": "rerank-v1",
        "query": "员工手册",
        "documents": ["第一段", "第二段"],
        "top_n": 1,
    }
    assert [item.index for item in result.items] == [1]
    assert [item.score for item in result.items] == [0.8]
