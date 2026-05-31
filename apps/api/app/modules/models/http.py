"""模型 provider 共享 HTTP transport。"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.modules.models.errors import ModelClientError

MAX_PROVIDER_ERROR_BODY_CHARS = 1000
UrlOpen = Callable[..., Any]


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    auth_token: str | None,
    provider_label: str,
    http_error_code: str,
    unavailable_error_code: str,
    response_invalid_error_code: str,
    opener: UrlOpen = urlopen,
) -> Any:
    response_body = post_bytes(
        url,
        payload,
        timeout_seconds=timeout_seconds,
        auth_token=auth_token,
        accept="application/json",
        provider_label=provider_label,
        http_error_code=http_error_code,
        unavailable_error_code=unavailable_error_code,
        opener=opener,
    )
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelClientError(
            response_invalid_error_code,
            f"{provider_label} response is not valid JSON",
        ) from exc


def post_bytes(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    auth_token: str | None,
    accept: str,
    provider_label: str,
    http_error_code: str,
    unavailable_error_code: str,
    opener: UrlOpen = urlopen,
) -> bytes:
    request = json_post_request(
        url,
        payload,
        auth_token=auth_token,
        accept=accept,
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            response_body = response.read()
    except HTTPError as exc:
        response_body = exc.read()
        raise ModelClientError(
            http_error_code,
            http_error_message(provider_label, exc.code, response_body),
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelClientError(
            unavailable_error_code,
            f"{provider_label} request failed: {exc.__class__.__name__}",
        ) from exc
    if status < 200 or status >= 300:
        raise ModelClientError(
            http_error_code,
            http_error_message(provider_label, status, response_body),
        )
    return response_body


def post_stream_lines(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    auth_token: str | None,
    provider_label: str,
    http_error_code: str,
    unavailable_error_code: str,
    opener: UrlOpen = urlopen,
) -> Iterator[bytes]:
    request = json_post_request(
        url,
        payload,
        auth_token=auth_token,
        accept="text/event-stream",
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise ModelClientError(
                    http_error_code,
                    http_error_message(provider_label, status, None),
                )
            yield from response
    except HTTPError as exc:
        response_body = exc.read()
        raise ModelClientError(
            http_error_code,
            http_error_message(provider_label, exc.code, response_body),
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelClientError(
            unavailable_error_code,
            f"{provider_label} streaming request failed: {exc.__class__.__name__}",
        ) from exc


def json_post_request(
    url: str,
    payload: dict[str, Any],
    *,
    auth_token: str | None,
    accept: str,
) -> Request:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json", "accept": accept}
    if auth_token:
        headers["authorization"] = f"Bearer {auth_token}"
    return Request(url, data=body, headers=headers, method="POST")


def http_error_message(
    provider_label: str,
    status: int,
    response_body: bytes | None,
) -> str:
    snippet = response_body_snippet(response_body)
    if not snippet:
        return f"{provider_label} returned HTTP {status}"
    return f"{provider_label} returned HTTP {status}: {snippet}"


def response_body_snippet(response_body: bytes | None) -> str | None:
    if not response_body:
        return None
    text = response_body.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= MAX_PROVIDER_ERROR_BODY_CHARS:
        return compact
    return f"{compact[:MAX_PROVIDER_ERROR_BODY_CHARS].rstrip()}..."


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
