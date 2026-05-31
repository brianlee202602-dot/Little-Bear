"""Config service shared helpers."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any

from app.modules.audit import AuditWriter
from app.modules.config.constants import (
    CONFIG_METADATA_KEYS,
    HIGH_RISK_CONFIG_KEYS,
    MEDIUM_RISK_CONFIG_KEYS,
)
from app.modules.config.errors import ConfigServiceError
from app.modules.config.schemas import ConfigVersion
from app.modules.config.validator import ConfigSchemaValidator


def parse_config_value(value: Any, *, version: int) -> dict[str, Any]:
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


def datetime_or_none(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def is_editable_config_section(key: str, value: Any) -> bool:
    return key not in CONFIG_METADATA_KEYS and isinstance(value, dict)


def normalized_config_for_version(config: dict[str, Any], *, version: int) -> dict[str, Any]:
    normalized = copy.deepcopy(config)
    normalized["schema_version"] = int(normalized.get("schema_version") or 1)
    normalized["config_version"] = version
    scope = normalized.get("scope")
    if not isinstance(scope, dict):
        normalized["scope"] = {"type": "global", "id": "global"}
    return normalized


def changed_config_keys(base: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    keys = sorted((set(base) | set(candidate)) - CONFIG_METADATA_KEYS)
    return [key for key in keys if base.get(key) != candidate.get(key)]


def risk_level_for_config_change(base: dict[str, Any], candidate: dict[str, Any]) -> str:
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    current = "low"
    for key in changed_config_keys(base, candidate):
        risk = risk_level_for_key(key)
        if risk_order[risk] > risk_order[current]:
            current = risk
    return current


def status_after_config_update(status: str) -> str:
    if status in {"active", "inactive"}:
        return status
    return "draft"


def risk_level_for_key(key: str) -> str:
    if key in HIGH_RISK_CONFIG_KEYS:
        return "high"
    if key in MEDIUM_RISK_CONFIG_KEYS:
        return "medium"
    return "low"


def schema_errors(config: dict[str, Any]) -> list[dict[str, object]]:
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


def config_version_from_mapping(row: dict[str, Any]) -> ConfigVersion:
    raw_config = row.get("value_json")
    config = (
        parse_config_value(raw_config, version=int(row["version"]))
        if raw_config is not None
        else None
    )
    return ConfigVersion(
        version=int(row["version"]),
        status=str(row["status"]),
        risk_level=str(row["risk_level"]),
        created_by=str(row["created_by"]) if row.get("created_by") else None,
        config=config,
        created_at=datetime_or_none(row.get("created_at")),
        updated_at=datetime_or_none(row.get("updated_at")),
        activated_at=datetime_or_none(row.get("activated_at")),
    )


def write_config_audit(
    session,
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
    AuditWriter().write(
        session,
        event_name=event_name,
        actor_type="user",
        actor_id=actor_id,
        resource_type="config",
        resource_id=resource_id,
        action=action,
        result=result,
        risk_level=risk_level,
        config_version=config_version,
        summary=summary,
        error_code=error_code,
        filter_summary_none=True,
    )
