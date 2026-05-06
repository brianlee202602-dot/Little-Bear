"""Config Service 的 P0 读取侧实现。

初始化会把完整运行配置写入 system_configs.active_config。后续业务模块不应再读
Redis、MinIO、Qdrant、模型服务等环境变量，而是统一通过 ConfigService 读取
active_config，并在这里完成版本、scope、schema 和 hash 校验。
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from typing import Any

from app.db.session import session_scope
from app.modules.config.cache import ConfigCache
from app.modules.config.errors import ConfigServiceError
from app.modules.config.schemas import ActiveConfigSnapshot
from app.modules.config.validator import ConfigSchemaValidator
from app.shared.json_utils import json_bool, json_int, json_str, stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

GLOBAL_CONFIG_CACHE = ConfigCache()


class ConfigService:
    """读取并校验当前生效运行配置。

    P0 只实现读取侧：active config 加载、schema/hash 校验和进程内缓存。
    草稿、审批、发布和回滚会在后续配置管理 API 中补齐。
    """

    def __init__(self, *, cache: ConfigCache | None = None) -> None:
        self.cache = cache or GLOBAL_CONFIG_CACHE

    def get_active_config(self, *, force_refresh: bool = False) -> ActiveConfigSnapshot:
        if not force_refresh:
            cached = self.cache.get()
            if cached is not None:
                return cached

        # cache miss 时只查一次数据库，成功加载后再写入进程内缓存。
        with session_scope() as session:
            snapshot = self.load_active_config(session)
        self.cache.set(snapshot)
        return snapshot

    def refresh_active_config(self) -> ActiveConfigSnapshot:
        return self.get_active_config(force_refresh=True)

    def invalidate_cache(self) -> None:
        self.cache.invalidate()

    def get_section(self, name: str, *, force_refresh: bool = False) -> dict[str, Any]:
        return self.get_active_config(force_refresh=force_refresh).section(name)

    def load_active_config(
        self,
        session: Session,
        *,
        active_config_version: int | None = None,
        validate_schema: bool = True,
    ) -> ActiveConfigSnapshot:
        version = active_config_version
        if version is None:
            version = self._load_active_config_version(session)
        else:
            self._assert_initialized(session)
        if version is None:
            raise ConfigServiceError(
                "CONFIG_ACTIVE_VERSION_MISSING",
                "system_state.active_config_version is missing",
                retryable=True,
            )

        row = self._load_active_config_row(session, version)
        config = _parse_config_value(row["value_json"], version=version)
        # 先校验数据库元数据，再做 JSON Schema；这样能更早发现指针错乱或数据篡改。
        self._validate_metadata(row, config, version)
        if validate_schema:
            self.validate_active_config(config)

        return ActiveConfigSnapshot(
            version=version,
            schema_version=int(row["schema_version"]),
            scope_type=str(row["scope_type"]),
            scope_id=str(row["scope_id"]),
            config_hash=str(row["config_hash"]),
            value_hash=str(row["value_hash"]),
            config_version_id=str(row["config_version_id"]),
            loaded_at=datetime.now(UTC),
            activated_at=_datetime_or_none(row.get("activated_at")),
            _config=copy.deepcopy(config),
        )

    def validate_active_config(self, config: dict[str, Any]) -> None:
        issues = ConfigSchemaValidator().validate_active_config(config)
        if issues:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_INVALID",
                "active config does not match ActiveConfigV1 schema",
                retryable=False,
                details={
                    "errors": [
                        {
                            "path": issue.path,
                            "message": issue.message,
                            "validator": issue.validator,
                        }
                        for issue in issues[:10]
                    ],
                    "error_count": len(issues),
                },
            )

    def _load_active_config_version(self, session: Session) -> int | None:
        values = self._load_system_state_values(session)
        self._assert_initialized_values(values)
        return json_int(values.get("active_config_version"), "version")

    def _assert_initialized(self, session: Session) -> None:
        values = self._load_system_state_values(session)
        self._assert_initialized_values(values)

    def _load_system_state_values(self, session: Session) -> dict[str, Any]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT key, value_json
                    FROM system_state
                    WHERE key IN ('initialized', 'setup_status', 'active_config_version')
                    """
                )
            ).all()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_STATE_UNAVAILABLE",
                "system_state cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc

        return {row._mapping["key"]: row._mapping["value_json"] for row in rows}

    def _assert_initialized_values(self, values: dict[str, Any]) -> None:
        initialized = json_bool(values.get("initialized"), "value", default=False)
        if not initialized:
            raise ConfigServiceError(
                "CONFIG_NOT_INITIALIZED",
                "system is not initialized",
                retryable=True,
                details={"setup_status": json_str(values.get("setup_status"), "status")},
            )

    def _load_active_config_row(self, session: Session, version: int) -> dict[str, Any]:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        cv.id::text AS config_version_id,
                        cv.version AS config_version,
                        cv.scope_type AS scope_type,
                        cv.scope_id AS scope_id,
                        cv.status AS config_status,
                        cv.config_hash AS config_hash,
                        cv.schema_version AS schema_version,
                        cv.activated_at AS activated_at,
                        sc.version AS system_config_version,
                        sc.status AS system_config_status,
                        sc.value_json AS value_json,
                        sc.value_hash AS value_hash
                    FROM system_configs sc
                    JOIN config_versions cv ON cv.id = sc.config_version_id
                    WHERE sc.key = 'active_config'
                      AND sc.version = :version
                      AND sc.status = 'active'
                      AND cv.status = 'active'
                    LIMIT 1
                    """
                ),
                {"version": version},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_ACTIVE_CONFIG_UNAVAILABLE",
                "active config cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__, "version": version},
            ) from exc

        if row is None:
            raise ConfigServiceError(
                "CONFIG_ACTIVE_MISSING",
                "active config row is missing or inactive",
                retryable=True,
                details={"version": version},
            )
        return dict(row._mapping)

    def _validate_metadata(
        self,
        row: dict[str, Any],
        config: dict[str, Any],
        version: int,
    ) -> None:
        config_version = config.get("config_version")
        if config_version != version or row["config_version"] != version:
            raise ConfigServiceError(
                "CONFIG_VERSION_MISMATCH",
                "active config version does not match database version",
                details={
                    "expected_version": version,
                    "config_version": config_version,
                    "database_version": row["config_version"],
                },
            )

        schema_version = config.get("schema_version")
        if schema_version != row["schema_version"]:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_VERSION_MISMATCH",
                "active config schema version does not match database metadata",
                details={
                    "config_schema_version": schema_version,
                    "database_schema_version": row["schema_version"],
                },
            )

        scope = config.get("scope")
        scope_mismatched = (
            not isinstance(scope, dict)
            or scope.get("type") != row["scope_type"]
            or scope.get("id") != row["scope_id"]
        )
        if scope_mismatched:
            raise ConfigServiceError(
                "CONFIG_SCOPE_MISMATCH",
                "active config scope does not match database metadata",
                details={
                    "config_scope": scope,
                    "database_scope": {"type": row["scope_type"], "id": row["scope_id"]},
                },
            )

        # 初始化写入时 value_hash/config_hash 都使用稳定 JSON hash；读取时重新计算兜底。
        config_hash = stable_json_hash(config)
        if config_hash != row["value_hash"] or config_hash != row["config_hash"]:
            raise ConfigServiceError(
                "CONFIG_HASH_MISMATCH",
                "active config hash does not match database metadata",
                retryable=True,
                details={
                    "computed_hash": config_hash,
                    "value_hash": row["value_hash"],
                    "config_hash": row["config_hash"],
                },
            )


def _parse_config_value(value: Any, *, version: int) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigServiceError(
                "CONFIG_ACTIVE_CONFIG_MALFORMED",
                "active config value_json is not valid JSON",
                retryable=False,
                details={"version": version, "message": str(exc)},
            ) from exc
        if isinstance(parsed, dict):
            return parsed

    raise ConfigServiceError(
        "CONFIG_ACTIVE_CONFIG_MALFORMED",
        "active config value_json must be a JSON object",
        retryable=False,
        details={"version": version, "value_type": type(value).__name__},
    )


def _datetime_or_none(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None
