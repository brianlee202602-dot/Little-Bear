from __future__ import annotations

from fastapi import APIRouter

from app.db.health import check_database
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
    active_config = bool(setup_state and setup_state.active_config_version is not None)
    service_bootstrap = bool(setup_state and setup_state.service_bootstrap_ready)

    return {
        "status": "ready" if initialized and active_config and service_bootstrap else "not_ready",
        "checks": {
            "database_configured": database.configured,
            "database_reachable": database.reachable,
            "initialized": initialized,
            "active_config": active_config,
            "service_bootstrap": service_bootstrap,
        },
        "setup_status": setup_state.setup_status.value if setup_state else None,
        "error": database.error,
    }
