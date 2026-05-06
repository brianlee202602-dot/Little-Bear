"""active_config 指针和记录可用性的统一探测。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

ActiveConfigProbeStatus = Literal[
    "present",
    "version_missing",
    "table_missing",
    "missing",
    "unavailable",
]


@dataclass(frozen=True)
class ActiveConfigProbeResult:
    status: ActiveConfigProbeStatus
    version: int | None
    reason: str | None = None
    message: str | None = None
    recoverable: bool = False

    @property
    def present(self) -> bool:
        return self.status == "present"

    def to_setup_state_available(self) -> bool | None:
        if self.status == "version_missing":
            return None
        return self.present


class ActiveConfigProbe:
    """只做轻量存在性检查，不加载完整 active_config bundle。"""

    def probe(self, session: Session, active_config_version: int | None) -> ActiveConfigProbeResult:
        table_result = self._check_tables(session, active_config_version)
        if table_result is not None:
            return table_result
        if active_config_version is None:
            return ActiveConfigProbeResult(
                status="version_missing",
                version=None,
                reason="active_config_version_missing",
                message="system_state.active_config_version is empty",
                recoverable=True,
            )

        try:
            row = session.execute(
                text(
                    """
                    SELECT 1
                    FROM system_configs sc
                    JOIN config_versions cv ON cv.id = sc.config_version_id
                    WHERE sc.key = 'active_config'
                      AND sc.version = :version
                      AND sc.status = 'active'
                      AND cv.status = 'active'
                    LIMIT 1
                    """
                ),
                {"version": active_config_version},
            ).one_or_none()
        except SQLAlchemyError as exc:
            return ActiveConfigProbeResult(
                status="unavailable",
                version=active_config_version,
                reason="active_config_unavailable",
                message=f"active_config check failed: {exc.__class__.__name__}",
                recoverable=False,
            )

        if row is None:
            return ActiveConfigProbeResult(
                status="missing",
                version=active_config_version,
                reason="active_config_missing",
                message="active_config row is missing or inactive",
                recoverable=True,
            )
        return ActiveConfigProbeResult(status="present", version=active_config_version)

    def _check_tables(
        self,
        session: Session,
        active_config_version: int | None,
    ) -> ActiveConfigProbeResult | None:
        try:
            table_status = session.execute(
                text(
                    """
                    SELECT
                        to_regclass('public.config_versions')::text AS config_versions_table,
                        to_regclass('public.system_configs')::text AS system_configs_table
                    """
                )
            ).one()
        except SQLAlchemyError as exc:
            return ActiveConfigProbeResult(
                status="unavailable",
                version=active_config_version,
                reason="active_config_table_check_failed",
                message=f"active_config table check failed: {exc.__class__.__name__}",
                recoverable=False,
            )

        table_data = table_status._mapping
        if not table_data["config_versions_table"] or not table_data["system_configs_table"]:
            return ActiveConfigProbeResult(
                status="table_missing",
                version=active_config_version,
                reason="config_table_missing",
                message="config_versions or system_configs table is missing",
                recoverable=False,
            )
        return None
