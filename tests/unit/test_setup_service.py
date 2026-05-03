from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.modules.setup.service import SetupService


def test_setup_service_returns_not_initialized_when_state_table_unavailable(monkeypatch) -> None:
    def fake_session_scope():
        raise OperationalError("select", {}, Exception("system_state is missing"))

    monkeypatch.setattr("app.modules.setup.service.session_scope", fake_session_scope)

    state = SetupService().load_state()

    assert state.initialized is False
    assert state.setup_status == "not_initialized"
    assert state.active_config_version is None


def test_setup_service_reads_system_state(monkeypatch) -> None:
    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
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
                    ]
                },
            )()

    monkeypatch.setattr("app.modules.setup.service.session_scope", lambda: _FakeSession())

    state = SetupService().load_state()

    assert state.initialized is True
    assert state.setup_status == "initialized"
    assert state.active_config_version == 1
