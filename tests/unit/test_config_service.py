from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.modules.config.cache import ConfigCache
from app.modules.config.errors import ConfigServiceError
from app.modules.config.probe import ActiveConfigProbe
from app.modules.config.service import ConfigService
from app.shared.json_utils import stable_json_hash


class _Result:
    def __init__(self, *, rows: list[Any] | None = None, row: Any | None = None) -> None:
        self.rows = rows or []
        self.row = row

    def all(self):
        return self.rows

    def one_or_none(self):
        return self.row

    def one(self):
        return self.row


class _Row:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping


class _SessionContext:
    def __init__(self, session: Any) -> None:
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _ProbeSession:
    def __init__(self, *, tables_present: bool = True, row_present: bool = True) -> None:
        self.tables_present = tables_present
        self.row_present = row_present

    def execute(self, statement, *_args, **_kwargs):
        sql = str(statement)
        if "to_regclass" in sql:
            table_name = "config_versions" if self.tables_present else None
            return _Result(
                row=_Row(
                    {
                        "config_versions_table": table_name,
                        "system_configs_table": table_name,
                    }
                )
            )
        if "FROM system_configs" in sql:
            return _Result(row=_Row({"exists": 1}) if self.row_present else None)
        raise AssertionError(f"unexpected SQL: {sql}")


class _FakeSession:
    def __init__(
        self,
        *,
        config: dict[str, Any] | str | None = None,
        initialized: bool = True,
        active_config_version: int | None = 1,
        value_hash: str | None = None,
        config_hash: str | None = None,
        row_missing: bool = False,
    ) -> None:
        self.config = _example_config() if config is None else config
        self.initialized = initialized
        self.active_config_version = active_config_version
        self.row_missing = row_missing
        if isinstance(self.config, dict):
            self.value_hash = value_hash or stable_json_hash(self.config)
            self.config_hash = config_hash or stable_json_hash(self.config)
        else:
            self.value_hash = value_hash or "hash_from_string"
        self.config_hash = config_hash or self.value_hash
        self.execute_count = 0
        self.next_version = 2
        self.config_version_status = "draft"
        self.statements: list[tuple[str, dict[str, Any]]] = []

    def execute(self, statement, *_args, **_kwargs):
        self.execute_count += 1
        sql = str(statement)
        params = _args[0] if _args and isinstance(_args[0], dict) else {}
        self.statements.append((sql, params))
        if "FROM system_state" in sql:
            return _Result(
                rows=[
                    _Row({"key": "initialized", "value_json": {"value": self.initialized}}),
                    _Row(
                        {
                            "key": "setup_status",
                            "value_json": {
                                "status": "initialized"
                                if self.initialized
                                else "not_initialized"
                            },
                        }
                    ),
                    _Row(
                        {
                            "key": "active_config_version",
                            "value_json": {"version": self.active_config_version},
                        }
                    ),
                ]
            )

        if "FROM system_configs" in sql:
            if self.row_missing:
                return _Result(row=None)
            return _Result(
                row=_Row(
                    {
                        "config_version_id": "cfg_1",
                        "config_version": self.active_config_version or 1,
                        "scope_type": "global",
                        "scope_id": "global",
                        "config_status": "active",
                        "config_hash": self.config_hash,
                        "schema_version": 1,
                        "activated_at": None,
                        "system_config_version": self.active_config_version or 1,
                        "system_config_status": "active",
                        "value_json": self.config,
                        "value_hash": self.value_hash,
                    }
                )
            )

        if "FROM config_versions" in sql and "WHERE version = :version" in sql:
            return _Result(
                row=_Row(
                    {
                        "config_version_id": "cfg_2",
                        "version": params.get("version", 2),
                        "scope_type": "global",
                        "scope_id": "global",
                        "status": self.config_version_status,
                        "config_hash": self.config_hash,
                        "schema_version": 1,
                        "validation_result_json": {"valid": True},
                        "risk_level": "medium",
                        "created_by": None,
                        "created_at": None,
                        "activated_at": None,
                    }
                )
            )

        if "COALESCE(MAX(version)" in sql:
            return _Result(row=_Row({"version": self.next_version}))

        if "cv.status = 'draft'" in sql:
            return _Result(rows=[])

        if "cv.status IN ('draft', 'validating')" in sql:
            return _Result(rows=[])

        if "cv.config_hash = :config_hash" in sql:
            return _Result(row=None)

        if "UPDATE config_versions" in sql or "UPDATE system_configs" in sql:
            return _Result()

        if (
            "INSERT INTO config_versions" in sql
            or "INSERT INTO system_configs" in sql
            or "INSERT INTO audit_logs" in sql
        ):
            return _Result()

        raise AssertionError(f"unexpected SQL: {sql}")


