from __future__ import annotations

from app.modules.setup.token_service import SetupTokenService


class _ExecuteResult:
    rowcount = 1


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, params=None):  # noqa: ANN001
        self.executed.append((str(statement), dict(params or {})))
        return _ExecuteResult()


def test_setup_token_issue_writes_metadata_only_audit(monkeypatch) -> None:
    audit_calls: list[dict[str, object]] = []

    class _AuditWriter:
        def write(self, _session, **kwargs):  # noqa: ANN001
            audit_calls.append(kwargs)

    monkeypatch.setattr("app.modules.setup.token_service.AuditWriter", lambda: _AuditWriter())

    session = _FakeSession()
    issued = SetupTokenService().issue(session, ttl_seconds=60)

    assert issued.token.count(".") == 2
    assert any("INSERT INTO setup_tokens" in sql for sql, _params in session.executed)
    assert audit_calls
    audit = audit_calls[0]
    assert audit["event_name"] == "setup_token.issued"
    assert audit["actor_type"] == "system"
    assert audit["resource_type"] == "setup"
    summary = audit["summary"]
    assert isinstance(summary, dict)
    assert summary["token_jti"] == issued.jwt_jti
    assert summary["expires_at"] == issued.expires_at.isoformat()
    assert "token" not in summary
    assert "token_hash" not in summary
    assert issued.token not in str(summary)
