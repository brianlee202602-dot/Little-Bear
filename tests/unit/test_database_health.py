from __future__ import annotations

from app.db.health import check_database
from app.shared.settings import get_settings


def test_database_health_reports_missing_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    health = check_database()

    assert health.configured is False
    assert health.reachable is False
    assert health.error == "DATABASE_URL is not configured"


def test_database_health_reports_driver_import_error(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
    get_settings.cache_clear()

    def fake_get_engine():
        raise ModuleNotFoundError("No module named 'psycopg'")

    monkeypatch.setattr("app.db.health.get_engine", fake_get_engine)

    health = check_database()

    assert health.configured is True
    assert health.reachable is False
    assert health.error == "ModuleNotFoundError"
