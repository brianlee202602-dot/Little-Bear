from __future__ import annotations

from datetime import UTC, datetime

from app.main import create_app
from app.modules.auth.schemas import AuthContext, AuthDepartment, AuthRole, AuthUser
from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import ImportJob, ImportJobList
from app.modules.import_pipeline.service import ImportService
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
        username="kb_admin",
        display_name="知识库管理员",
        status="active",
        roles=(
            AuthRole(
                id="role_1",
                code="knowledge_base_admin",
                name="Knowledge Base Admin",
                scope_type="enterprise",
                is_builtin=True,
                status="active",
                scopes=(
                    "document:import",
                    "import_job:read:self",
                    "import_job:manage:self",
                    "import_job:read",
                    "document:index",
                ),
            ),
        ),
        departments=(
            AuthDepartment(
                id="22222222-2222-2222-2222-222222222222",
                code="default",
                name="默认部门",
                status="active",
                is_primary=True,
            ),
        ),
        scopes=(
            "document:import",
            "import_job:read:self",
            "import_job:manage:self",
            "import_job:read",
            "document:index",
        ),
    )
    return AuthContext(
        user=user,
        token_jti="access_1",
        token_type="access",
        scopes=user.scopes,
        claims={"sub": user.id, "iat": int(datetime.now(UTC).timestamp())},
    )


def _job(status: str = "queued", stage: str = "validate") -> ImportJob:
    return ImportJob(
        id="99999999-9999-9999-9999-999999999999",
        kb_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        status=status,
        stage=stage,
        document_ids=("44444444-4444-4444-4444-444444444444",),
    )


def test_create_document_import_route(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.build_import_service",
        lambda _session: ImportService(),
    )
    captured: dict[str, object] = {}

    def _create_import(_self, _session, **kwargs):
        captured.update(kwargs)
        return _job()

    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.create_document_import",
        _create_import,
    )

    response = TestClient(app).post(
        "/internal/v1/knowledge-bases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/document-imports",
        headers={"Authorization": "Bearer token"},
        json={
            "job_type": "metadata_batch",
            "items": [{"title": "员工手册", "metadata": {"tags": ["HR"]}}],
        },
    )

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "queued"
    assert captured["job_type"] == "metadata_batch"


def test_create_upload_document_import_route(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.build_import_service",
        lambda _session: ImportService(),
    )
    captured: dict[str, object] = {}

    def _create_import(_self, _session, **kwargs):
        captured.update(kwargs)
        return _job()

    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.create_document_import",
        _create_import,
    )

    response = TestClient(app).post(
        "/internal/v1/knowledge-bases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/documents",
        headers={"Authorization": "Bearer token"},
        files={"files": ("handbook.md", b"# Handbook\n\nHello", "text/markdown")},
        data={"visibility": "department"},
    )

    assert response.status_code == 202
    assert captured["job_type"] == "upload"
    item = captured["items"][0]
    assert item.title == "handbook.md"
    assert item.object_content == b"# Handbook\n\nHello"
    assert item.metadata["file_type"] == "md"
    assert "content" not in item.metadata


def test_create_upload_document_import_route_rejects_disallowed_file_type(
    monkeypatch,
) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.build_import_service",
        lambda _session: ImportService(allowed_file_types=("txt",)),
    )

    response = TestClient(app).post(
        "/internal/v1/knowledge-bases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/documents",
        headers={"Authorization": "Bearer token"},
        files={"files": ("handbook.pdf", b"%PDF", "application/pdf")},
        data={"visibility": "department"},
    )

    assert response.status_code == 415
    assert response.json()["error_code"] == "IMPORT_FILE_TYPE_UNSUPPORTED"


def test_create_upload_document_import_route_rejects_oversized_file(
    monkeypatch,
) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.build_import_service",
        lambda _session: ImportService(max_upload_bytes=4, allowed_file_types=("txt",)),
    )

    response = TestClient(app).post(
        "/internal/v1/knowledge-bases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/documents",
        headers={"Authorization": "Bearer token"},
        files={"files": ("handbook.txt", b"hello", "text/plain")},
        data={"visibility": "department"},
    )

    assert response.status_code == 413
    assert response.json()["error_code"] == "IMPORT_FILE_TOO_LARGE"