def _example_config() -> dict[str, Any]:
    payload = json.loads(
        Path("docs/examples/setup-initialization.local.p0.json").read_text(encoding="utf-8")
    )
    return payload["config"]


def test_config_service_loads_active_config_snapshot() -> None:
    session = _FakeSession()

    snapshot = ConfigService(cache=ConfigCache()).load_active_config(session)

    assert snapshot.version == 1
    assert snapshot.schema_version == 1
    assert snapshot.scope_type == "global"
    assert snapshot.section("auth")["jwt_issuer"] == "little-bear-rag"
    assert snapshot.summary()["config_hash"] == stable_json_hash(_example_config())


def test_active_config_probe_reports_table_missing() -> None:
    result = ActiveConfigProbe().probe(_ProbeSession(tables_present=False), 1)

    assert result.status == "table_missing"
    assert result.reason == "config_table_missing"
    assert result.recoverable is False


def test_active_config_probe_reports_active_config_missing() -> None:
    result = ActiveConfigProbe().probe(_ProbeSession(row_present=False), 1)

    assert result.status == "missing"
    assert result.reason == "active_config_missing"
    assert result.recoverable is True


def test_config_snapshot_sections_are_copied() -> None:
    snapshot = ConfigService(cache=ConfigCache()).load_active_config(_FakeSession())

    auth = snapshot.section("auth")
    auth["jwt_issuer"] = "changed"

    assert snapshot.section("auth")["jwt_issuer"] == "little-bear-rag"


def test_config_snapshot_rejects_missing_section() -> None:
    snapshot = ConfigService(cache=ConfigCache()).load_active_config(_FakeSession())

    with pytest.raises(ConfigServiceError) as exc_info:
        snapshot.section("missing")

    assert exc_info.value.error_code == "CONFIG_SECTION_MISSING"
    assert exc_info.value.details["section"] == "missing"


def test_config_snapshot_rejects_non_object_section() -> None:
    config = _example_config()
    config["auth"] = "invalid"
    snapshot = ConfigService(cache=ConfigCache()).load_active_config(
        _FakeSession(config=config),
        validate_schema=False,
    )

    with pytest.raises(ConfigServiceError) as exc_info:
        snapshot.section("auth")

    assert exc_info.value.error_code == "CONFIG_SECTION_INVALID"
    assert exc_info.value.details["value_type"] == "str"


def test_config_service_rejects_uninitialized_system() -> None:
    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).load_active_config(
            _FakeSession(initialized=False, active_config_version=None)
        )

    assert exc_info.value.error_code == "CONFIG_NOT_INITIALIZED"
    assert exc_info.value.retryable is True


def test_config_service_rejects_explicit_version_when_uninitialized() -> None:
    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).load_active_config(
            _FakeSession(initialized=False, active_config_version=1),
            active_config_version=1,
        )

    assert exc_info.value.error_code == "CONFIG_NOT_INITIALIZED"
    assert exc_info.value.retryable is True


def test_config_service_rejects_missing_active_config_row() -> None:
    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).load_active_config(_FakeSession(row_missing=True))

    assert exc_info.value.error_code == "CONFIG_ACTIVE_MISSING"
    assert exc_info.value.retryable is True


