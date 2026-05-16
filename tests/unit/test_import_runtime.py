from __future__ import annotations

from app.modules.import_pipeline.executors import MultiFormatDocumentParser
from app.modules.import_pipeline.runtime import _build_import_service


def test_build_import_service_uses_active_import_config(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.import_pipeline.runtime._secret_value",
        lambda *_args, **_kwargs: "secret",
    )

    service = _build_import_service(
        object(),
        {
            "storage": {
                "provider": "minio",
                "minio_endpoint": "http://minio:9000",
                "bucket": "little-bear-rag",
                "access_key_ref": "secret://rag/minio/access-key",
                "secret_key_ref": "secret://rag/minio/secret-key",
            },
            "chunk": {
                "default_size_tokens": 500,
                "overlap_tokens": 50,
            },
            "import": {
                "max_file_mb": 7,
                "allowed_file_types": ["pdf", "docx"],
            },
        },
    )

    assert service.max_upload_bytes == 7 * 1024 * 1024
    assert service.allowed_file_types == ("pdf", "docx")
    assert isinstance(service.parser, MultiFormatDocumentParser)
