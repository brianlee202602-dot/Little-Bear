"""Persistence for service bootstrap state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.setup.bootstrap_types import (
    BootstrapCheck,
    CheckStatus,
    ServiceBootstrapResult,
    ServiceBootstrapState,
)
from app.shared.json_utils import as_dict, json_bool, json_dumps, json_int, json_str
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class ServiceBootstrapStateRepository:
    """Read and write bootstrap state rows."""

    def load_schema_revision(self, session: Session) -> str | None:
        try:
            row = session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).one_or_none()
        except SQLAlchemyError:
            return None
        if row is None:
            return None
        value = row._mapping["version_num"]
        return value if isinstance(value, str) and value else None

    def load_state(self, session: Session) -> ServiceBootstrapState | None:
        try:
            row = session.execute(
                text(
                    """
                    SELECT value_json, updated_at
                    FROM system_state
                    WHERE key = 'service_bootstrap'
                    LIMIT 1
                    """
                )
            ).one_or_none()
        except SQLAlchemyError:
            return None
        if row is None:
            return None
        value_json = as_dict(row._mapping["value_json"])
        return ServiceBootstrapState(
            ready=json_bool(value_json, "ready", default=False),
            config_version=json_int(value_json, "config_version"),
            schema_revision=json_str(value_json, "schema_migration_version"),
            checks=_checks_from_state(value_json.get("checks")),
            updated_at=_datetime_or_none(row._mapping.get("updated_at")),
        )

    def persist_result(self, session: Session, result: ServiceBootstrapResult) -> None:
        session.execute(
            text(
                """
                INSERT INTO system_state(key, value_json)
                VALUES ('service_bootstrap', CAST(:value_json AS jsonb))
                ON CONFLICT (key) DO UPDATE
                SET value_json = EXCLUDED.value_json, updated_at = now()
                """
            ),
            {"value_json": json_dumps(result.to_state_value())},
        )


def _checks_from_state(value: object) -> tuple[BootstrapCheck, ...]:
    if not isinstance(value, list):
        return ()
    checks: list[BootstrapCheck] = []
    for item in value:
        data = as_dict(item)
        raw_status = data.get("status")
        status: CheckStatus = "failed"
        if raw_status == "passed":
            status = "passed"
        elif raw_status == "skipped":
            status = "skipped"
        checks.append(
            BootstrapCheck(
                name=json_str(data.get("name"), default="unknown") or "unknown",
                status=status,
                message=json_str(data.get("message"), default="") or "",
                required=data.get("required") is not False,
                latency_ms=json_int(data.get("latency_ms")),
            )
        )
    return tuple(checks)


def _datetime_or_none(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None