def test_config_service_rejects_version_mismatch() -> None:
    config = _example_config()
    config["config_version"] = 2

    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).load_active_config(_FakeSession(config=config))

    assert exc_info.value.error_code == "CONFIG_VERSION_MISMATCH"


def test_config_service_rejects_schema_invalid_config() -> None:
    config = _example_config()
    del config["auth"]

    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).load_active_config(_FakeSession(config=config))

    assert exc_info.value.error_code == "CONFIG_SCHEMA_INVALID"
    assert exc_info.value.details["error_count"] >= 1


def test_config_service_rejects_hash_mismatch() -> None:
    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).load_active_config(
            _FakeSession(value_hash="not_the_real_hash")
        )

    assert exc_info.value.error_code == "CONFIG_HASH_MISMATCH"
    assert exc_info.value.retryable is True


def test_config_service_uses_cache_until_invalidated(monkeypatch) -> None:
    session = _FakeSession()

    def fake_session_scope():
        return _SessionContext(session)

    monkeypatch.setattr("app.modules.config.service.session_scope", fake_session_scope)

    cache = ConfigCache(ttl_seconds=60)
    service = ConfigService(cache=cache)

    first = service.get_active_config()
    second = service.get_active_config()

    assert first is second
    assert session.execute_count == 2

    service.invalidate_cache()
    third = service.get_active_config()

    assert third is not first
    assert session.execute_count == 4


def test_config_service_lists_editable_active_config_sections() -> None:
    items = ConfigService(cache=ConfigCache()).list_config_items(_FakeSession())

    keys = {item.key for item in items}

    assert "auth" in keys
    assert "model_gateway" in keys
    assert "config_version" not in keys
    assert "schema_version" not in keys


def test_config_service_saves_draft_from_active_config() -> None:
    session = _FakeSession()
    config = _example_config()
    auth_config = dict(config["auth"])
    auth_config["access_token_ttl_minutes"] = 45

    item = ConfigService(cache=ConfigCache()).save_config_draft(
        session,
        key="auth",
        value_json=auth_config,
        actor_user_id=None,
    )

    assert item.key == "auth"
    assert item.status == "draft"
    assert item.version == 2
    assert item.value_json["access_token_ttl_minutes"] == 45
    assert any("INSERT INTO config_versions" in sql for sql, _params in session.statements)
    assert any("INSERT INTO system_configs" in sql for sql, _params in session.statements)


def test_config_service_rejects_non_editable_metadata_key() -> None:
    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).get_config_item(_FakeSession(), "config_version")

    assert exc_info.value.error_code == "CONFIG_KEY_NOT_FOUND"


def test_config_service_discards_draft_version() -> None:
    session = _FakeSession()

    version = ConfigService(cache=ConfigCache()).discard_config_draft(
        session,
        version=2,
        actor_user_id=None,
    )

    assert version.version == 2
    assert version.status == "archived"
    assert any("UPDATE config_versions" in sql for sql, _params in session.statements)
    assert any("UPDATE system_configs" in sql for sql, _params in session.statements)
    assert any(
        "config.draft_discarded" in params.get("event_name", "")
        for _sql, params in session.statements
    )


def test_config_service_rejects_discarding_active_version() -> None:
    session = _FakeSession()
    session.config_version_status = "active"

    with pytest.raises(ConfigServiceError) as exc_info:
        ConfigService(cache=ConfigCache()).discard_config_draft(
            session,
            version=1,
            actor_user_id=None,
        )

    assert exc_info.value.error_code == "CONFIG_VERSION_NOT_DISCARDABLE"


def test_config_validation_reports_schema_errors_without_dependency_checks(monkeypatch) -> None:
    called = False

    def fake_bootstrap(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.modules.setup.bootstrap_service.ServiceBootstrapService.bootstrap",
        fake_bootstrap,
    )
    invalid_config = _example_config()
    del invalid_config["auth"]

    result = ConfigService(cache=ConfigCache()).validate_config_payload(
        _FakeSession(),
        config=invalid_config,
    )

    assert result.valid is False
    assert result.errors
    assert called is False
