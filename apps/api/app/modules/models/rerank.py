"""Rerank provider client。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.modules.models.errors import ModelClientError
from app.shared.json_utils import stable_json_hash


@dataclass(frozen=True)
class RerankScoredItem:
    index: int
    score: float


@dataclass(frozen=True)
class RerankClientResult:
    items: tuple[RerankScoredItem, ...]
    model_name: str
    model_route_hash: str
    latency_ms: int
    input_hash: str
    output_hash: str


class RerankClient(Protocol):
    def rerank(
        self,
        *,
        query_text: str,
        texts: tuple[str, ...],
        top_k: int,
    ) -> RerankClientResult:
        ...


class ModelGatewayRerankClient:
    """通过 active_config 中的 rerank provider 调用外部精排服务。"""

    def __init__(
        self,
        *,
        base_url: str,
        path: str,
        provider_type: str,
        model: str,
        auth_token: str | None = None,
        timeout_seconds: float = 0.8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"
        self.provider_type = provider_type
        self.model = model
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds

    def rerank(
        self,
        *,
        query_text: str,
        texts: tuple[str, ...],
        top_k: int,
    ) -> RerankClientResult:
        if not texts:
            return RerankClientResult(
                items=(),
                model_name=self.model,
                model_route_hash=self.model_route_hash,
                latency_ms=0,
                input_hash=stable_json_hash({"query": query_text, "texts": []}),
                output_hash=stable_json_hash({"items": []}),
            )
        input_hash = stable_json_hash({"query": query_text, "texts": list(texts)})
        started_at = time.monotonic()
        response = _post_json(
            _join_url(self.base_url, self.path),
            _rerank_payload(
                provider_type=self.provider_type,
                model=self.model,
                query_text=query_text,
                texts=texts,
                top_k=top_k,
            ),
            timeout_seconds=self.timeout_seconds,
            auth_token=self.auth_token,
        )
        items = _extract_items(response)
        if not items:
            raise ModelClientError(
                "RERANK_PROVIDER_RESPONSE_INVALID",
                "rerank provider response does not contain scores",
            )
        limited = tuple(sorted(items, key=lambda item: item.score, reverse=True)[: max(top_k, 1)])
        return RerankClientResult(
            items=limited,
            model_name=self.model,
            model_route_hash=self.model_route_hash,
            latency_ms=_elapsed_ms(started_at),
            input_hash=input_hash,
            output_hash=stable_json_hash(
                {"items": [{"index": item.index, "score": item.score} for item in limited]}
            ),
        )

    @property
    def model_route_hash(self) -> str:
        return stable_json_hash(
            {"base_url": self.base_url, "path": self.path, "model": self.model}
        )


def _rerank_payload(
    *,
    provider_type: str,
    model: str,
    query_text: str,
    texts: tuple[str, ...],
    top_k: int,
) -> dict[str, Any]:
    if provider_type == "tei":
        return {
            "query": query_text,
            "texts": list(texts),
            "raw_scores": False,
            "return_text": False,
            "truncate": True,
        }
    return {
        "model": model,
        "query": query_text,
        "documents": list(texts),
        "top_n": max(top_k, 1),
    }


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
        raise ModelClientError(
            "RERANK_PROVIDER_HTTP_ERROR",
            f"rerank provider returned HTTP {exc.code}",
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelClientError(
            "RERANK_PROVIDER_UNAVAILABLE",
            f"rerank provider request failed: {exc.__class__.__name__}",
        ) from exc
    if status < 200 or status >= 300:
        raise ModelClientError(
            "RERANK_PROVIDER_HTTP_ERROR",
            f"rerank provider returned HTTP {status}",
        )
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelClientError(
            "RERANK_PROVIDER_RESPONSE_INVALID",
            "rerank provider response is not valid JSON",
        ) from exc


def _extract_items(response: Any) -> tuple[RerankScoredItem, ...]:
    values: Any = response
    if isinstance(response, dict):
        for key in ("results", "data", "rerankings"):
            if isinstance(response.get(key), list):
                values = response[key]
                break
    if not isinstance(values, list):
        raise ModelClientError(
            "RERANK_PROVIDER_RESPONSE_INVALID",
            "rerank provider response must contain a list of scores",
        )
    return tuple(
        item
        for index, value in enumerate(values)
        if (item := _item_from_value(value, default_index=index)) is not None
    )


def _item_from_value(value: Any, *, default_index: int) -> RerankScoredItem | None:
    if isinstance(value, int | float):
        return RerankScoredItem(index=default_index, score=float(value))
    if not isinstance(value, dict):
        return None
    index = value.get("index", value.get("document_index", default_index))
    score = value.get("score", value.get("relevance_score", value.get("relevanceScore")))
    if not isinstance(index, int) or not isinstance(score, int | float):
        return None
    return RerankScoredItem(index=index, score=float(score))


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _elapsed_ms(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)
