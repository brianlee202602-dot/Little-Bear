"""配置契约校验器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.shared.json_utils import json_schema_path
from app.shared.paths import CONFIG_SCHEMA_PATH

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover - 由调用方转成结构化错误。
    Draft202012Validator = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ConfigSchemaIssue:
    path: str
    message: str
    validator: str


class ConfigSchemaValidator:
    """统一加载 `config.schema.json` 并执行 setup/active_config schema 校验。"""

    def validate_setup_payload(self, payload: dict[str, Any]) -> list[ConfigSchemaIssue]:
        schema = self._load_schema()
        return self._validate(schema, payload)

    def validate_active_config(self, config: dict[str, Any]) -> list[ConfigSchemaIssue]:
        schema = self._load_schema()
        active_schema = {
            "$schema": schema.get("$schema"),
            "$defs": schema.get("$defs", {}),
            "$ref": "#/$defs/ActiveConfigV1",
        }
        return self._validate(active_schema, config)

    def _load_schema(self) -> dict[str, Any]:
        if Draft202012Validator is None:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_VALIDATOR_UNAVAILABLE",
                "jsonschema is required to validate config schema",
                retryable=False,
            )
        try:
            return json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_UNAVAILABLE",
                "config schema cannot be loaded",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except json.JSONDecodeError as exc:
            raise ConfigServiceError(
                "CONFIG_SCHEMA_MALFORMED",
                "config schema is not valid JSON",
                retryable=False,
                details={"message": str(exc)},
            ) from exc

    def _validate(self, schema: dict[str, Any], payload: dict[str, Any]) -> list[ConfigSchemaIssue]:
        errors = sorted(
            Draft202012Validator(schema).iter_errors(payload),
            key=lambda item: list(item.path),
        )
        return [
            ConfigSchemaIssue(
                path=json_schema_path(error),
                message=error.message,
                validator=str(error.validator),
            )
            for error in errors
        ]
