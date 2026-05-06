"""JSON 配置值的轻量工具函数。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def stable_json_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def json_bool(value_json: Any, key: str, *, default: bool) -> bool:
    if isinstance(value_json, dict) and isinstance(value_json.get(key), bool):
        return value_json[key]
    return default


def json_int(value_json: Any, key: str | None = None) -> int | None:
    if key is None:
        return value_json if isinstance(value_json, int) else None
    if isinstance(value_json, dict) and isinstance(value_json.get(key), int):
        return value_json[key]
    return None


def json_str(value_json: Any, key: str | None = None, *, default: str | None = None) -> str | None:
    value = value_json.get(key) if key is not None and isinstance(value_json, dict) else value_json
    if isinstance(value, str) and value:
        return value
    return default


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_schema_path(error: Any) -> str:
    parts = list(error.path)
    if not parts:
        return "$"
    return "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts)
