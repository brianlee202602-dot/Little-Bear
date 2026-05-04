from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.db.health import DatabaseHealth
from app.modules.setup.service import SetupState, SetupStatus
from app.modules.setup.startup_service import ActiveConfigIssue, SetupStartupService
from app.modules.setup.token_service import IssuedSetupToken


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSetupService:
    def __init__(self, state: SetupState) -> None:
        self.state = state

    def load_state(self) -> SetupState:
        return self.state


class _FakeTokenService:
    def issue(self, _session) -> IssuedSetupToken:
        return IssuedSetupToken(
            token="setup.jwt.token",
            setup_token_id="setup_token_1",
            jwt_jti="setup_jti_1",
            expires_at=datetime(2026, 5, 4, tzinfo=UTC),
            scopes=("setup:validate", "setup:initialize"),
        )


def test_setup_startup_fails_when_database_is_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.setup.startup_service.check_database",
        lambda: DatabaseHealth(configured=True, reachable=False, error="OperationalError"),
    )

    with pytest.raises(RuntimeError, match="database startup check failed"):
        SetupStartupService().run()


def test_setup_startup_issues_token_when_setup_is_required(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.setup.startup_service.check_database",
        lambda: DatabaseHealth(configured=True, reachable=True),
    )
    monkeypatch.setattr("app.modules.setup.startup_service.session_scope", lambda: _FakeSession())

    service = SetupStartupService(
        setup_service=_FakeSetupService(
            SetupState(
                initialized=False,
                setup_status=SetupStatus.SETUP_REQUIRED,
                active_config_version=None,
            )
        ),
        token_service=_FakeTokenService(),
    )

    result = service.run()

    assert result.mode == "setup_required"
    assert result.setup_token == "setup.jwt.token"
    assert result.setup_url.endswith("/admin/setup-initialization")


def test_setup_startup_enters_recovery_when_active_config_is_missing(monkeypatch) -> None:
    recovery_reasons: list[str] = []

    monkeypatch.setattr(
        "app.modules.setup.startup_service.check_database",
        lambda: DatabaseHealth(configured=True, reachable=True),
    )
    monkeypatch.setattr("app.modules.setup.startup_service.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.modules.setup.startup_service.SetupStartupService._detect_active_config_issue",
        lambda _self, _session, _version: ActiveConfigIssue(
            reason="active_config_missing",
            message="active_config row is missing",
            recoverable=True,
        ),
    )
    monkeypatch.setattr(
        "app.modules.setup.startup_service.SetupStartupService._mark_recovery_required",
        lambda _self, _session, reason: recovery_reasons.append(reason),
    )

    service = SetupStartupService(
        setup_service=_FakeSetupService(
            SetupState(
                initialized=True,
                setup_status=SetupStatus.INITIALIZED,
                active_config_version=1,
            )
        ),
        token_service=_FakeTokenService(),
    )

    result = service.run()

    assert result.mode == "recovery_required"
    assert result.setup_token == "setup.jwt.token"
    assert recovery_reasons == ["active_config_missing"]
