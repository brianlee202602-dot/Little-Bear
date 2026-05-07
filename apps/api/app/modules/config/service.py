"""Config Service 的 P0 读取侧实现。

初始化会把完整运行配置写入 system_configs.active_config。后续业务模块不应再读
Redis、MinIO、Qdrant、模型服务等环境变量，而是统一通过 ConfigService 读取
active_config，并在这里完成版本、scope、schema 和 hash 校验。
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.db.session import session_scope
from app.modules.config.cache import ConfigCache
from app.modules.config.errors import ConfigServiceError
from app.modules.config.schemas import (
    ActiveConfigSnapshot,
    ConfigItem,
    ConfigValidationResult,
    ConfigVersion,
)
from app.modules.config.validator import ConfigSchemaValidator
from app.shared.context import get_request_context
from app.shared.json_utils import json_bool, json_dumps, json_int, json_str, stable_json_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

GLOBAL_CONFIG_CACHE = ConfigCache()
CONFIG_METADATA_KEYS = {"schema_version", "config_version", "scope"}
HIGH_RISK_CONFIG_KEYS = {
    "auth",
    "audit",
    "model",
    "model_gateway",
    "retrieval",
    "secret_provider",
    "security",
    "storage",
    "vector_store",
}
MEDIUM_RISK_CONFIG_KEYS = {
    "cache",
    "chunking",
    "import",
    "keyword_search",
    "llm",
    "rate_limit",
    "redis",
}


class ConfigService:
    """读取、校验并发布当前生效运行配置。

    P0 的管理侧按 active_config 的顶层 section 保存草稿，真正发布时仍以完整
    active_config bundle 写入 `system_configs`，保证版本指针切换是单事务完成的。
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

    def list_config_items(self, session: Session) -> list[ConfigItem]:
        snapshot = self.load_active_config(session)
        return [
            ConfigItem(
                key=key,
                value_json=copy.deepcopy(value),
                scope_type=snapshot.scope_type,
                status="active",
                version=snapshot.version,
            )
            for key, value in sorted(snapshot.config.items())
            if _is_editable_config_section(key, value)
        ]

    def get_config_item(self, session: Session, key: str) -> ConfigItem:
        snapshot = self.load_active_config(session)
        value = snapshot.config.get(key)
        if not _is_editable_config_section(key, value):
            raise ConfigServiceError(
                "CONFIG_KEY_NOT_FOUND",
                "config key is not an editable active_config section",
                details={"key": key},
            )
        return ConfigItem(
            key=key,
            value_json=copy.deepcopy(value),
            scope_type=snapshot.scope_type,
            status="active",
            version=snapshot.version,
        )

    def save_config_draft(
        self,
        session: Session,
        *,
        key: str,
        value_json: dict[str, Any],
        actor_user_id: str | None,
    ) -> ConfigItem:
        snapshot = self.load_active_config(session)
        active_config = snapshot.config
        current_value = active_config.get(key)
        if not _is_editable_config_section(key, current_value):
            raise ConfigServiceError(
                "CONFIG_KEY_NOT_FOUND",
                "config key is not an editable active_config section",
                details={"key": key},
            )
        if current_value == value_json:
            return ConfigItem(
                key=key,
                value_json=copy.deepcopy(current_value),
                scope_type=snapshot.scope_type,
                status="active",
                version=snapshot.version,
            )

        existing_draft = self._load_draft_by_section(session, key, value_json)
        if existing_draft is not None:
            return existing_draft

        config = copy.deepcopy(active_config)
        version = self._next_config_version(session)
        config["config_version"] = version
        config[key] = copy.deepcopy(value_json)
        self.validate_active_config(config)

        config_hash = stable_json_hash(config)
        existing = self._load_config_by_hash(session, config_hash)
        if existing is not None:
            return ConfigItem(
                key=key,
                value_json=copy.deepcopy(existing["config"][key]),
                scope_type=str(existing["scope_type"]),
                status=str(existing["status"]),
                version=int(existing["version"]),
            )

        risk_level = _risk_level_for_key(key)
        config_version_id = uuid.uuid4()
        self._insert_config_version(
            session,
            config_version_id=config_version_id,
            version=version,
            status="draft",
            config_hash=config_hash,
            schema_version=int(config["schema_version"]),
            risk_level=risk_level,
            created_by=actor_user_id,
            validation_result={"valid": True, "stage": "schema"},
        )
        self._insert_system_config(
            session,
            config_version_id=config_version_id,
            version=version,
            status="draft",
            config=config,
            config_hash=config_hash,
        )
        self._insert_audit_log(
            session,
            event_name="config.draft_saved",
            action="save_draft",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level=risk_level,
            config_version=version,
            summary={"key": key, "config_hash": config_hash, "risk_level": risk_level},
        )
        return ConfigItem(
            key=key,
            value_json=copy.deepcopy(value_json),
            scope_type=snapshot.scope_type,
            status="draft",
            version=version,
        )

    def list_config_versions(self, session: Session, *, limit: int = 100) -> list[ConfigVersion]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT version, status, risk_level, created_by::text AS created_by
                    FROM config_versions
                    ORDER BY version DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).all()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config versions cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        return [_config_version_from_mapping(dict(row._mapping)) for row in rows]

    def get_config_version(self, session: Session, version: int) -> ConfigVersion:
        row = self._load_config_version_row(session, version)
        return _config_version_from_mapping(row)

    def validate_config_payload(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> ConfigValidationResult:
        validation, _bootstrap_result = self._validate_config_and_dependencies(
            session,
            config=config,
        )
        return validation

    def _validate_config_and_dependencies(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> tuple[ConfigValidationResult, Any | None]:
        errors = _schema_errors(config)
        if errors:
            return ConfigValidationResult(valid=False, errors=errors, warnings=[]), None

        bootstrap_result = self._run_dependency_validation(session, config=config)
        return (
            ConfigValidationResult(
                valid=not bootstrap_result["errors"],
                errors=bootstrap_result["errors"],
                warnings=bootstrap_result["warnings"],
            ),
            bootstrap_result["bootstrap_result"],
        )

    def publish_config_version(
        self,
        session: Session,
        *,
        version: int,
        actor_user_id: str | None,
    ) -> ConfigVersion:
        row = self._load_config_version_row(session, version, for_update=True)
        status = str(row["status"])
        if status == "active":
            return _config_version_from_mapping(row)
        if status not in {"draft", "validating"}:
            raise ConfigServiceError(
                "CONFIG_VERSION_NOT_PUBLISHABLE",
                "only draft or validating config versions can be published",
                details={"version": version, "status": status},
            )

        config_row = self._load_config_payload_row(session, version, for_update=True)
        config = _parse_config_value(config_row["value_json"], version=version)
        self._validate_metadata(
            {
                **row,
                "config_version": row["version"],
                "value_hash": config_row["value_hash"],
                "system_config_version": config_row["version"],
                "system_config_status": config_row["system_config_status"],
            },
            config,
            version,
        )

        self._mark_version_status(session, version, "validating")
        validation, bootstrap_result = self._validate_config_and_dependencies(
            session,
            config=config,
        )
        validation_payload = {
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }
        if not validation.valid:
            self._mark_version_status(
                session,
                version,
                "failed",
                validation_result=validation_payload,
            )
            self._insert_audit_log(
                session,
                event_name="config.publish_failed",
                action="publish",
                result="failure",
                actor_id=actor_user_id,
                resource_id=str(version),
                risk_level="critical",
                config_version=version,
                summary={
                    "config_hash": row["config_hash"],
                    "previous_active_version": self._load_active_config_version(session),
                    "active_pointer_unchanged": True,
                },
                error_code="CONFIG_DEPENDENCY_FAILED",
            )
            raise ConfigServiceError(
                "CONFIG_DEPENDENCY_FAILED",
                "config dependency validation failed",
                retryable=True,
                details=validation_payload,
            )

        previous_active_version = self._load_active_config_version(session)
        self._archive_active_config(session)
        self._mark_version_status(
            session,
            version,
            "active",
            validation_result=validation_payload,
            activated=True,
        )
        self._mark_system_config_status(session, version, "active")
        self._set_active_config_version(session, version, actor_user_id=actor_user_id)
        self._persist_bootstrap_state(session, bootstrap_result=bootstrap_result)
        self.invalidate_cache()
        self._insert_audit_log(
            session,
            event_name="config.published",
            action="publish",
            result="success",
            actor_id=actor_user_id,
            resource_id=str(version),
            risk_level="critical",
            config_version=version,
            summary={
                "config_hash": row["config_hash"],
                "previous_active_version": previous_active_version,
                "risk_level": row["risk_level"],
            },
        )
        return ConfigVersion(
            version=version,
            status="active",
            risk_level=str(row["risk_level"]),
            created_by=str(row["created_by"]) if row.get("created_by") else None,
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

    def _load_config_version_row(
        self,
        session: Session,
        version: int,
        *,
        for_update: bool = False,
    ) -> dict[str, Any]:
        lock_clause = "FOR UPDATE" if for_update else ""
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS config_version_id,
                        version,
                        scope_type,
                        scope_id,
                        status,
                        config_hash,
                        schema_version,
                        validation_result_json,
                        risk_level,
                        created_by::text AS created_by,
                        created_at,
                        activated_at
                    FROM config_versions
                    WHERE version = :version
                    {lock_clause}
                    """
                ),
                {"version": version},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config version cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__, "version": version},
            ) from exc
        if row is None:
            raise ConfigServiceError(
                "CONFIG_VERSION_NOT_FOUND",
                "config version does not exist",
                details={"version": version},
            )
        return dict(row._mapping)

    def _load_config_payload_row(
        self,
        session: Session,
        version: int,
        *,
        for_update: bool = False,
    ) -> dict[str, Any]:
        lock_clause = "FOR UPDATE" if for_update else ""
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        sc.version,
                        sc.status AS system_config_status,
                        sc.value_json,
                        sc.value_hash
                    FROM system_configs sc
                    JOIN config_versions cv ON cv.id = sc.config_version_id
                    WHERE sc.key = 'active_config'
                      AND sc.version = :version
                    LIMIT 1
                    {lock_clause}
                    """
                ),
                {"version": version},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_PAYLOAD_UNAVAILABLE",
                "config version payload cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__, "version": version},
            ) from exc
        if row is None:
            raise ConfigServiceError(
                "CONFIG_VERSION_PAYLOAD_MISSING",
                "config version payload is missing",
                retryable=True,
                details={"version": version},
            )
        return dict(row._mapping)

    def _load_config_by_hash(self, session: Session, config_hash: str) -> dict[str, Any] | None:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        cv.version,
                        cv.scope_type,
                        cv.status,
                        sc.value_json
                    FROM config_versions cv
                    JOIN system_configs sc ON sc.config_version_id = cv.id
                    WHERE cv.config_hash = :config_hash
                      AND sc.key = 'active_config'
                    LIMIT 1
                    """
                ),
                {"config_hash": config_hash},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config version cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        if row is None:
            return None
        data = dict(row._mapping)
        data["config"] = _parse_config_value(data["value_json"], version=int(data["version"]))
        return data

    def _load_draft_by_section(
        self,
        session: Session,
        key: str,
        value_json: dict[str, Any],
    ) -> ConfigItem | None:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        cv.version,
                        cv.scope_type,
                        cv.status,
                        sc.value_json
                    FROM config_versions cv
                    JOIN system_configs sc ON sc.config_version_id = cv.id
                    WHERE cv.status = 'draft'
                      AND sc.key = 'active_config'
                    ORDER BY cv.version DESC
                    LIMIT 20
                    """
                )
            ).all()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config draft cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc

        for row in rows:
            data = dict(row._mapping)
            version = int(data["version"])
            config = _parse_config_value(data["value_json"], version=version)
            if config.get(key) == value_json:
                return ConfigItem(
                    key=key,
                    value_json=copy.deepcopy(value_json),
                    scope_type=str(data["scope_type"]),
                    status=str(data["status"]),
                    version=version,
                )
        return None

    def _next_config_version(self, session: Session) -> int:
        row = session.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM config_versions")
        ).one()
        return int(row._mapping["version"])

    def _insert_config_version(
        self,
        session: Session,
        *,
        config_version_id: uuid.UUID,
        version: int,
        status: str,
        config_hash: str,
        schema_version: int,
        risk_level: str,
        created_by: str | None,
        validation_result: dict[str, object],
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO config_versions(
                    id, version, scope_type, scope_id, status, config_hash,
                    schema_version, validation_result_json, risk_level, created_by
                )
                VALUES (
                    :id, :version, 'global', 'global', :status, :config_hash,
                    :schema_version, CAST(:validation_result_json AS jsonb),
                    :risk_level, CAST(:created_by AS uuid)
                )
                """
            ),
            {
                "id": config_version_id,
                "version": version,
                "status": status,
                "config_hash": config_hash,
                "schema_version": schema_version,
                "validation_result_json": json_dumps(validation_result),
                "risk_level": risk_level,
                "created_by": created_by,
            },
        )

    def _insert_system_config(
        self,
        session: Session,
        *,
        config_version_id: uuid.UUID,
        version: int,
        status: str,
        config: dict[str, Any],
        config_hash: str,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO system_configs(
                    id, config_version_id, version, scope_type, scope_id, key,
                    value_json, value_hash, status
                )
                VALUES (
                    :id, :config_version_id, :version, 'global', 'global',
                    'active_config', CAST(:value_json AS jsonb), :value_hash, :status
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "config_version_id": config_version_id,
                "version": version,
                "value_json": json.dumps(config, ensure_ascii=False, sort_keys=True),
                "value_hash": config_hash,
                "status": status,
            },
        )

    def _mark_version_status(
        self,
        session: Session,
        version: int,
        status: str,
        *,
        validation_result: dict[str, object] | None = None,
        activated: bool = False,
    ) -> None:
        session.execute(
            text(
                """
                UPDATE config_versions
                SET status = :status,
                    validation_result_json = COALESCE(
                        CAST(:validation_result_json AS jsonb),
                        validation_result_json
                    ),
                    activated_at = CASE WHEN :activated THEN now() ELSE activated_at END
                WHERE version = :version
                """
            ),
            {
                "version": version,
                "status": status,
                "validation_result_json": (
                    json_dumps(validation_result) if validation_result is not None else None
                ),
                "activated": activated,
            },
        )

    def _mark_system_config_status(self, session: Session, version: int, status: str) -> None:
        session.execute(
            text(
                """
                UPDATE system_configs
                SET status = :status, updated_at = now()
                WHERE version = :version AND key = 'active_config'
                """
            ),
            {"version": version, "status": status},
        )

    def _archive_active_config(self, session: Session) -> None:
        session.execute(
            text(
                """
                UPDATE system_configs
                SET status = 'archived', updated_at = now()
                WHERE key = 'active_config' AND status = 'active'
                """
            )
        )
        session.execute(
            text("UPDATE config_versions SET status = 'archived' WHERE status = 'active'")
        )

    def _set_active_config_version(
        self,
        session: Session,
        version: int,
        *,
        actor_user_id: str | None,
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO system_state(key, value_json, updated_by)
                VALUES (
                    'active_config_version',
                    jsonb_build_object('version', CAST(:version AS integer)),
                    CAST(:actor_user_id AS uuid)
                )
                ON CONFLICT (key) DO UPDATE
                SET value_json = EXCLUDED.value_json,
                    updated_at = now(),
                    updated_by = EXCLUDED.updated_by
                """
            ),
            {"version": version, "actor_user_id": actor_user_id},
        )

    def _run_dependency_validation(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        from app.modules.setup.bootstrap_service import ServiceBootstrapService

        result = ServiceBootstrapService().bootstrap(session, config=config)
        errors: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []
        for check in result.checks:
            item: dict[str, object] = {
                "error_code": "CONFIG_DEPENDENCY_FAILED",
                "path": check.name,
                "message": check.message,
                "retryable": True,
                "status": check.status,
                "required": check.required,
            }
            if check.passed:
                continue
            if check.required:
                errors.append(item)
            else:
                warnings.append(item)
        return {"errors": errors, "warnings": warnings, "bootstrap_result": result}

    def _persist_bootstrap_state(self, session: Session, *, bootstrap_result: Any | None) -> None:
        from app.modules.setup.bootstrap_service import ServiceBootstrapService

        if bootstrap_result is not None:
            ServiceBootstrapService().persist_result(session, bootstrap_result)

    def _insert_audit_log(
        self,
        session: Session,
        *,
        event_name: str,
        action: str,
        result: str,
        actor_id: str | None,
        resource_id: str | None,
        risk_level: str,
        config_version: int | None,
        summary: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        request_context = get_request_context()
        session.execute(
            text(
                """
                INSERT INTO audit_logs(
                    id, request_id, trace_id, event_name, actor_type, actor_id,
                    resource_type, resource_id, action, result, risk_level,
                    config_version, summary_json, error_code
                )
                VALUES (
                    :id, :request_id, :trace_id, :event_name, 'user', :actor_id,
                    'config', :resource_id, :action, :result, :risk_level,
                    :config_version, CAST(:summary_json AS jsonb), :error_code
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "request_id": request_context.request_id if request_context else None,
                "trace_id": request_context.trace_id if request_context else None,
                "event_name": event_name,
                "actor_id": actor_id,
                "resource_id": resource_id,
                "action": action,
                "result": result,
                "risk_level": risk_level,
                "config_version": config_version,
                "summary_json": json.dumps(
                    {key: value for key, value in summary.items() if value is not None},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "error_code": error_code,
            },
        )

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


def _is_editable_config_section(key: str, value: Any) -> bool:
    return key not in CONFIG_METADATA_KEYS and isinstance(value, dict)


def _risk_level_for_key(key: str) -> str:
    if key in HIGH_RISK_CONFIG_KEYS:
        return "high"
    if key in MEDIUM_RISK_CONFIG_KEYS:
        return "medium"
    return "low"


def _schema_errors(config: dict[str, Any]) -> list[dict[str, object]]:
    issues = ConfigSchemaValidator().validate_active_config(config)
    return [
        {
            "error_code": "CONFIG_SCHEMA_INVALID",
            "path": issue.path,
            "message": issue.message,
            "validator": issue.validator,
            "retryable": False,
        }
        for issue in issues[:20]
    ]


def _config_version_from_mapping(row: dict[str, Any]) -> ConfigVersion:
    return ConfigVersion(
        version=int(row["version"]),
        status=str(row["status"]),
        risk_level=str(row["risk_level"]),
        created_by=str(row["created_by"]) if row.get("created_by") else None,
    )
