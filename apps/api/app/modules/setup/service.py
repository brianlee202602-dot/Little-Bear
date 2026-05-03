from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import session_scope

SETUP_STATE_KEYS = ("initialized", "setup_status", "active_config_version")


@dataclass(frozen=True)
class SetupState:
    initialized: bool
    setup_status: str
    active_config_version: int | None


class SetupService:
    """协调 setup-state、配置校验和首次初始化流程。"""

    async def get_state(self) -> dict[str, object]:
        state = self.load_state()
        return {
            "initialized": state.initialized,
            "setup_status": state.setup_status,
            "active_config_version": state.active_config_version,
            "setup_required": not state.initialized,
        }

    def load_state(self) -> SetupState:
        """从 system_state 读取当前初始化状态。

        约定：
        - migration 尚未执行或 system_state 尚未创建时，视为未初始化。
        - initialized=false 时，不尝试推导任何业务依赖状态。
        """
        try:
            with session_scope() as session:
                rows = session.execute(
                    text(
                        """
                        SELECT key, value_json
                        FROM system_state
                        WHERE key IN ('initialized', 'setup_status', 'active_config_version')
                        """
                    )
                ).all()
        except SQLAlchemyError:
            return SetupState(
                initialized=False,
                setup_status="not_initialized",
                active_config_version=None,
            )

        values = {row._mapping["key"]: row._mapping["value_json"] for row in rows}
        if not all(key in values for key in SETUP_STATE_KEYS):
            return SetupState(
                initialized=False,
                setup_status="not_initialized",
                active_config_version=None,
            )

        initialized = bool(values.get("initialized", {}).get("value", False))
        setup_status = str(values.get("setup_status", {}).get("status", "not_initialized"))
        active_config_version_raw = values.get("active_config_version", {}).get("version")

        active_config_version: int | None
        if isinstance(active_config_version_raw, int):
            active_config_version = active_config_version_raw
        else:
            active_config_version = None

        return SetupState(
            initialized=initialized,
            setup_status=setup_status,
            active_config_version=active_config_version,
        )
