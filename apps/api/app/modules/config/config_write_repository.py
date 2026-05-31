"""Config write repository."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.shared.json_utils import json_dumps
from sqlalchemy import text
from sqlalchemy.orm import Session


class ConfigWriteRepository:
    def insert_config_version(
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

    def insert_system_config(
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

    def update_config_version_payload(
        self,
        session: Session,
        *,
        version: int,
        status: str,
        config: dict[str, Any],
        config_hash: str,
        schema_version: int,
        risk_level: str,
        validation_result: dict[str, object],
    ) -> None:
        session.execute(
            text(
                """
                UPDATE config_versions
                SET status = :status,
                    config_hash = :config_hash,
                    schema_version = :schema_version,
                    validation_result_json = CAST(:validation_result_json AS jsonb),
                    risk_level = :risk_level,
                    updated_at = now()
                WHERE version = :version
                """
            ),
            {
                "version": version,
                "status": status,
                "config_hash": config_hash,
                "schema_version": schema_version,
                "validation_result_json": json_dumps(validation_result),
                "risk_level": risk_level,
            },
        )
        session.execute(
            text(
                """
                UPDATE system_configs
                SET value_json = CAST(:value_json AS jsonb),
                    value_hash = :value_hash,
                    status = :status,
                    updated_at = now()
                WHERE version = :version
                  AND key = 'active_config'
                """
            ),
            {
                "version": version,
                "status": status,
                "value_json": json.dumps(config, ensure_ascii=False, sort_keys=True),
                "value_hash": config_hash,
            },
        )

    def mark_version_status(
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
                    activated_at = CASE WHEN :activated THEN now() ELSE activated_at END,
                    updated_at = now()
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

    def mark_system_config_status(self, session: Session, version: int, status: str) -> None:
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

    def deactivate_active_config(self, session: Session) -> None:
        session.execute(
            text(
                """
                UPDATE system_configs
                SET status = 'inactive', updated_at = now()
                WHERE key = 'active_config' AND status = 'active'
                """
            )
        )
        session.execute(
            text(
                """
                UPDATE config_versions
                SET status = 'inactive', updated_at = now()
                WHERE status = 'active'
                """
            )
        )
