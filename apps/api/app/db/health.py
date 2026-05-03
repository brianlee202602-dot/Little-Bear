from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine
from app.shared.settings import get_settings


@dataclass(frozen=True)
class DatabaseHealth:
    configured: bool
    reachable: bool
    error: str | None = None


def check_database() -> DatabaseHealth:
    settings = get_settings()
    if not settings.database_url:
        return DatabaseHealth(configured=False, reachable=False, error="DATABASE_URL is not configured")

    try:
        with get_engine().connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        return DatabaseHealth(configured=True, reachable=False, error=exc.__class__.__name__)

    return DatabaseHealth(configured=True, reachable=True)
