from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, setup
from app.modules.setup.startup_service import SetupStartupService
from app.shared.logging import configure_logging
from app.shared.middleware import RequestContextMiddleware
from app.shared.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if getattr(app.state, "run_startup_checks", True):
        SetupStartupService().run()
    yield


def create_app(*, run_startup_checks: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Little Bear API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )
    app.state.run_startup_checks = run_startup_checks
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(setup.router)
    return app


app = create_app()
