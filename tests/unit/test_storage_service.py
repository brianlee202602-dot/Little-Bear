from __future__ import annotations

from app.modules.storage.service import MinioObjectStorage


class _Response:
    status = 200

    def __init__(self, body: bytes = b"") -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_minio_object_storage_uses_prefix_and_signature(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        captured["body"] = request.data
        return _Response(b"ok")

    monkeypatch.setattr("app.modules.storage.service.urlopen", _urlopen)
    storage = MinioObjectStorage(
        endpoint="http://minio:9000",
        bucket="little-bear-rag",
        access_key="access",
        secret_key="secret",
        region="local",
        object_key_prefix="p0",
        timeout_seconds=3,
    )

    storage.put_object(object_key="uploads/doc 1.txt", content=b"hello", content_type="text/plain")

    assert captured["method"] == "PUT"
    assert captured["url"] == "http://minio:9000/little-bear-rag/p0/uploads/doc%201.txt"
    assert captured["body"] == b"hello"
    assert captured["timeout"] == 3
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert "Authorization" in headers
    assert "X-amz-content-sha256" in headers
