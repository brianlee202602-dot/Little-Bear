from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser
from app.modules.knowledge import (
    AccessibleChunk,
    AccessibleDocument,
    AccessibleDocumentList,
    AccessibleKnowledgeBase,
    AccessibleKnowledgeBaseList,
)
from app.modules.setup.service import SetupState, SetupStatus
from fastapi.testclient import TestClient


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _create_test_app():
    return create_app(run_startup_checks=False)


def _open_business_api(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.shared.middleware.SetupService.load_state",
        lambda _self: SetupState(
            initialized=True,
            setup_status=SetupStatus.INITIALIZED,
            active_config_version=1,
            active_config_available=True,
            service_bootstrap_ready=True,
        ),
    )


def _auth_context() -> AuthContext:
    user = AuthUser(
        id="11111111-1111-1111-1111-111111111111",
        enterprise_id="33333333-3333-3333-3333-333333333333",
        username="alice",
        display_name="Alice",
        status="active",
        roles=(
            AuthRole(
                id="role_1",
                code="employee",
                name="Employee",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=("knowledge_base:read", "document:read", "rag:query"),
            ),
        ),
        scopes=("knowledge_base:read", "document:read", "rag:query"),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id, "iat": int(datetime.now(UTC).timestamp())},
    )


def test_list_knowledge_bases_route_requires_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_knowledge_bases(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleKnowledgeBaseList(
            items=[
                AccessibleKnowledgeBase(
                    id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    name="制度知识库",
                    status="active",
                    owner_department_id="22222222-2222-2222-2222-222222222222",
                    default_visibility="enterprise",
                    config_scope_id=None,
                    policy_version=1,
                )
            ],
            total=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.knowledge.AuthService.authenticate_access_token",
        authenticate,
    )
    monkeypatch.setattr(
        "app.api.routes.knowledge.KnowledgeService.list_knowledge_bases",
        list_knowledge_bases,
    )

    response = TestClient(_create_test_app()).get(
        "/internal/v1/knowledge-bases",
        headers={"authorization": "Bearer access.jwt", "x-request-id": "req_kb"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "knowledge_base:read"
    assert seen["user_id"] == _auth_context().user.id
    assert response.json()["request_id"] == "req_kb"
    assert response.json()["data"][0]["name"] == "制度知识库"


def test_list_documents_route_requires_document_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_documents(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleDocumentList(
            items=[
                AccessibleDocument(
                    id="44444444-4444-4444-4444-444444444444",
                    kb_id=kwargs["kb_id"],
                    folder_id=None,
                    title="员工手册",
                    lifecycle_status="active",
                    index_status="indexed",
                    owner_department_id="22222222-2222-2222-2222-222222222222",
                    visibility="enterprise",
                    current_version_id="55555555-5555-5555-5555-555555555555",
                )
            ],
            total=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.knowledge.AuthService.authenticate_access_token",
        authenticate,
    )
    monkeypatch.setattr(
        "app.api.routes.knowledge.KnowledgeService.list_documents",
        list_documents,
    )

    response = TestClient(_create_test_app()).get(
        "/internal/v1/knowledge-bases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/documents",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "document:read"
    assert seen["kb_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert response.json()["data"][0]["title"] == "员工手册"


def test_list_document_chunks_route_returns_chunk_previews(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def list_document_chunks(_self, _session, **kwargs):
        seen.update(kwargs)
        return (
            AccessibleChunk(
                id="66666666-6666-6666-6666-666666666666",
                document_id=kwargs["document_id"],
                document_version_id="55555555-5555-5555-5555-555555555555",
                text_preview="员工年假需要提前申请",
                page_start=1,
                page_end=2,
                status="active",
            ),
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.knowledge.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.knowledge.KnowledgeService.list_document_chunks",
        list_document_chunks,
    )

    response = TestClient(_create_test_app()).get(
        "/internal/v1/documents/44444444-4444-4444-4444-444444444444/chunks",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["document_id"] == "44444444-4444-4444-4444-444444444444"
    assert response.json()["data"][0]["text_preview"] == "员工年假需要提前申请"
