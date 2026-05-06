from __future__ import annotations

from copy import deepcopy

from app.modules.setup.initialize_service import SetupInitializationService, SetupStatus


class _CaptureSession:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params or {}))


def _valid_payload() -> dict:
    return {
        "setup": {
            "admin": {
                "username": "admin",
                "display_name": "System Admin",
                "initial_password": "ChangeMe_123456",
                "email": "admin@example.com",
                "phone": None,
            },
            "organization": {
                "enterprise": {"name": "Default Enterprise", "code": "default"},
                "departments": [
                    {"name": "Default Department", "code": "default", "is_default": True}
                ],
            },
            "roles": {
                "builtin_roles": [
                    "system_admin",
                    "security_admin",
                    "audit_admin",
                    "department_admin",
                    "knowledge_base_admin",
                    "employee",
                ],
                "admin_role": "system_admin",
                "default_user_role": "employee",
            },
        },
        "config": {
            "schema_version": 1,
            "config_version": 1,
            "scope": {"type": "global", "id": "global"},
            "storage": {
                "access_key_ref": "secret://rag/minio/access-key",
                "secret_key_ref": "secret://rag/minio/secret-key",
            },
            "auth": {
                "password_min_length": 12,
                "password_require_uppercase": True,
                "password_require_lowercase": True,
                "password_require_digit": True,
                "jwt_signing_key_ref": "secret://rag/auth/jwt-signing-key",
            },
            "cache": {"cross_user_final_answer_allowed": False},
            "keyword_search": {"keyword_analyzer": "zhparser"},
        },
    }


def test_setup_initialize_validation_rejects_missing_default_department(monkeypatch) -> None:
    monkeypatch.setattr("app.modules.setup.initialize_service.Draft202012Validator", None)
    payload = _valid_payload()
    payload["setup"]["organization"]["departments"][0]["is_default"] = False

    result = SetupInitializationService().validate_payload(payload)

    assert result.valid is False
    assert any(issue["path"] == "$.setup.organization.departments" for issue in result.errors)


def test_setup_initialize_validation_rejects_cross_user_final_answer_cache(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.modules.setup.initialize_service.Draft202012Validator", None)
    payload = deepcopy(_valid_payload())
    payload["config"]["cache"]["cross_user_final_answer_allowed"] = True

    result = SetupInitializationService().validate_payload(payload)

    assert result.valid is False
    assert any(
        issue["path"] == "$.config.cache.cross_user_final_answer_allowed"
        for issue in result.errors
    )


def test_setup_initialize_validation_handles_malformed_config_without_crashing(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.modules.setup.initialize_service.Draft202012Validator", None)
    payload = deepcopy(_valid_payload())
    payload["config"]["auth"]["password_min_length"] = "abc"
    payload["config"]["storage"] = "bad"

    result = SetupInitializationService().validate_payload(payload)

    assert result.valid is False
    assert any(issue["path"] == "$.config.storage.access_key_ref" for issue in result.errors)


def test_prepare_model_provider_secrets_encrypts_plaintext_and_rewrites_refs(
    monkeypatch,
) -> None:
    writes: list[tuple[str, str]] = []

    def fake_put_secret(self, session, *, secret_ref: str, secret_value: str, **kwargs) -> None:
        writes.append((secret_ref, secret_value))

    monkeypatch.setattr(
        "app.modules.setup.initialize_service.SecretStoreService.put_secret",
        fake_put_secret,
    )

    payload = deepcopy(_valid_payload())
    payload["setup"]["model_provider_secrets"] = {
        "embedding_auth_token": " emb-key ",
        "rerank_auth_token": None,
        "llm_auth_token": "llm-key",
    }
    payload["config"]["model_gateway"] = {
        "providers": {
            "embedding": {"auth_token_ref": None},
            "rerank": {"auth_token_ref": None},
            "llm": {"auth_token_ref": None},
        }
    }

    prepared = SetupInitializationService()._prepare_model_provider_secrets(object(), payload)

    assert writes == [
        ("secret://rag/model/embedding-api-key", "emb-key"),
        ("secret://rag/model/llm-api-key", "llm-key"),
    ]
    assert "model_provider_secrets" not in prepared["setup"]
    assert (
        prepared["config"]["model_gateway"]["providers"]["embedding"]["auth_token_ref"]
        == "secret://rag/model/embedding-api-key"
    )
    assert (
        prepared["config"]["model_gateway"]["providers"]["rerank"]["auth_token_ref"] is None
    )
    assert (
        prepared["config"]["model_gateway"]["providers"]["llm"]["auth_token_ref"]
        == "secret://rag/model/llm-api-key"
    )


def test_mark_status_writes_json_value_without_jsonb_build_object_parameter() -> None:
    session = _CaptureSession()

    SetupInitializationService()._mark_status(session, SetupStatus.CREATING_ADMIN)

    statement, params = session.calls[0]
    assert "jsonb_build_object" not in str(statement)
    assert params == {"value_json": '{"status": "creating_admin"}'}
