"""Import Service runtime factory。"""

from __future__ import annotations

from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.executors import MultiFormatDocumentParser, StructureAwareChunker
from app.modules.import_pipeline.service import ImportService
from app.modules.storage import StorageRuntimeError, build_object_storage_from_config
from app.shared.json_utils import as_dict, json_int
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
    chunk_config = as_dict(config.get("chunk"))
    import_config = as_dict(config.get("import"))
    missing = [
        path
        for path, value in (
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

    try:
        object_storage = build_object_storage_from_config(session, config, required=True)
    except StorageRuntimeError as exc:
        raise ImportServiceError(
            _import_storage_error_code(exc.error_code),
            exc.message,
            status_code=exc.status_code,
            retryable=exc.retryable,
            details=exc.details,
        ) from exc
    if object_storage is None:
        raise ImportServiceError(
            "IMPORT_RUNTIME_STORAGE_UNAVAILABLE",
            "object storage is unavailable for import runtime",
            status_code=503,
            retryable=True,
        )

    max_chars = _chunk_chars(json_int(chunk_config, "default_size_tokens"), default=1600)
    overlap_chars = _chunk_chars(json_int(chunk_config, "overlap_tokens"), default=0)
    max_file_mb = json_int(import_config, "max_file_mb") or 1
    allowed_file_types = _json_str_list(import_config.get("allowed_file_types"))
    return ImportService(
        object_storage=object_storage,
        parser=MultiFormatDocumentParser(),
        chunker=StructureAwareChunker(max_chars=max_chars, overlap_chars=overlap_chars),
        max_upload_bytes=max_file_mb * 1024 * 1024,
        allowed_file_types=tuple(allowed_file_types),
    )


def _import_storage_error_code(error_code: str) -> str:
    mapping = {
        "STORAGE_RUNTIME_PROVIDER_UNSUPPORTED": "IMPORT_RUNTIME_STORAGE_UNSUPPORTED",
        "STORAGE_RUNTIME_CONFIG_INCOMPLETE": "IMPORT_RUNTIME_CONFIG_INCOMPLETE",
        "STORAGE_RUNTIME_SECRET_UNAVAILABLE": "IMPORT_RUNTIME_SECRET_UNAVAILABLE",
    }
    return mapping.get(error_code, "IMPORT_RUNTIME_STORAGE_UNAVAILABLE")


def _chunk_chars(token_count: int | None, *, default: int) -> int:
    if token_count is None or token_count <= 0:
        return default
    return max(token_count * 4, 200)


def _json_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]
