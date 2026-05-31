"""对象存储运行时工厂。"""

from __future__ import annotations

from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.storage.service import MinioObjectStorage, ObjectStorage
from app.shared.errors import ServiceError
from app.shared.json_utils import as_dict, json_str
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class StorageRuntimeError(ServiceError):
    """对象存储运行时配置或密钥不可用。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 503,
        retryable: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code,
            message,
            status_code=status_code,
            retryable=retryable,
            details=details,
        )


def build_object_storage(session: Session, *, required: bool = False) -> ObjectStorage | None:
    """按 active_config 构建对象存储。

    查询预览等非关键路径可使用 ``required=False``，配置不可用时返回 ``None``；
    导入链路必须使用 ``required=True``，避免文件已入库但对象未写入的半成功状态。
    """

    try:
        snapshot = ConfigService().load_active_config(session, validate_schema=False)
    except (ConfigServiceError, SQLAlchemyError, AttributeError, TypeError) as exc:
        if not required:
            return None
        raise StorageRuntimeError(
            "STORAGE_RUNTIME_CONFIG_UNAVAILABLE",
            "active config cannot be loaded for object storage runtime",
            details=_source_error_details(exc),
        ) from exc
    return build_object_storage_from_config(session, snapshot.config, required=required)


def build_object_storage_from_config(
    session: Session,
    config: dict[str, Any],
    *,
    required: bool = False,
) -> ObjectStorage | None:
    """按配置快照构建对象存储。"""

    storage_config = as_dict(config.get("storage"))
    provider = json_str(storage_config, "provider")
    if provider != "minio":
        if not required:
            return None
        raise StorageRuntimeError(
            "STORAGE_RUNTIME_PROVIDER_UNSUPPORTED",
            "object storage provider is unsupported",
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
        )
        if not value
    ]
    if missing:
        if not required:
            return None
        raise StorageRuntimeError(
            "STORAGE_RUNTIME_CONFIG_INCOMPLETE",
            "object storage config is incomplete",
            details={"missing": missing},
        )

    try:
        secret_store = SecretStoreService()
        access_key = secret_store.get_secret_value(session, secret_ref=access_key_ref or "")
        secret_key = secret_store.get_secret_value(session, secret_ref=secret_key_ref or "")
    except (SecretStoreError, SQLAlchemyError, AttributeError, TypeError) as exc:
        if not required:
            return None
        raise StorageRuntimeError(
            "STORAGE_RUNTIME_SECRET_UNAVAILABLE",
            "object storage secret cannot be loaded",
            details={
                **_source_error_details(exc),
                "access_key_ref": access_key_ref,
                "secret_key_ref": secret_key_ref,
            },
        ) from exc

    return MinioObjectStorage(
        endpoint=endpoint or "",
        bucket=bucket or "",
        access_key=access_key,
        secret_key=secret_key,
        region=json_str(storage_config, "region", default="us-east-1") or "us-east-1",
        object_key_prefix=json_str(storage_config, "object_key_prefix", default="") or "",
    )


def _source_error_details(exc: BaseException) -> dict[str, Any]:
    details: dict[str, Any] = {"error_type": exc.__class__.__name__}
    error_code = getattr(exc, "error_code", None)
    if isinstance(error_code, str) and error_code:
        details["source_error_code"] = error_code
    source_details = getattr(exc, "details", None)
    if isinstance(source_details, dict):
        details["source_details"] = source_details
    return details
