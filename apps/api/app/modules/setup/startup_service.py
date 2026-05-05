from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.db.health import check_database
from app.db.session import session_scope
from app.modules.setup.bootstrap_service import ServiceBootstrapService
from app.modules.setup.service import SetupService, SetupStatus
from app.modules.setup.token_service import IssuedSetupToken, SetupTokenService
from app.shared.settings import get_settings
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

StartupMode = Literal[
    "initialized",
    "setup_required",
    "recovery_required",
    "migration_required",
    "bootstrap_failed",
]


@dataclass(frozen=True)
class StartupSetupResult:
    mode: StartupMode
    setup_url: str
    setup_token: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ActiveConfigIssue:
    reason: str
    message: str
    recoverable: bool


class SetupStartupService:
    """进程启动时执行 setup 状态判定和本地 setup token 引导。"""

    def __init__(
        self,
        *,
        setup_service: SetupService | None = None,
        token_service: SetupTokenService | None = None,
    ) -> None:
        self.setup_service = setup_service or SetupService()
        self.token_service = token_service or SetupTokenService()

    def run(self) -> StartupSetupResult:
        settings = get_settings()
        setup_url = settings.admin_setup_url
        database = check_database()
        if not database.configured or not database.reachable:
            message = (
                "database startup check failed: "
                f"configured={database.configured}, reachable={database.reachable}, "
                f"error={database.error}"
            )
            logger.critical(message)
            raise RuntimeError(message)

        state = self.setup_service.load_state()
        if state.setup_status == SetupStatus.MIGRATION_REQUIRED:
            logger.error(
                "database is reachable but setup tables are missing or outdated; "
                "run Alembic migrations before setup. setup_url=%s",
                setup_url,
            )
            return StartupSetupResult(
                mode="migration_required",
                setup_url=setup_url,
                reason="setup_tables_missing_or_outdated",
            )

        if not state.initialized:
            with session_scope() as session:
                issued = self.token_service.issue(session)
            self._log_setup_token(issued, setup_url, reason="setup_required")
            return StartupSetupResult(
                mode="setup_required",
                setup_url=setup_url,
                setup_token=issued.token,
                reason="setup_required",
            )

        with session_scope() as session:
            active_config_issue = self._detect_active_config_issue(
                session,
                state.active_config_version,
            )
            if active_config_issue and active_config_issue.recoverable:
                self._mark_recovery_required(session, active_config_issue.reason)
                issued = self.token_service.issue(session)
                self._log_setup_token(issued, setup_url, reason=active_config_issue.reason)
                logger.error(
                    "active config is unavailable: %s. Visit %s and choose recovery setup.",
                    active_config_issue.message,
                    setup_url,
                )
                return StartupSetupResult(
                    mode="recovery_required",
                    setup_url=setup_url,
                    setup_token=issued.token,
                    reason=active_config_issue.reason,
                )
            if active_config_issue:
                logger.error(
                    "active config check failed and cannot be recovered through setup UI: %s",
                    active_config_issue.message,
                )
                return StartupSetupResult(
                    mode="migration_required",
                    setup_url=setup_url,
                    reason=active_config_issue.reason,
                )

            bootstrap_result = ServiceBootstrapService().bootstrap(
                session,
                active_config_version=state.active_config_version,
            )
            ServiceBootstrapService().persist_result(session, bootstrap_result)
            if not bootstrap_result.ready:
                failed_checks = [
                    check.name
                    for check in bootstrap_result.checks
                    if check.required and not check.passed
                ]
                logger.error(
                    "service bootstrap checks failed: active_config_version=%s failed_checks=%s",
                    state.active_config_version,
                    ",".join(failed_checks),
                )
                return StartupSetupResult(
                    mode="bootstrap_failed",
                    setup_url=setup_url,
                    reason="service_bootstrap_failed",
                )

        logger.info(
            "setup startup check passed: initialized=true active_config_version=%s",
            state.active_config_version,
        )
        return StartupSetupResult(mode="initialized", setup_url=setup_url)

    def _detect_active_config_issue(
        self, session: Session, active_config_version: int | None
    ) -> ActiveConfigIssue | None:
        table_status = session.execute(
            text(
                """
                SELECT
                    to_regclass('public.config_versions')::text AS config_versions_table,
                    to_regclass('public.system_configs')::text AS system_configs_table
                """
            )
        ).one()
        table_data = table_status._mapping
        if not table_data["config_versions_table"] or not table_data["system_configs_table"]:
            return ActiveConfigIssue(
                reason="config_table_missing",
                message="config_versions or system_configs table is missing",
                recoverable=False,
            )
        if active_config_version is None:
            return ActiveConfigIssue(
                reason="active_config_version_missing",
                message="system_state.active_config_version is empty",
                recoverable=True,
            )

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
        if row is None:
            return ActiveConfigIssue(
                reason="active_config_missing",
                message="active_config row is missing or inactive",
                recoverable=True,
            )
        return None

    def _mark_recovery_required(self, session: Session, reason: str) -> None:
        values = {
            "setup_status": {"status": SetupStatus.RECOVERY_REQUIRED.value},
            "recovery_setup_allowed": {"value": True},
            "recovery_reason": {"reason": reason},
        }
        for key, value_json in values.items():
            session.execute(
                text(
                    """
                    UPDATE system_state
                    SET value_json = CAST(:value_json AS jsonb), updated_at = now()
                    WHERE key = :key
                    """
                ),
                {"key": key, "value_json": _json_dumps(value_json)},
            )

    def _log_setup_token(
        self,
        issued: IssuedSetupToken,
        setup_url: str,
        *,
        reason: str,
    ) -> None:
        settings = get_settings()
        if not settings.setup_token_log_enabled:
            logger.warning(
                "setup token issued for %s but token logging is disabled. Visit %s",
                reason,
                setup_url,
            )
            return
        logger.warning("setup required: visit %s", setup_url)
        logger.warning("setup JWT token: %s", issued.token)
        logger.warning("setup token expires at: %s", issued.expires_at.isoformat())


def _json_dumps(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
