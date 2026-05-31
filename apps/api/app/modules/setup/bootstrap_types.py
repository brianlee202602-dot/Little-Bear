"""Service bootstrap data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

CheckStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class BootstrapCheck:
    name: str
    status: CheckStatus
    message: str
    required: bool = True
    latency_ms: int | None = None

    @property
    def passed(self) -> bool:
        return self.status == "passed" or (self.status == "skipped" and not self.required)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "required": self.required,
        }
        if self.latency_ms is not None:
            data["latency_ms"] = self.latency_ms
        return data


@dataclass(frozen=True)
class ServiceBootstrapResult:
    ready: bool
    config_version: int | None
    schema_revision: str | None
    checks: tuple[BootstrapCheck, ...]

    def to_state_value(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "mode": "p0_dependency_checks",
            "targets": [check.name for check in self.checks],
            "config_version": self.config_version,
            "schema_migration_version": self.schema_revision,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class ServiceBootstrapState:
    ready: bool
    config_version: int | None
    schema_revision: str | None
    checks: tuple[BootstrapCheck, ...]
    updated_at: datetime | None

    def fresh_for(self, active_config_version: int | None, *, ttl_seconds: float) -> bool:
        if not self.ready or self.config_version != active_config_version:
            return False
        if self.updated_at is None:
            return False
        return datetime.now(UTC) - self.updated_at <= timedelta(seconds=max(ttl_seconds, 0.0))

    def to_result(self) -> ServiceBootstrapResult:
        return ServiceBootstrapResult(
            ready=self.ready,
            config_version=self.config_version,
            schema_revision=self.schema_revision,
            checks=self.checks,
        )
