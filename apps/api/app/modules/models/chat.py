"""OpenAI-compatible Chat Completions client。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.modules.models.errors import ModelClientError

ChatRole = Literal["system", "user", "assistant"]
MAX_PROVIDER_ERROR_BODY_CHARS = 1000


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class ChatCompletionResult:
    content: str
    token_usage: dict[str, int] | None = None


@dataclass(frozen=True)
class ChatCompletionChunk:
    content_delta: str = ""
    token_usage: dict[str, int] | None = None


class ChatCompletionClient(Protocol):
    def complete(
        self,
        *,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletionResult:
        ...

    def stream_complete(
        self,
        *,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        max_tokens: int,
    ) -> Iterator[ChatCompletionChunk]:
        ...


class ModelGatewayChatClient:
    """通过 active_config 中的 LLM provider 调用 OpenAI-compatible Chat Completions。"""

    def __init__(
        self,
        *,
        base_url: str,
        path: str,
        model: str,
        auth_token: str | None = None,
        timeout_seconds: float = 20.0,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"
        self.model = model
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds
        self.extra_body = dict(extra_body or {})

    def complete(
        self,
        *,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletionResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        for key, value in self.extra_body.items():
            if key not in payload:
                payload[key] = value
        response = _post_json(
            _join_url(self.base_url, self.path),
            payload,
            timeout_seconds=self.timeout_seconds,
            auth_token=self.auth_token,
        )
        return ChatCompletionResult(
            content=_extract_chat_content(response),
            token_usage=_extract_token_usage(response),
        )

    def stream_complete(
        self,
        *,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        max_tokens: int,
    ) -> Iterator[ChatCompletionChunk]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        for key, value in self.extra_body.items():
            if key not in payload:
                payload[key] = value
        yield from _post_json_stream(
            _join_url(self.base_url, self.path),
            payload,
            timeout_seconds=self.timeout_seconds,
            auth_token=self.auth_token,
        )


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    auth_token: str | None,
) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json", "accept": "application/json"}
    if auth_token:
        headers["authorization"] = f"Bearer {auth_token}"
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            response_body = response.read()
    except HTTPError as exc:
        response_body = exc.read()
        raise ModelClientError(
            "LLM_PROVIDER_HTTP_ERROR",
            _http_error_message(exc.code, response_body),
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelClientError(
            "LLM_PROVIDER_UNAVAILABLE",
            f"LLM provider request failed: {exc.__class__.__name__}",
        ) from exc
    if status < 200 or status >= 300:
        raise ModelClientError(
            "LLM_PROVIDER_HTTP_ERROR",
            _http_error_message(status, response_body),
        )
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider response is not valid JSON",
        ) from exc


def _post_json_stream(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    auth_token: str | None,
) -> Iterator[ChatCompletionChunk]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json", "accept": "text/event-stream"}
    if auth_token:
        headers["authorization"] = f"Bearer {auth_token}"
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise ModelClientError(
                    "LLM_PROVIDER_HTTP_ERROR",
                    f"LLM provider returned HTTP {status}",
                )
            for raw_line in response:
                chunk = _parse_stream_line(raw_line)
                if chunk is not None:
                    yield chunk
    except HTTPError as exc:
        response_body = exc.read()
        raise ModelClientError(
            "LLM_PROVIDER_HTTP_ERROR",
            _http_error_message(exc.code, response_body),
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelClientError(
            "LLM_PROVIDER_UNAVAILABLE",
            f"LLM provider streaming request failed: {exc.__class__.__name__}",
        ) from exc


def _parse_stream_line(raw_line: bytes) -> ChatCompletionChunk | None:
    try:
        line = raw_line.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider stream is not valid UTF-8",
        ) from exc
    if not line or line.startswith(":") or not line.startswith("data:"):
        return None
    data = line.removeprefix("data:").strip()
    if data == "[DONE]":
        return None
    try:
        event = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider stream event is not valid JSON",
        ) from exc
    if not isinstance(event, dict):
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider stream event must be a JSON object",
        )
    return ChatCompletionChunk(
        content_delta=_extract_stream_delta(event),
        token_usage=_extract_token_usage(event),
    )


def _extract_stream_delta(event: dict[str, Any]) -> str:
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    return text if isinstance(text, str) else ""


def _extract_chat_content(response: Any) -> str:
    if not isinstance(response, dict):
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider response must be a JSON object",
        )
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider response does not contain choices",
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider choice is invalid",
        )
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else first.get("text")
    if not isinstance(content, str) or not content.strip():
        raise ModelClientError(
            "LLM_PROVIDER_RESPONSE_INVALID",
            "LLM provider response does not contain answer content",
        )
    return content.strip()


def _extract_token_usage(response: Any) -> dict[str, int] | None:
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    normalized = {
        key: value
        for key, value in usage.items()
        if isinstance(key, str) and isinstance(value, int)
    }
    return normalized or None


def _http_error_message(status: int, response_body: bytes | None) -> str:
    snippet = _response_body_snippet(response_body)
    if not snippet:
        return f"LLM provider returned HTTP {status}"
    return f"LLM provider returned HTTP {status}: {snippet}"


def _response_body_snippet(response_body: bytes | None) -> str | None:
    if not response_body:
        return None
    text = response_body.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= MAX_PROVIDER_ERROR_BODY_CHARS:
        return compact
    return f"{compact[:MAX_PROVIDER_ERROR_BODY_CHARS].rstrip()}..."


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
