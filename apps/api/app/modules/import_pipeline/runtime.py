"""Import Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.executors import HeadingParagraphChunker, MultiFormatDocumentParser
from app.modules.import_pipeline.service import ImportService
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.storage import MinioObjectStorage
from app.shared.json_utils import as_dict, json_int, json_str
from sqlalchemy.orm import Session


def build_import_service(session: Session) -> ImportService:
    """按 active_config 组装导入运行时。"""

    try:
        snapshot = ConfigService().load_active_config(session, validate_schema=False)
    except ConfigServiceError as exc:
        raise ImportServiceError(
            "IMPORT_RUNTIME_CONFIG_UNAVAILABLE",
            "active config cannot be loaded for import runtime",
            status_code=503,
            retryable=True,
            details={"source_error_code": exc.error_code, "source_details": exc.details},
        ) from exc
    return _build_import_service(session, snapshot.config)


def _build_import_service(session: Session, config: dict[str, Any]) -> ImportService:
    storage_config = as_dict(config.get("storage"))
    chunk_config = as_dict(config.get("chunk"))
    import_config = as_dict(config.get("import"))
    provider = json_str(storage_config, "provider")
    if provider != "minio":
        raise ImportServiceError(
            "IMPORT_RUNTIME_STORAGE_UNSUPPORTED",
            "active config storage provider is unsupported for import runtime",
            status_code=503,
            retryable=True,
            details={"provider": provider},
        )

    endpoint = json_str(storage_config, "minio_endpoint")
    bucket = json_str(storage_config, "bucket")
    access_key_ref = json_str(storage_config, "access_key_ref")
    secret_key_ref = json_str(storage_config, "secret_key_ref")
    missing = [
        path
        for path, value in (
            ("storage.minio_endpoint", endpoint),
            ("storage.bucket", bucket),
            ("storage.access_key_ref", access_key_ref),
            ("storage.secret_key_ref", secret_key_ref),
            ("import.max_file_mb", json_int(import_config, "max_file_mb")),
            ("import.allowed_file_types", _json_str_list(import_config.get("allowed_file_types"))),
        )
        if not value
    ]
    if missing:
        raise ImportServiceError(
            "IMPORT_RUNTIME_CONFIG_INCOMPLETE",
            "active config is incomplete for import runtime",
            status_code=503,
            retryable=True,
            details={"missing": missing},
        )

    max_chars = _chunk_chars(json_int(chunk_config, "default_size_tokens"), default=1600)
    overlap_chars = _chunk_chars(json_int(chunk_config, "overlap_tokens"), default=0)
    max_file_mb = json_int(import_config, "max_file_mb") or 1
    allowed_file_types = _json_str_list(import_config.get("allowed_file_types"))
    return ImportService(
        object_storage=MinioObjectStorage(
            endpoint=endpoint or "",
            bucket=bucket or "",
            access_key=_secret_value(session, access_key_ref),
            secret_key=_secret_value(session, secret_key_ref),
            region=json_str(storage_config, "region", default="us-east-1") or "us-east-1",
            object_key_prefix=json_str(storage_config, "object_key_prefix", default="") or "",
        ),
        parser=MultiFormatDocumentParser(),
        chunker=HeadingParagraphChunker(max_chars=max_chars, overlap_chars=overlap_chars),
        max_upload_bytes=max_file_mb * 1024 * 1024,
        allowed_file_types=tuple(allowed_file_types),
    )


def _secret_value(session: Session, secret_ref: str | None) -> str:
    if not secret_ref:
        raise ImportServiceError(
            "IMPORT_RUNTIME_SECRET_REF_MISSING",
            "object storage secret ref is missing",
            status_code=503,
            retryable=True,
        )
    try:
        return SecretStoreService().get_secret_value(session, secret_ref=secret_ref)
    except SecretStoreError as exc:
        raise ImportServiceError(
            "IMPORT_RUNTIME_SECRET_UNAVAILABLE",
            "object storage secret cannot be loaded",
            status_code=503,
            retryable=True,
            details={"secret_ref": secret_ref, "source_error_code": exc.error_code},
        ) from exc


def _chunk_chars(token_count: int | None, *, default: int) -> int:
    if token_count is None or token_count <= 0:
        return default
    return max(token_count * 4, 200)


def _json_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]
