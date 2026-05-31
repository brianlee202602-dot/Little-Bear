from app.modules.admin.errors import AdminServiceError
from app.modules.audit.errors import AuditServiceError
from app.modules.auth.errors import AuthServiceError
from app.modules.config.errors import ConfigServiceError
from app.shared.errors import ServiceError


def test_domain_service_errors_share_base_contract() -> None:
    errors = [
        AdminServiceError("ADMIN_INVALID", "invalid"),
        AuthServiceError("AUTH_INVALID", "invalid"),
        ConfigServiceError("CONFIG_INVALID", "invalid"),
        AuditServiceError("AUDIT_UNAVAILABLE", "unavailable"),
    ]

    for exc in errors:
        assert isinstance(exc, ServiceError)
        assert exc.error_code
        assert exc.message
        assert isinstance(exc.status_code, int)
        assert isinstance(exc.retryable, bool)
        assert isinstance(exc.details, dict)


def test_config_service_error_status_code_defaults() -> None:
    assert ConfigServiceError("CONFIG_KEY_NOT_FOUND", "missing").status_code == 404
    assert ConfigServiceError("CONFIG_VERSION_NOT_PUBLISHABLE", "conflict").status_code == 409
    assert ConfigServiceError("CONFIG_ACTIVE_MISSING", "unavailable").status_code == 503
    assert ConfigServiceError("CONFIG_SCHEMA_INVALID", "invalid").status_code == 400


def test_audit_service_error_status_code_defaults() -> None:
    assert AuditServiceError("AUDIT_LOG_NOT_FOUND", "missing").status_code == 404
    assert AuditServiceError("AUDIT_LOG_UNAVAILABLE", "unavailable").status_code == 503
