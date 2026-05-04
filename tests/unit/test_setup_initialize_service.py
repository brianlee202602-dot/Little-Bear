from __future__ import annotations

from copy import deepcopy

from app.modules.setup.initialize_service import SetupInitializationService


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
