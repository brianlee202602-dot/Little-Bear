#!/usr/bin/env python3
"""用于 P0 开发的本地最小 Model Gateway mock。"""

from __future__ import annotations

import hashlib
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


EMBEDDING_DIMENSION = 1024


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("content-length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _route_hash(model: str) -> str:
    return hashlib.sha256(f"mock:{model}".encode("utf-8")).hexdigest()[:16]


def _vector(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for idx in range(dimension):
        byte = digest[idx % len(digest)]
        values.append((byte / 255.0) - 0.5)
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [round(value / norm, 8) for value in values]


class MockGatewayHandler(BaseHTTPRequestHandler):
    server_version = "LittleBearMockModelGateway/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/internal/v1/model-health":
            _write_json(
                self,
                200,
                {
                    "status": "ready",
                    "checks": {
                        "embedding": "ready",
                        "rerank": "ready",
                        "llm": "ready",
                    },
                },
            )
            return
        if self.path == "/internal/v1/model-catalog":
            _write_json(
                self,
                200,
                {
                    "data": {
                        "embedding": ["mock-embedding-v1"],
                        "rerank": ["mock-rerank-v1"],
                        "llm": ["mock-llm-v1"],
                    }
                },
            )
            return
        _write_json(self, 404, {"error_code": "NOT_FOUND", "message": "not found"})

    def do_POST(self) -> None:
        try:
            payload = _read_json(self)
            if self.path == "/internal/v1/model-embeddings":
                model = payload.get("model", "mock-embedding-v1")
                inputs = payload.get("input") or []
                _write_json(
                    self,
                    200,
                    {
                        "vectors": [_vector(str(item)) for item in inputs],
                        "model_route_hash": _route_hash(model),
                        "degraded": False,
                    },
                )
                return
            if self.path == "/internal/v1/model-rerankings":
                model = payload.get("model", "mock-rerank-v1")
                docs = payload.get("documents") or []
                top_n = payload.get("top_n") or len(docs)
                results = []
                for idx, doc in enumerate(docs[:top_n]):
                    results.append({"id": doc.get("id", str(idx)), "score": round(1.0 / (idx + 1), 6)})
                _write_json(
                    self,
                    200,
                    {
                        "results": results,
                        "model_route_hash": _route_hash(model),
                        "degraded": False,
                    },
                )
                return
            if self.path == "/internal/v1/model-chat-completions":
                model = payload.get("model", "mock-llm-v1")
                _write_json(
                    self,
                    200,
                    {
                        "content": "这是本地 mock 回答。请以检索结果中的 citation 为准。",
                        "model_route_hash": _route_hash(model),
                        "token_usage": {
                            "prompt_tokens": 16,
                            "completion_tokens": 18,
                            "total_tokens": 34,
                        },
                        "degraded": False,
                    },
                )
                return
            _write_json(self, 404, {"error_code": "NOT_FOUND", "message": "not found"})
        except Exception as exc:
            _write_json(
                self,
                500,
                {
                    "error_code": "MODEL_MOCK_FAILED",
                    "message": str(exc),
                    "retryable": True,
                },
            )


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), MockGatewayHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
