"""Upload file validation helpers for import workflows."""

from __future__ import annotations

from app.modules.import_pipeline.errors import ImportServiceError

DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
DEFAULT_ALLOWED_FILE_TYPES = ("txt", "md", "pdf", "docx")
CONTENT_TYPE_TO_FILE_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
}
EXTENSION_TO_FILE_TYPE = {
    "pdf": "pdf",
    "docx": "docx",
    "txt": "txt",
    "text": "txt",
    "md": "md",
    "markdown": "md",
}


def validate_upload_file(
    *,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    file_index: int,
    max_upload_bytes: int,
    allowed_file_types: tuple[str, ...],
) -> str:
    """Validate an uploaded file against import runtime policy."""

    normalized_allowed = normalize_allowed_file_types(allowed_file_types)
    file_type = infer_file_type(filename=filename, content_type=content_type)
    if not file_type or file_type not in normalized_allowed:
        raise ImportServiceError(
            "IMPORT_FILE_TYPE_UNSUPPORTED",
            "uploaded file type is not allowed by active import config",
            status_code=415,
            retryable=False,
            details={
                "file_index": file_index,
                "filename": filename,
                "content_type": content_type,
                "file_type": file_type,
                "allowed_file_types": list(normalized_allowed),
            },
        )
    if size_bytes > max_upload_bytes:
        raise ImportServiceError(
            "IMPORT_FILE_TOO_LARGE",
            "uploaded file is too large for active import config",
            status_code=413,
            retryable=False,
            details={
                "file_index": file_index,
                "filename": filename,
                "max_bytes": max_upload_bytes,
                "size_bytes": size_bytes,
            },
        )
    return file_type


def infer_file_type(*, filename: str, content_type: str | None) -> str | None:
    extension = extension_from_name(filename)
    if extension and extension in EXTENSION_TO_FILE_TYPE:
        return EXTENSION_TO_FILE_TYPE[extension]
    if extension:
        return None
    if content_type:
        normalized_content_type = content_type.lower().split(";")[0].strip()
        return CONTENT_TYPE_TO_FILE_TYPE.get(normalized_content_type)
    return None


def extension_from_name(name: str | None) -> str | None:
    if not name or "." not in name:
        return None
    extension = name.rsplit(".", 1)[1].strip().lower()
    return extension or None


def normalize_allowed_file_types(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        item = value.strip().lower().lstrip(".")
        file_type = EXTENSION_TO_FILE_TYPE.get(item, item)
        if file_type and file_type not in normalized:
            normalized.append(file_type)
    return tuple(normalized)

