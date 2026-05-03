from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import health, setup
from app.shared.logging import configure_logging
from app.shared.middleware import RequestContextMiddleware
from app.shared.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Little Bear API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(setup.router)
    return app


app = create_app()
