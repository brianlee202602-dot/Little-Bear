"""OpenAI-compatible Chat Completions client。"""

from __future__ import annotations

import json
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


class ChatCompletionClient(Protocol):
    def complete(
        self,
        *,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletionResult:
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
