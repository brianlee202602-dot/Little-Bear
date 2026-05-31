"""Route registration for the FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import (
    admin,
    audit,
    auth,
    config,
    health,
    import_pipeline,
    knowledge,
    permissions,
    query,
    setup,
)


def include_api_routes(app: FastAPI) -> None:
    app.include_router(admin.router)
    app.include_router(audit.router)
    app.include_router(auth.router)
    app.include_router(config.router)
    app.include_router(health.router)
    app.include_router(import_pipeline.router)
    app.include_router(knowledge.router)
    app.include_router(permissions.router)
    app.include_router(query.router)
    app.include_router(setup.router)
