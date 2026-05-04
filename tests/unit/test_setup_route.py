from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.setup.initialize_service import (
    SetupInitializationError,
    SetupInitializationResult,
    SetupValidationResult,
)
from app.modules.setup.service import SetupState, SetupStatus


def test_setup_state_route_wraps_response_with_request_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.setup.SetupService.load_state",
        lambda _self: SetupState(
            initialized=False,
            setup_status=SetupStatus.SETUP_REQUIRED,
            active_config_version=None,
        ),
    )

    client = TestClient(create_app())
    response = client.get("/internal/v1/setup-state", headers={"x-request-id": "req_test_setup"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req_test_setup"
    assert payload["data"]["initialized"] is False
    assert payload["data"]["setup_status"] == "setup_required"
    assert payload["data"]["setup_required"] is True
    assert payload["data"]["active_config_present"] is False


def test_setup_config_validations_route_returns_validation_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.validate_payload",
        lambda _self, _payload: SetupValidationResult(valid=True, errors=[], warnings=[]),
    )

    client = TestClient(create_app())
    response = client.post(
        "/internal/v1/setup-config-validations",
        headers={"x-request-id": "req_validate"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req_validate"
    assert payload["data"]["valid"] is True
    assert payload["data"]["errors"] == []
    assert payload["data"]["warnings"] == []


def test_setup_initialization_route_requires_confirmation_header(monkeypatch) -> None:
    client = TestClient(create_app())
    response = client.put("/internal/v1/setup-initialization", json={"setup": {}, "config": {}})

    assert response.status_code == 428
    payload = response.json()
    assert payload["error_code"] == "SETUP_CONFIRMATION_REQUIRED"


def test_setup_initialization_route_returns_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.initialize",
        lambda _self, _session, _payload: SetupInitializationResult(
            initialized=True,
            active_config_version=1,
            enterprise_id="ent_1",
            admin_user_id="user_1",
        ),
    )

    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(create_app())
    response = client.put(
        "/internal/v1/setup-initialization",
        headers={"x-setup-confirm": "initialize", "x-request-id": "req_initialize"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req_initialize"
    assert payload["data"]["initialized"] is True
    assert payload["data"]["active_config_version"] == 1


def test_setup_initialization_route_returns_structured_error(monkeypatch) -> None:
    def fake_initialize(_self, _session, _payload):
        raise SetupInitializationError(
            "SETUP_CONFIG_INVALID",
            "payload is invalid",
            details={"errors": [{"path": "$.config", "message": "invalid"}]},
        )

    monkeypatch.setattr("app.api.routes.setup.SetupInitializationService.initialize", fake_initialize)

    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(create_app())
    response = client.put(
        "/internal/v1/setup-initialization",
        headers={"x-setup-confirm": "initialize"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "SETUP_CONFIG_INVALID"
    assert payload["details"]["errors"][0]["path"] == "$.config"
