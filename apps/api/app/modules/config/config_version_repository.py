"""Config version repository."""

from __future__ import annotations

from typing import Any

from app.modules.config.errors import ConfigServiceError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class ConfigVersionRepository:
    def load_config_version_row(
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
                        updated_at,
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

    def load_config_payload_row(
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

    def load_config_version_payload_row(
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
                        cv.id::text AS config_version_id,
                        cv.version,
                        cv.scope_type,
                        cv.scope_id,
                        cv.status,
                        cv.config_hash,
                        cv.schema_version,
                        cv.validation_result_json,
                        cv.risk_level,
                        cv.created_by::text AS created_by,
                        cv.created_at,
                        cv.updated_at,
                        cv.activated_at,
                        sc.value_json
                    FROM config_versions cv
                    JOIN system_configs sc ON sc.config_version_id = cv.id
                    WHERE cv.version = :version
                      AND sc.key = 'active_config'
                    LIMIT 1
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

    def count_config_versions(self, session: Session) -> int:
        try:
            row = session.execute(text("SELECT COUNT(*) AS total FROM config_versions")).one()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config versions cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        return int(row._mapping["total"])

    def list_config_version_rows(
        self,
        session: Session,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        cv.version,
                        cv.status,
                        cv.risk_level,
                        cv.created_by::text AS created_by,
                        cv.created_at,
                        cv.updated_at,
                        cv.activated_at
                    FROM config_versions cv
                    ORDER BY version DESC
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            ).all()
        except SQLAlchemyError as exc:
            raise ConfigServiceError(
                "CONFIG_VERSION_UNAVAILABLE",
                "config versions cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        return [dict(row._mapping) for row in rows]

    def next_config_version(self, session: Session) -> int:
        row = session.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM config_versions")
        ).one()
        return int(row._mapping["version"])
