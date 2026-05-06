"""API 进程启动时的 setup 状态判定。

这里是“只读取数据库连接配置启动”的落地点：数据库不可达直接失败；数据库可达但未
初始化时签发 setup JWT；已初始化时执行 ServiceBootstrap，确认 active_config 能驱动
关键依赖。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.db.health import check_database
from app.db.session import session_scope
from app.modules.config.probe import ActiveConfigProbe
from app.modules.setup.bootstrap_service import ServiceBootstrapStateService
from app.modules.setup.service import SetupService, SetupStatus
from app.modules.setup.token_service import IssuedSetupToken, SetupTokenService
from app.shared.json_utils import json_dumps
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
            # 未初始化时自动签发一次性 setup JWT，便于本地首次安装直接进入初始化页。
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
            # 已初始化但 active_config 指针损坏时，允许进入受控恢复初始化。
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

            bootstrap_result = ServiceBootstrapStateService().ensure_ready(
                session,
                active_config_version=state.active_config_version,
                force_refresh=True,
            )
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
        result = ActiveConfigProbe().probe(session, active_config_version)
        if not result.present:
            return ActiveConfigIssue(
                reason=result.reason or result.status,
                message=result.message or "active_config is unavailable",
                recoverable=result.recoverable,
            )
        return None

    def _mark_recovery_required(self, session: Session, reason: str) -> None:
        """把系统切到恢复初始化模式，但不直接修改已有业务数据。"""

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
                {"key": key, "value_json": json_dumps(value_json)},
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