def test_import_job_get_route_requires_owner_scope(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    captured: dict[str, object] = {}

    def _authenticate(*_args, **kwargs):
        captured.update(kwargs)
        return _auth_context()

    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        _authenticate,
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.get_import_job",
        lambda *_args, **_kwargs: _job(),
    )

    response = TestClient(app).get(
        "/internal/v1/import-jobs/99999999-9999-9999-9999-999999999999",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert captured["required_scope"] == "import_job:read:self"


def test_import_job_patch_route_returns_cancelled_job(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.request_cancel",
        lambda *_args, **_kwargs: _job(status="cancelled"),
    )

    response = TestClient(app).patch(
        "/internal/v1/import-jobs/99999999-9999-9999-9999-999999999999",
        headers={"Authorization": "Bearer token"},
        json={"status": "cancelled"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"


def test_admin_import_job_list_route(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    captured: dict[str, object] = {}

    def _list_import_jobs(_self, _session, **kwargs):
        captured.update(kwargs)
        return ImportJobList(items=(_job(),), total=1)

    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.list_import_jobs",
        _list_import_jobs,
    )

    response = TestClient(app).get(
        "/internal/v1/admin/import-jobs?job_type=index_rebuild",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert captured["job_type"] == "index_rebuild"
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["data"][0]["document_count"] == 1
    assert "document_ids" not in payload["data"][0]


def test_admin_index_job_retry_route_requires_document_index(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    captured: dict[str, object] = {}

    def _authenticate(*_args, **kwargs):
        captured["required_scope"] = kwargs["required_scope"]
        return _auth_context()

    def _retry_index_jobs(_self, _session, **kwargs):
        captured.update(kwargs)
        return ImportJobList(
            items=(
                ImportJob(
                    id="88888888-8888-8888-8888-888888888888",
                    kb_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    status="queued",
                    stage="embed",
                    document_ids=("44444444-4444-4444-4444-444444444444",),
                    job_type="index_rebuild",
                ),
            ),
            total=1,
        )

    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        _authenticate,
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.create_index_job_retries",
        _retry_index_jobs,
    )

    response = TestClient(app).post(
        "/internal/v1/admin/index-jobs/retries",
        headers={"Authorization": "Bearer token", "x-index-confirm": "retry"},
        json={"job_ids": ["99999999-9999-9999-9999-999999999999"]},
    )

    assert response.status_code == 202
    assert captured["required_scope"] == "document:index"
    assert captured["job_ids"] == ["99999999-9999-9999-9999-999999999999"]
    payload = response.json()
    assert payload["data"][0]["job_type"] == "index_rebuild"
    assert payload["data"][0]["document_count"] == 1
    assert "document_ids" not in payload["data"][0]


def test_import_route_returns_service_error(monkeypatch) -> None:
    app = _create_test_app()
    _open_business_api(monkeypatch)
    monkeypatch.setattr("app.api.routes.import_pipeline.session_scope", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.AuthService.authenticate_access_token",
        lambda *_args, **_kwargs: _auth_context(),
    )
    monkeypatch.setattr(
        "app.api.routes.import_pipeline.build_import_service",
        lambda _session: ImportService(),
    )

    def _raise_error(*_args, **_kwargs):
        raise ImportServiceError("IMPORT_KB_DENIED", "denied", status_code=403)

    monkeypatch.setattr(
        "app.api.routes.import_pipeline.ImportService.create_document_import",
        _raise_error,
    )

    response = TestClient(app).post(
        "/internal/v1/knowledge-bases/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/document-imports",
        headers={"Authorization": "Bearer token"},
        json={"job_type": "metadata_batch", "items": [{"title": "员工手册"}]},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "IMPORT_KB_DENIED"
