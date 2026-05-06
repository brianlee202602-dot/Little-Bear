from __future__ import annotations

from app.main import create_app
from app.modules.setup.initialize_service import (
    SetupInitializationError,
    SetupInitializationResult,
    SetupValidationResult,
)
from app.modules.setup.service import SetupState, SetupStatus
from app.modules.setup.token_service import SetupTokenContext
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


def _fake_setup_token() -> SetupTokenContext:
    return SetupTokenContext(
        setup_token_id="setup_token_1",
        jwt_jti="setup_jti_1",
        token_hash="hash_1",
        scopes=("setup:validate", "setup:initialize"),
    )


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _create_test_app():
    return create_app(run_startup_checks=False)


def test_setup_state_route_wraps_response_with_request_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.setup.SetupService.load_state",
        lambda _self: SetupState(
            initialized=False,
            setup_status=SetupStatus.SETUP_REQUIRED,
            active_config_version=None,
        ),
    )

    client = TestClient(_create_test_app())
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
    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.ensure_setup_open",
        lambda _self, _session: None,
    )
    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.audit_validation",
        lambda _self, _session, _validation, _payload, *, setup_token=None: None,
    )
    monkeypatch.setattr(
        "app.api.routes.setup.SetupTokenService.validate",
        lambda _self, _session, _token, *, required_scope: _fake_setup_token(),
    )
    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/setup-config-validations",
        headers={"x-request-id": "req_validate", "authorization": "Bearer setup_test"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req_validate"
    assert payload["data"]["valid"] is True
    assert payload["data"]["errors"] == []
    assert payload["data"]["warnings"] == []


def test_setup_guard_blocks_business_routes_before_initialization(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.shared.middleware.SetupService.load_state",
        lambda _self: SetupState(
            initialized=False,
            setup_status=SetupStatus.SETUP_REQUIRED,
            active_config_version=None,
        ),
    )

    client = TestClient(_create_test_app())
    response = client.get("/internal/v1/business-placeholder")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error_code"] == "SETUP_REQUIRED"
    assert payload["stage"] == "setup_guard"


def test_setup_config_validations_route_requires_setup_token(monkeypatch) -> None:
    class _RejectingTokenService:
        def validate(self, *_args, **_kwargs):
            from app.modules.setup.token_service import SetupTokenError

            raise SetupTokenError("SETUP_TOKEN_INVALID", "setup bearer token is required")

    monkeypatch.setattr("app.api.routes.setup.SetupTokenService", _RejectingTokenService)
    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(_create_test_app())
    response = client.post(
        "/internal/v1/setup-config-validations",
        headers={"x-request-id": "req_validate"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["error_code"] == "SETUP_TOKEN_INVALID"
    assert payload["stage"] == "setup_config_validation"


def test_setup_initialization_route_requires_confirmation_header(monkeypatch) -> None:
    client = TestClient(_create_test_app())
    response = client.put("/internal/v1/setup-initialization", json={"setup": {}, "config": {}})

    assert response.status_code == 428
    payload = response.json()
    assert payload["error_code"] == "SETUP_CONFIRMATION_REQUIRED"


def test_setup_initialization_route_returns_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.initialize",
        lambda _self, _session, _payload, *, setup_token=None: SetupInitializationResult(
            initialized=True,
            active_config_version=1,
            enterprise_id="ent_1",
            admin_user_id="user_1",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.setup.SetupTokenService.validate",
        lambda _self, _session, _token, *, required_scope: _fake_setup_token(),
    )
    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/setup-initialization",
        headers={
            "x-setup-confirm": "initialize",
            "x-request-id": "req_initialize",
            "authorization": "Bearer setup_test",
        },
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req_initialize"
    assert payload["data"]["initialized"] is True
    assert payload["data"]["active_config_version"] == 1


def test_setup_initialization_route_returns_structured_error(monkeypatch) -> None:
    def fake_initialize(_self, _session, _payload, *, setup_token=None):
        raise SetupInitializationError(
            "SETUP_CONFIG_INVALID",
            "payload is invalid",
            details={"errors": [{"path": "$.config", "message": "invalid"}]},
        )

    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.initialize",
        fake_initialize,
    )
    monkeypatch.setattr(
        "app.api.routes.setup.SetupTokenService.validate",
        lambda _self, _session, _token, *, required_scope: _fake_setup_token(),
    )
    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/setup-initialization",
        headers={"x-setup-confirm": "initialize", "authorization": "Bearer setup_test"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "SETUP_CONFIG_INVALID"
    assert payload["details"]["errors"][0]["path"] == "$.config"


def test_setup_initialization_route_returns_database_error_details(monkeypatch) -> None:
    class _FakeDriverError(Exception):
        pass

    def fake_initialize(_self, _session, _payload, *, setup_token=None):
        raise SQLAlchemyError("db failed").with_traceback(None) from _FakeDriverError("duplicate key")

    monkeypatch.setattr(
        "app.api.routes.setup.SetupInitializationService.initialize",
        fake_initialize,
    )
    monkeypatch.setattr(
        "app.api.routes.setup.SetupTokenService.validate",
        lambda _self, _session, _token, *, required_scope: _fake_setup_token(),
    )
    monkeypatch.setattr(
        "app.api.routes.setup._record_initialization_failure",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("app.api.routes.setup.session_scope", lambda: _FakeSession())

    client = TestClient(_create_test_app())
    response = client.put(
        "/internal/v1/setup-initialization",
        headers={"x-setup-confirm": "initialize", "authorization": "Bearer setup_test"},
        json={"setup": {}, "config": {}},
    )

    assert response.status_code == 500
    payload = response.json()
    assert payload["error_code"] == "SETUP_DATABASE_ERROR"
    assert payload["details"]["database_error"]["type"] == "SQLAlchemyError"
