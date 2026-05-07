"""Config Service 对外返回的数据结构。"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.modules.config.errors import ConfigServiceError


@dataclass(frozen=True)
class ActiveConfigSnapshot:
    """当前生效配置的不可变快照。

    _config 不直接暴露可变引用，业务模块只能通过 config/section 拿深拷贝，避免
    某个模块误改进程内配置后影响其它请求。
    """

    version: int
    schema_version: int
    scope_type: str
    scope_id: str
    config_hash: str
    value_hash: str
    config_version_id: str
    loaded_at: datetime
    activated_at: datetime | None = None
    _config: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def config(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)

    def section(self, name: str) -> dict[str, Any]:
        if name not in self._config:
            raise ConfigServiceError(
                "CONFIG_SECTION_MISSING",
                "active config section is missing",
                details={"section": name, "config_version": self.version},
            )
        value = self._config[name]
        if not isinstance(value, dict):
            raise ConfigServiceError(
                "CONFIG_SECTION_INVALID",
                "active config section must be a JSON object",
                details={
                    "section": name,
                    "config_version": self.version,
                    "value_type": type(value).__name__,
                },
            )
        return copy.deepcopy(value)

    def summary(self) -> dict[str, object]:
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "config_hash": self.config_hash,
            "value_hash": self.value_hash,
            "config_version_id": self.config_version_id,
            "loaded_at": self.loaded_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
        }


@dataclass(frozen=True)
class ConfigItem:
    """管理后台看到的一个可编辑配置分组。"""

    key: str
    value_json: dict[str, Any]
    scope_type: str
    status: str
    version: int


@dataclass(frozen=True)
class ConfigVersion:
    """配置版本元数据，P0 不在列表响应里直接返回完整配置正文。"""

    version: int
    status: str
    risk_level: str
    created_by: str | None = None


@dataclass(frozen=True)
class ConfigValidationResult:
    """配置校验结果，兼容 setup 校验响应结构。"""

    valid: bool
    errors: list[dict[str, object]] = field(default_factory=list)
    warnings: list[dict[str, object]] = field(default_factory=list)
