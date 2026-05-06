from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.modules.setup.bootstrap_service import (
    EXPECTED_SCHEMA_REVISION,
    BootstrapCheck,
    ServiceBootstrapResult,
    ServiceBootstrapService,
    ServiceBootstrapStateService,
)


class _Result:
    def __init__(self, row=None) -> None:
        self.row = row

    def one_or_none(self):
        return self.row

    def one(self):
        return self.row or _Row({})


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _FakeSession:
    def execute(self, statement, *_args, **_kwargs):
        sql = str(statement)
        if "alembic_version" in sql:
            return _Result(_Row({"version_num": EXPECTED_SCHEMA_REVISION}))
        return _Result(_Row({}))


class _StateSession:
    def execute(self, statement, *_args, **_kwargs):
        sql = str(statement)
        if "FROM system_state" in sql:
            return _Result(
                _Row(
                    {
                        "value_json": {
                            "ready": True,
                            "config_version": 1,
                            "schema_migration_version": EXPECTED_SCHEMA_REVISION,
                            "checks": [
                                {
                                    "name": "redis",
                                    "status": "passed",
                                    "message": "cached",
                                    "required": True,
                                }
                            ],
                        },
                        "updated_at": datetime.now(UTC),
                    }
                )
            )
        raise AssertionError(f"unexpected SQL: {sql}")


class _ExplodingBootstrapService(ServiceBootstrapService):
    def load_schema_revision(self, _session):
        return EXPECTED_SCHEMA_REVISION

    def bootstrap(self, *_args, **_kwargs) -> ServiceBootstrapResult:
        raise AssertionError("cached bootstrap state should be reused")

    def persist_result(self, *_args, **_kwargs) -> None:
        raise AssertionError("cached bootstrap state should not be persisted")


def _example_config() -> dict:
    payload = json.loads(
        Path("docs/examples/setup-initialization.local.p0.json").read_text(encoding="utf-8")
    )
    return payload["config"]


def test_service_bootstrap_passes_when_required_dependencies_are_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.SecretStoreService.verify_secret",
        lambda _self, _session, *, secret_ref: None,
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.SecretStoreService.get_secret_value",
        lambda _self, _session, *, secret_ref: "provider-token",
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service._redis_ping",
        lambda _redis_url, _timeout: None,
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service._http_get",
        lambda _url, *, timeout_seconds, headers=None: None,
    )

    result = ServiceBootstrapService().bootstrap(_FakeSession(), config=_example_config())

    assert result.ready is True
    assert result.schema_revision == EXPECTED_SCHEMA_REVISION
    assert {check.name for check in result.checks} >= {
        "migration",
        "active_config_schema",
        "secret_minio_access_key",
        "redis",
        "minio",
        "qdrant",
        "keyword_search",
        "model_provider_embedding",
        "model_provider_rerank",
        "model_provider_llm",
    }


def test_service_bootstrap_state_reuses_fresh_cached_result() -> None:
    result = ServiceBootstrapStateService(
        bootstrap_service=_ExplodingBootstrapService(),
        ttl_seconds=60,
    ).ensure_ready(_StateSession(), active_config_version=1)

    assert result.ready is True
    assert result.config_version == 1
    assert result.checks == (
        BootstrapCheck(name="redis", status="passed", message="cached", required=True),
    )


def test_service_bootstrap_fails_when_required_secret_is_missing(monkeypatch) -> None:
    from app.modules.secrets.service import SecretStoreError

    def fake_verify(_self, _session, *, secret_ref):
        if secret_ref == "secret://rag/auth/jwt-signing-key":
            raise SecretStoreError("secret ref does not exist")

    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.SecretStoreService.verify_secret",
        fake_verify,
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.SecretStoreService.get_secret_value",
        lambda _self, _session, *, secret_ref: "provider-token",
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service._redis_ping",
        lambda _redis_url, _timeout: None,
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service._http_get",
        lambda _url, *, timeout_seconds, headers=None: None,
    )

    result = ServiceBootstrapService().bootstrap(_FakeSession(), config=_example_config())

    assert result.ready is False
    assert any(
        check.name == "secret_jwt_signing_key" and check.status == "failed"
        for check in result.checks
    )


def test_service_bootstrap_reports_redis_resolution_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.SecretStoreService.verify_secret",
        lambda _self, _session, *, secret_ref: None,
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.SecretStoreService.get_secret_value",
        lambda _self, _session, *, secret_ref: "provider-token",
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service._redis_ping",
        lambda _redis_url, _timeout: (_ for _ in ()).throw(
            OSError("Name or service not known")
        ),
    )
    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service._http_get",
        lambda _url, *, timeout_seconds, headers=None: None,
    )

    result = ServiceBootstrapService().bootstrap(_FakeSession(), config=_example_config())

    assert result.ready is False
    assert any(
        check.name == "redis"
        and check.status == "failed"
        and "Name or service not known" in check.message
        for check in result.checks
    )
