"""setup-state 读取服务。

该模块只负责把 system_state 解释成 SetupState，不执行初始化写入。API、启动检查
和 SetupGuard 都依赖它判断当前系统是否允许普通业务请求。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.db.session import session_scope
from app.modules.config.probe import ActiveConfigProbe
from app.shared.json_utils import json_bool, json_int, json_str
from sqlalchemy import text
from sqlalchemy.exc import NoSuchTableError, OperationalError, ProgrammingError, SQLAlchemyError

SETUP_STATE_KEYS = ("initialized", "setup_status", "active_config_version")


class SetupStatus(StrEnum):
    """初始化状态机中的有限状态。"""

    NOT_INITIALIZED = "not_initialized"
    SETUP_REQUIRED = "setup_required"
    VALIDATING_CONFIG = "validating_config"
    TESTING_DEPENDENCIES = "testing_dependencies"
    CREATING_ADMIN = "creating_admin"
    PUBLISHING_CONFIG = "publishing_config"
    INITIALIZED = "initialized"
    VALIDATION_FAILED = "validation_failed"
    DEPENDENCY_TEST_FAILED = "dependency_test_failed"
    INITIALIZATION_FAILED = "initialization_failed"
    RECOVERY_REQUIRED = "recovery_required"
    RECOVERY_VALIDATING_CONFIG = "recovery_validating_config"
    RECOVERY_PUBLISHING_CONFIG = "recovery_publishing_config"
    DATABASE_UNAVAILABLE = "database_unavailable"
    MIGRATION_REQUIRED = "migration_required"


@dataclass(frozen=True)
class SetupState:
    initialized: bool
    setup_status: SetupStatus
    active_config_version: int | None
    active_config_available: bool | None = None
    service_bootstrap_ready: bool = False
    recovery_setup_allowed: bool = False
    recovery_reason: str | None = None
    system_token_expires_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def setup_required(self) -> bool:
        # 数据库不可用或 migration 缺失不是 setup mode，必须先修复基础设施。
        return self.setup_status in {
            SetupStatus.NOT_INITIALIZED,
            SetupStatus.SETUP_REQUIRED,
            SetupStatus.VALIDATION_FAILED,
            SetupStatus.DEPENDENCY_TEST_FAILED,
            SetupStatus.INITIALIZATION_FAILED,
            SetupStatus.RECOVERY_REQUIRED,
            SetupStatus.RECOVERY_VALIDATING_CONFIG,
            SetupStatus.RECOVERY_PUBLISHING_CONFIG,
        }

    @property
    def active_config_present(self) -> bool:
        return self.active_config_version is not None and self.active_config_available is not False

    def to_response_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "initialized": self.initialized,
            "setup_status": self.setup_status.value,
            "active_config_version": self.active_config_version,
            "setup_required": self.setup_required,
            "active_config_present": self.active_config_present,
            "recovery_setup_allowed": self.recovery_setup_allowed,
            "recovery_reason": self.recovery_reason,
            "system_token_expires_at": self.system_token_expires_at,
        }
        if self.error_code:
            data["error_code"] = self.error_code
        if self.error_message:
            data["error_message"] = self.error_message
        return data


class SetupService:
    """协调 setup-state、配置校验和首次初始化流程。"""

    async def get_state(self) -> dict[str, object]:
        state = self.load_state()
        return {
            "initialized": state.initialized,
            "setup_status": state.setup_status.value,
            "active_config_version": state.active_config_version,
            "setup_required": state.setup_required,
        }

    def load_state(self) -> SetupState:
        """从 system_state 读取当前初始化状态。

        约定：
        - PostgreSQL 不可用时返回 database_unavailable，不进入 setup_required。
        - migration 尚未执行或 system_state 尚未创建时返回 migration_required。
        - initialized=false 时，不尝试推导任何业务依赖状态。
        """
        try:
            with session_scope() as session:
                rows = session.execute(
                    text(
                        """
                        SELECT key, value_json
                        FROM system_state
                        WHERE key IN (
                            'initialized',
                            'setup_status',
                            'active_config_version',
                            'service_bootstrap',
                            'recovery_setup_allowed',
                            'recovery_reason'
                        )
                        """
                    )
                ).all()
                values = {row._mapping["key"]: row._mapping["value_json"] for row in rows}
                active_config_available: bool | None = None
                if all(key in values for key in SETUP_STATE_KEYS):
                    active_config_version = json_int(values.get("active_config_version"), "version")
                    initialized_for_probe = json_bool(
                        values.get("initialized"), "value", default=False
                    )
                    if initialized_for_probe:
                        active_config_available = ActiveConfigProbe().probe(
                            session,
                            active_config_version,
                        ).to_setup_state_available()
        except ProgrammingError as exc:
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.MIGRATION_REQUIRED,
                active_config_version=None,
                error_code="SETUP_MIGRATION_REQUIRED",
                error_message=exc.__class__.__name__,
            )
        except OperationalError as exc:
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.DATABASE_UNAVAILABLE,
                active_config_version=None,
                error_code="SETUP_DATABASE_UNAVAILABLE",
                error_message=exc.__class__.__name__,
            )
        except RuntimeError as exc:
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.DATABASE_UNAVAILABLE,
                active_config_version=None,
                error_code="SETUP_DATABASE_UNAVAILABLE",
                error_message=str(exc),
            )
        except NoSuchTableError as exc:
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.MIGRATION_REQUIRED,
                active_config_version=None,
                error_code="SETUP_MIGRATION_REQUIRED",
                error_message=exc.__class__.__name__,
            )
        except ModuleNotFoundError as exc:
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.DATABASE_UNAVAILABLE,
                active_config_version=None,
                error_code="SETUP_DATABASE_UNAVAILABLE",
                error_message=str(exc),
            )
        except SQLAlchemyError as exc:
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.DATABASE_UNAVAILABLE,
                active_config_version=None,
                error_code="SETUP_DATABASE_UNAVAILABLE",
                error_message=exc.__class__.__name__,
            )

        if not all(key in values for key in SETUP_STATE_KEYS):
            return SetupState(
                initialized=False,
                setup_status=SetupStatus.SETUP_REQUIRED,
                active_config_version=None,
            )

        initialized = json_bool(values.get("initialized"), "value", default=False)
        raw_status = json_str(values.get("setup_status"), "status", default=None)
        setup_status = _normalize_status(raw_status, initialized=initialized)
        recovery_setup_allowed = json_bool(
            values.get("recovery_setup_allowed"), "value", default=False
        )
        recovery_reason = json_str(values.get("recovery_reason"), "reason", default=None)
        service_bootstrap_ready = json_bool(
            values.get("service_bootstrap"), "ready", default=False
        )

        return SetupState(
            initialized=initialized,
            setup_status=setup_status,
            active_config_version=active_config_version,
            active_config_available=active_config_available,
            service_bootstrap_ready=service_bootstrap_ready,
            recovery_setup_allowed=recovery_setup_allowed,
            recovery_reason=recovery_reason,
        )


def _normalize_status(raw_status: str | None, *, initialized: bool) -> SetupStatus:
    if raw_status:
        try:
            setup_status = SetupStatus(raw_status)
            if setup_status == SetupStatus.NOT_INITIALIZED and not initialized:
                return SetupStatus.SETUP_REQUIRED
            return setup_status
        except ValueError:
            pass
    return SetupStatus.INITIALIZED if initialized else SetupStatus.SETUP_REQUIRED
