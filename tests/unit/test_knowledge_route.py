from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.auth.schemas import AuthContext, AuthRole, AuthUser
from app.modules.knowledge import (
    AccessibleChunk,
    AccessibleChunkList,
    AccessibleCitationSource,
    AccessibleDocument,
    AccessibleDocumentList,
    AccessibleDocumentListItem,
    AccessibleDocumentVersion,
    AccessibleDocumentVersionList,
    AccessibleKnowledgeBase,
    AccessibleKnowledgeBaseList,
)
from app.modules.setup.service import SetupState, SetupStatus
from fastapi.testclient import TestClient

AUTH_TARGET = "app.api.dependencies.auth.AuthService.authenticate_access_token"


class _FakeSession:
    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _create_test_app():
    return create_app(run_startup_checks=False)


def _open_business_api(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.middleware.setup_guard.SetupService.load_state",
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
                )
            ],
            total=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        AUTH_TARGET,
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
    payload = response.json()["data"][0]
    assert payload["name"] == "制度知识库"
    assert "owner_department_id" not in payload
    assert "kb_visibility" not in payload
    assert "default_document_visibility" not in payload
    assert "policy_version" not in payload


def test_list_documents_route_requires_document_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def list_documents(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleDocumentList(
            items=[
                AccessibleDocumentListItem(
                    id="44444444-4444-4444-4444-444444444444",
                    title="员工手册",
                    lifecycle_status="active",
                    index_status="indexed",
                    updated_at=datetime(2026, 5, 25, tzinfo=UTC),
                )
            ],
            total=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        AUTH_TARGET,
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
    payload = response.json()["data"][0]
    assert payload["title"] == "员工手册"
    assert payload["can_view"] is True
    assert payload["can_cite"] is True
    assert "kb_id" not in payload
    assert "owner_department_id" not in payload
    assert "visibility" not in payload
    assert "current_version_id" not in payload


def test_get_document_route_requires_document_read_scope(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def authenticate(_self, _session, *, required_scope, **_kwargs):
        seen["required_scope"] = required_scope
        return _auth_context()

    def get_document(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleDocument(
            id=kwargs["document_id"],
            title="员工手册",
            lifecycle_status="active",
            index_status="indexed",
            updated_at=datetime(2026, 5, 1, tzinfo=UTC),
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        AUTH_TARGET,
        authenticate,
    )
    monkeypatch.setattr("app.api.routes.knowledge.KnowledgeService.get_document", get_document)

    response = TestClient(_create_test_app()).get(
        "/internal/v1/documents/44444444-4444-4444-4444-444444444444",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["required_scope"] == "document:read"
    assert seen["document_id"] == "44444444-4444-4444-4444-444444444444"
    payload = response.json()["data"]
    assert payload["title"] == "员工手册"
    assert payload["can_view"] is True
    assert payload["can_cite"] is True
    assert "kb_id" not in payload
    assert "folder_id" not in payload
    assert "owner_department_id" not in payload
    assert "visibility" not in payload
    assert "current_version_id" not in payload


def test_list_document_versions_route_returns_versions(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def list_document_versions(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleDocumentVersionList(
            items=[
                AccessibleDocumentVersion(
                    id="55555555-5555-5555-5555-555555555555",
                    document_id=kwargs["document_id"],
                    version_no=1,
                    status="active",
                ),
            ],
            total=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.knowledge.KnowledgeService.list_document_versions",
        list_document_versions,
    )

    response = TestClient(_create_test_app()).get(
        "/internal/v1/documents/44444444-4444-4444-4444-444444444444/versions",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["document_id"] == "44444444-4444-4444-4444-444444444444"
    assert seen["page"] == 1
    assert seen["page_size"] == 50
    assert response.json()["data"][0]["version_no"] == 1
    assert response.json()["pagination"] == {"page": 1, "page_size": 50, "total": 1}


def test_list_document_chunks_route_returns_chunk_previews(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def list_document_chunks(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleChunkList(
            items=[
                AccessibleChunk(
                    id="66666666-6666-6666-6666-666666666666",
                    document_id=kwargs["document_id"],
                    document_version_id="55555555-5555-5555-5555-555555555555",
                    text_preview="员工年假需要提前申请",
                    page_start=1,
                    page_end=2,
                    status="active",
                    ordinal=1,
                ),
            ],
            total=1,
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.knowledge.KnowledgeService.list_document_chunks",
        list_document_chunks,
    )

    response = TestClient(_create_test_app()).get(
        "/internal/v1/documents/44444444-4444-4444-4444-444444444444/chunks?page=2&page_size=10",
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["document_id"] == "44444444-4444-4444-4444-444444444444"
    assert seen["page"] == 2
    assert seen["page_size"] == 10
    assert response.json()["data"][0]["text_preview"] == "员工年假需要提前申请"
    assert response.json()["data"][0]["ordinal"] == 1
    assert response.json()["pagination"]["total"] == 1


def test_get_document_source_route_returns_verifiable_source(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def get_document_source(_self, _session, **kwargs):
        seen.update(kwargs)
        return AccessibleCitationSource(
            source_id=kwargs["source_id"],
            doc_id=kwargs["document_id"],
            document_version_id="55555555-5555-5555-5555-555555555555",
            title="员工手册",
            text="员工年假需要提前申请。",
            text_preview="员工年假需要提前申请",
            page_start=1,
            page_end=2,
            ordinal=1,
            heading_path="制度/请假",
            source_offsets={"chunk_ordinal": 1},
            text_status="object",
        )

    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.knowledge.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        AUTH_TARGET,
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.knowledge.KnowledgeService.get_document_source",
        get_document_source,
    )

    response = TestClient(_create_test_app()).get(
        (
            "/internal/v1/documents/44444444-4444-4444-4444-444444444444"
            "/sources/66666666-6666-6666-6666-666666666666"
        ),
        headers={"authorization": "Bearer access.jwt"},
    )

    assert response.status_code == 200
    assert seen["document_id"] == "44444444-4444-4444-4444-444444444444"
    assert seen["source_id"] == "66666666-6666-6666-6666-666666666666"
    assert response.json()["data"]["text"] == "员工年假需要提前申请。"
    assert response.json()["data"]["text_status"] == "object"
