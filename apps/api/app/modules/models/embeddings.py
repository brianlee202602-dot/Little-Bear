"""Embedding provider client。"""

from __future__ import annotations

import json
import math
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.modules.models.errors import ModelClientError


class EmbeddingClient(Protocol):
    """查询向量化端口。"""

    def embed_query(self, query_text: str) -> list[float]:
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class ModelGatewayEmbeddingClient:
    """通过 active_config 中的 embedding provider 调用外部模型服务。"""

    def __init__(
        self,
        *,
        base_url: str,
        path: str,
        provider_type: str,
        model: str,
        auth_token: str | None = None,
        timeout_seconds: float = 3.0,
        expected_dimension: int | None = None,
        normalize: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"
        self.provider_type = provider_type
        self.model = model
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds
        self.expected_dimension = expected_dimension
        self.normalize = normalize

    def embed_query(self, query_text: str) -> list[float]:
        vectors = self.embed_texts([query_text])
        if not vectors:
            raise ModelClientError(
                "EMBEDDING_PROVIDER_RESPONSE_INVALID",
                "embedding provider response does not contain an embedding vector",
            )
        return vectors[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = _embedding_payload(
            provider_type=self.provider_type,
            model=self.model,
            texts=texts,
        )
        response = _post_json(
            _join_url(self.base_url, self.path),
            payload,
            timeout_seconds=self.timeout_seconds,
            auth_token=self.auth_token,
        )
        vectors = _extract_embeddings(response)
        if len(vectors) != len(texts):
            raise ModelClientError(
                "EMBEDDING_COUNT_MISMATCH",
                "embedding count does not match input count",
            )
        return [self._validate_vector(vector) for vector in vectors]

    def _validate_vector(self, vector: list[float]) -> list[float]:
        if self.expected_dimension is not None and len(vector) != self.expected_dimension:
            raise ModelClientError(
                "EMBEDDING_DIMENSION_MISMATCH",
                "embedding dimension does not match active config",
            )
        return _l2_normalize(vector) if self.normalize else vector


def _embedding_payload(*, provider_type: str, model: str, texts: list[str]) -> dict[str, Any]:
    if provider_type == "tei":
        return {"inputs": texts}
    return {"model": model, "input": texts}


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
            "EMBEDDING_PROVIDER_HTTP_ERROR",
            f"embedding provider returned HTTP {exc.code}",
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelClientError(
            "EMBEDDING_PROVIDER_UNAVAILABLE",
            f"embedding provider request failed: {exc.__class__.__name__}",
        ) from exc
    if status < 200 or status >= 300:
        raise ModelClientError(
            "EMBEDDING_PROVIDER_HTTP_ERROR",
            f"embedding provider returned HTTP {status}",
        )
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelClientError(
            "EMBEDDING_PROVIDER_RESPONSE_INVALID",
            "embedding provider response is not valid JSON",
        ) from exc


def _extract_embeddings(response: Any) -> list[list[float]]:
    value: Any = response
    if isinstance(response, dict):
        if isinstance(response.get("data"), list) and response["data"]:
            return [
                _coerce_vector(item.get("embedding") if isinstance(item, dict) else item)
                for item in response["data"]
            ]
        elif "embedding" in response:
            value = response["embedding"]
        elif "embeddings" in response:
            value = response["embeddings"]
    if isinstance(value, list) and value and all(_is_number(item) for item in value):
        return [_coerce_vector(value)]
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [_coerce_vector(item) for item in value]
    raise ModelClientError(
        "EMBEDDING_PROVIDER_RESPONSE_INVALID",
        "embedding provider response does not contain an embedding vector",
    )


def _coerce_vector(value: Any) -> list[float]:
    if isinstance(value, list) and value and all(_is_number(item) for item in value):
        return [float(item) for item in value]
    raise ModelClientError(
        "EMBEDDING_PROVIDER_RESPONSE_INVALID",
        "embedding provider response does not contain an embedding vector",
    )


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(item * item for item in vector))
    if norm == 0:
        return vector
    return [item / norm for item in vector]


def _is_number(value: object) -> bool:
    return isinstance(value, int | float)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
