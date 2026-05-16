from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest
from app.modules.models import ChatMessage, ModelClientError, ModelGatewayChatClient


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


def test_chat_client_calls_openai_compatible_chat_completions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(
            {
                "choices": [
                    {"message": {"content": "员工年假需要提前申请。[source:chunk_1]"}}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )

    monkeypatch.setattr("app.modules.models.chat.urlopen", _urlopen)

    result = ModelGatewayChatClient(
        base_url="https://model.example",
        path="/v1/chat/completions",
        model="qwen3-4b",
        auth_token="token",
        timeout_seconds=2.5,
    ).complete(
        messages=(
            ChatMessage(role="system", content="system prompt"),
            ChatMessage(role="user", content="员工年假怎么申请？"),
        ),
        temperature=0.1,
        max_tokens=800,
    )

    assert captured["url"] == "https://model.example/v1/chat/completions"
    assert captured["timeout"] == 2.5
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["body"] == {
        "model": "qwen3-4b",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "员工年假怎么申请？"},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "stream": False,
    }
    assert result.content == "员工年假需要提前申请。[source:chunk_1]"
    assert result.token_usage == {"prompt_tokens": 10, "completion_tokens": 5}


def test_chat_client_rejects_invalid_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.models.chat.urlopen",
        lambda *_args, **_kwargs: _Response({"choices": []}),
    )

    with pytest.raises(ModelClientError) as exc_info:
        ModelGatewayChatClient(
            base_url="https://model.example",
            path="/v1/chat/completions",
            model="qwen3-4b",
        ).complete(
            messages=(ChatMessage(role="user", content="员工年假怎么申请？"),),
            temperature=0.1,
            max_tokens=800,
        )

    assert exc_info.value.error_code == "LLM_PROVIDER_RESPONSE_INVALID"


def test_chat_client_merges_extra_body_without_overriding_core_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response({"choices": [{"message": {"content": "答案"}}]})

    monkeypatch.setattr("app.modules.models.chat.urlopen", _urlopen)

    ModelGatewayChatClient(
        base_url="https://model.example",
        path="/v1/chat/completions",
        model="qwen3-4b",
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": 999,
        },
    ).complete(
        messages=(ChatMessage(role="user", content="员工年假怎么申请？"),),
        temperature=0.1,
        max_tokens=128,
    )

    assert captured["body"]["max_tokens"] == 128
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_chat_client_includes_http_error_body(monkeypatch) -> None:
    def _urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs={},
            fp=BytesIO(b'{"error":{"message":"context length exceeded"}}'),
        )

    monkeypatch.setattr("app.modules.models.chat.urlopen", _urlopen)

    with pytest.raises(ModelClientError) as exc_info:
        ModelGatewayChatClient(
            base_url="https://model.example",
            path="/v1/chat/completions",
            model="qwen3-4b",
        ).complete(
            messages=(ChatMessage(role="user", content="员工年假怎么申请？"),),
            temperature=0.1,
            max_tokens=800,
        )

    assert exc_info.value.error_code == "LLM_PROVIDER_HTTP_ERROR"
    assert "HTTP 400" in exc_info.value.message
    assert "context length exceeded" in exc_info.value.message
