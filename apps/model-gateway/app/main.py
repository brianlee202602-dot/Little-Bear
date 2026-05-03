from __future__ import annotations

import hashlib
import math

from fastapi import FastAPI
from pydantic import BaseModel, Field


EMBEDDING_DIMENSION = 1024

app = FastAPI(title="Little Bear Model Gateway", version="0.1.0")


class EmbeddingRequest(BaseModel):
    model: str = "mock-embedding-v1"
    input_type: str = "query"
    input: list[str] = Field(default_factory=list)
    normalize: bool = True
    trace_id: str | None = None


class RerankDocument(BaseModel):
    id: str
    text: str | None = None


class RerankRequest(BaseModel):
    model: str = "mock-rerank-v1"
    query: str = ""
    documents: list[RerankDocument] = Field(default_factory=list)
    top_n: int | None = None
    trace_id: str | None = None


class ChatRequest(BaseModel):
    model: str = "mock-llm-v1"
    messages: list[dict[str, str]] = Field(default_factory=list)
    trace_id: str | None = None


def _route_hash(model: str) -> str:
    return hashlib.sha256(f"mock:{model}".encode("utf-8")).hexdigest()[:16]


def _vector(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [digest[idx % len(digest)] / 255.0 - 0.5 for idx in range(dimension)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [round(value / norm, 8) for value in values]


@app.get("/internal/v1/model-health")
async def model_health() -> dict[str, object]:
    return {
        "status": "ready",
        "checks": {
            "embedding": "ready",
            "rerank": "ready",
            "llm": "ready",
        },
    }


@app.get("/internal/v1/model-catalog")
async def model_catalog() -> dict[str, object]:
    return {
        "data": {
            "embedding": ["mock-embedding-v1"],
            "rerank": ["mock-rerank-v1"],
            "llm": ["mock-llm-v1"],
        }
    }


@app.post("/internal/v1/model-embeddings")
async def create_embeddings(request: EmbeddingRequest) -> dict[str, object]:
    return {
        "vectors": [_vector(item) for item in request.input],
        "model_route_hash": _route_hash(request.model),
        "degraded": False,
    }


@app.post("/internal/v1/model-rerankings")
async def create_rerankings(request: RerankRequest) -> dict[str, object]:
    top_n = request.top_n or len(request.documents)
    results = [
        {"id": document.id, "score": round(1.0 / (idx + 1), 6)}
        for idx, document in enumerate(request.documents[:top_n])
    ]
    return {
        "results": results,
        "model_route_hash": _route_hash(request.model),
        "degraded": False,
    }


@app.post("/internal/v1/model-chat-completions")
async def create_chat_completion(request: ChatRequest) -> dict[str, object]:
    return {
        "content": "这是本地 mock 回答。请以检索结果中的 citation 为准。",
        "model_route_hash": _route_hash(request.model),
        "token_usage": {
            "prompt_tokens": 16,
            "completion_tokens": 18,
            "total_tokens": 34,
        },
        "degraded": False,
    }
