"""健康检查路由。

live 只表示进程存活；ready 表示数据库、初始化状态、active_config 和关键依赖
都足以承载业务请求。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.db.health import check_database
from app.db.session import session_scope
from app.modules.setup.bootstrap_service import (
    EXPECTED_SCHEMA_REVISION,
    ServiceBootstrapStateService,
)
from app.modules.setup.service import SetupService

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
async def ready() -> dict[str, object]:
    database = check_database()
    setup_state = SetupService().load_state() if database.reachable else None
    initialized = bool(setup_state and setup_state.initialized)
    active_config = bool(setup_state and setup_state.active_config_present)
    service_bootstrap = False
    bootstrap_checks: list[dict[str, object]] = []
    schema_revision: str | None = None
    migration_ready = False

    if database.reachable:
        bootstrap_state_service = ServiceBootstrapStateService()
        with session_scope() as session:
            schema_revision = bootstrap_state_service.bootstrap_service.load_schema_revision(
                session
            )
            migration_ready = schema_revision == EXPECTED_SCHEMA_REVISION
            if initialized and setup_state and setup_state.active_config_version is not None:
                bootstrap_result = bootstrap_state_service.ensure_ready(
                    session,
                    active_config_version=setup_state.active_config_version,
                )
                service_bootstrap = bootstrap_result.ready
                bootstrap_checks = [check.to_dict() for check in bootstrap_result.checks]

    return {
        "status": (
            "ready"
            if initialized and active_config and service_bootstrap and migration_ready
            else "not_ready"
        ),
        "checks": {
            "database_configured": database.configured,
            "database_reachable": database.reachable,
            "migration_ready": migration_ready,
            "initialized": initialized,
            "active_config": active_config,
            "service_bootstrap": service_bootstrap,
        },
        "schema_migration_version": schema_revision,
        "bootstrap_checks": bootstrap_checks,
        "setup_status": setup_state.setup_status.value if setup_state else None,
        "error": database.error,
    }
