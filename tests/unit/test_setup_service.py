from __future__ import annotations

from app.modules.setup.service import SetupService, SetupStatus
from sqlalchemy.exc import OperationalError, ProgrammingError


def test_setup_service_reports_database_unavailable(monkeypatch) -> None:
    def fake_session_scope():
        raise OperationalError("select", {}, Exception("database unavailable"))

    monkeypatch.setattr("app.modules.setup.service.session_scope", fake_session_scope)

    state = SetupService().load_state()

    assert state.initialized is False
    assert state.setup_status == SetupStatus.DATABASE_UNAVAILABLE
    assert state.active_config_version is None
    assert state.error_code == "SETUP_DATABASE_UNAVAILABLE"


def test_setup_service_reports_missing_database_driver(monkeypatch) -> None:
    def fake_session_scope():
        raise ModuleNotFoundError("No module named 'psycopg'")

    monkeypatch.setattr("app.modules.setup.service.session_scope", fake_session_scope)

    state = SetupService().load_state()

    assert state.initialized is False
    assert state.setup_status == SetupStatus.DATABASE_UNAVAILABLE
    assert state.active_config_version is None
    assert state.setup_required is False
    assert state.error_code == "SETUP_DATABASE_UNAVAILABLE"


def test_setup_service_reports_migration_required_when_state_table_missing(monkeypatch) -> None:
    def fake_session_scope():
        raise ProgrammingError("select", {}, Exception("system_state is missing"))

    monkeypatch.setattr("app.modules.setup.service.session_scope", fake_session_scope)

    state = SetupService().load_state()

    assert state.initialized is False
    assert state.setup_status == SetupStatus.MIGRATION_REQUIRED
    assert state.active_config_version is None
    assert state.setup_required is False
    assert state.error_code == "SETUP_MIGRATION_REQUIRED"


def test_setup_service_returns_setup_required_when_state_rows_are_incomplete(
    monkeypatch,
) -> None:
    class _FakeSession:
        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, *_args, **_kwargs):
            return type("_Result", (), {"all": lambda self: []})()

    monkeypatch.setattr("app.modules.setup.service.session_scope", lambda: _FakeSession())

    state = SetupService().load_state()

    assert state.initialized is False
    assert state.setup_status == SetupStatus.SETUP_REQUIRED
    assert state.active_config_version is None
    assert state.setup_required is True


def test_setup_service_normalizes_not_initialized_to_setup_required(monkeypatch) -> None:
    class _FakeSession:
        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, *_args, **_kwargs):
            return type(
                "_Result",
                (),
                {
                    "all": lambda self: [
                        type(
                            "Row",
                            (),
                            {"_mapping": {"key": "initialized", "value_json": {"value": False}}},
                        )(),
                        type(
                            "Row",
                            (),
                            {
                                "_mapping": {
                                    "key": "setup_status",
                                    "value_json": {"status": "not_initialized"},
                                }
                            },
                        )(),
                        type(
                            "Row",
                            (),
                            {
                                "_mapping": {
                                    "key": "active_config_version",
                                    "value_json": {"version": None},
                                }
                            },
                        )(),
                        type(
                            "Row",
                            (),
                            {
                                "_mapping": {
                                    "key": "service_bootstrap",
                                    "value_json": {"ready": False},
                                }
                            },
                        )(),
                    ]
                },
            )()

    monkeypatch.setattr("app.modules.setup.service.session_scope", lambda: _FakeSession())

    state = SetupService().load_state()

    assert state.initialized is False
    assert state.setup_status == SetupStatus.SETUP_REQUIRED
    assert state.setup_required is True


def test_setup_service_reads_system_state(monkeypatch) -> None:
    class _ProbeResult:
        def to_setup_state_available(self) -> bool:
            return True

    class _FakeSession:
        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, *_args, **_kwargs):
            return type(
                "_Result",
                (),
                {
                    "all": lambda self: [
                        type(
                            "Row",
                            (),
                            {"_mapping": {"key": "initialized", "value_json": {"value": True}}},
                        )(),
                        type(
                            "Row",
                            (),
                            {
                                "_mapping": {
                                    "key": "setup_status",
                                    "value_json": {"status": "initialized"},
                                }
                            },
                        )(),
                        type(
                            "Row",
                            (),
                            {
                                "_mapping": {
                                    "key": "active_config_version",
                                    "value_json": {"version": 1},
                                }
                            },
                        )(),
                        type(
                            "Row",
                            (),
                            {
                                "_mapping": {
                                    "key": "service_bootstrap",
                                    "value_json": {"ready": True},
                                }
                            },
                        )(),
                    ]
                },
            )()

    monkeypatch.setattr("app.modules.setup.service.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.modules.setup.service.ActiveConfigProbe.probe",
        lambda _self, _session, _version: _ProbeResult(),
    )

    state = SetupService().load_state()

    assert state.initialized is True
    assert state.setup_status == SetupStatus.INITIALIZED
    assert state.active_config_version == 1
    assert state.active_config_present is True
    assert state.service_bootstrap_ready is True
    assert state.setup_required is False
