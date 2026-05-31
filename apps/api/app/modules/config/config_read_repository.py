"""Config read repository."""

from __future__ import annotations

import copy
from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.modules.config.schemas import ConfigItem
from app.modules.config.utils import parse_config_value
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class ConfigReadRepository:
    def load_active_config_row(self, session: Session, version: int) -> dict[str, Any]:
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

    def load_config_by_hash(self, session: Session, config_hash: str) -> dict[str, Any] | None:
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
        data["config"] = parse_config_value(data["value_json"], version=int(data["version"]))
        return data

    def load_draft_by_section(
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
            config = parse_config_value(data["value_json"], version=version)
            if config.get(key) == value_json:
                return ConfigItem(
                    key=key,
                    value_json=copy.deepcopy(value_json),
                    scope_type=str(data["scope_type"]),
                    status=str(data["status"]),
                    version=version,
                )
        return None

    def list_draft_config_payloads(
        self,
        session: Session,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
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
                    WHERE cv.status IN ('draft', 'validating')
                      AND sc.key = 'active_config'
                    ORDER BY cv.version DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).all()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config drafts cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        return [dict(row._mapping) for row in rows]
