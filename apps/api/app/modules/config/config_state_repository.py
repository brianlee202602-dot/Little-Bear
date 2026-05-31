"""Config system_state repository."""

from __future__ import annotations

from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.shared.json_utils import json_bool, json_int, json_str
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class ConfigStateRepository:
    def load_active_config_version(self, session: Session) -> int | None:
        values = self._load_system_state_values(session)
        self._assert_initialized_values(values)
        return json_int(values.get("active_config_version"), "version")

    def assert_initialized(self, session: Session) -> None:
        values = self._load_system_state_values(session)
        self._assert_initialized_values(values)

    def set_active_config_version(
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
