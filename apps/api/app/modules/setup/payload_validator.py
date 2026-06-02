"""Setup initialization payload validation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.modules.config.errors import ConfigServiceError
from app.modules.setup.contracts import (
    BUILTIN_ROLE_NAMES,
    SetupValidationResult,
    issue,
    setup_schema_error_code,
)
from app.shared.json_utils import as_dict


class SetupPayloadValidator:
    """Validate setup payload without mutating persistent state."""

    def __init__(self, *, schema_validator_factory: Callable[[], Any]) -> None:
        self._schema_validator_factory = schema_validator_factory

    def validate(self, payload: dict[str, Any]) -> SetupValidationResult:
        errors: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []

        self._validate_schema(payload, errors)
        setup = as_dict(payload.get("setup"))
        config = as_dict(payload.get("config"))

        self._validate_setup_rules(setup, config, errors)
        self._validate_secret_refs(config, errors)
        self._validate_cache_policy(config, errors)
        self._validate_keyword_search(config, warnings)

        return SetupValidationResult(valid=not errors, errors=errors, warnings=warnings)

    def _validate_schema(self, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
        try:
            issues = self._schema_validator_factory().validate_setup_payload(payload)
        except ConfigServiceError as exc:
            errors.append(
                issue(
                    setup_schema_error_code(exc.error_code),
                    "$",
                    exc.message,
                    retryable=exc.retryable,
                )
            )
            return

        for schema_issue in issues:
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    schema_issue.path,
                    schema_issue.message,
                    retryable=False,
                )
            )

    def _validate_setup_rules(
        self,
        setup: dict[str, Any],
        config: dict[str, Any],
        errors: list[dict[str, object]],
    ) -> None:
        admin = as_dict(setup.get("admin"))
        organization = as_dict(setup.get("organization"))
        roles = as_dict(setup.get("roles"))
        departments = organization.get("departments")

        if not isinstance(departments, list) or not departments:
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.organization.departments",
                    "at least one department is required",
                )
            )
        else:
            default_count = sum(
                1
                for item in departments
                if isinstance(item, dict) and item.get("is_default") is True
            )
            if default_count != 1:
                errors.append(
                    issue(
                        "SETUP_CONFIG_INVALID",
                        "$.setup.organization.departments",
                        "exactly one default department is required",
                    )
                )

        builtin_roles = roles.get("builtin_roles")
        if not isinstance(builtin_roles, list) or set(builtin_roles) != BUILTIN_ROLE_NAMES:
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.roles.builtin_roles",
                    "builtin roles must match P0 role set",
                )
            )
        if roles.get("admin_role") != "system_admin":
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.roles.admin_role",
                    "admin_role must be system_admin",
                )
            )
        if roles.get("default_user_role") != "employee":
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.roles.default_user_role",
                    "default_user_role must be employee",
                )
            )

        password = admin.get("initial_password")
        auth_config = as_dict(config.get("auth"))
        min_length = auth_config.get("password_min_length", 12)
        if not isinstance(min_length, int):
            min_length = 12
        if not isinstance(password, str) or len(password) < min_length:
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password does not meet length policy",
                )
            )
        if auth_config.get("password_require_uppercase") and not any(
            char.isupper() for char in password or ""
        ):
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password requires uppercase letter",
                )
            )
        if auth_config.get("password_require_lowercase") and not any(
            char.islower() for char in password or ""
        ):
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password requires lowercase letter",
                )
            )
        if auth_config.get("password_require_digit") and not any(
            char.isdigit() for char in password or ""
        ):
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.setup.admin.initial_password",
                    "initial password requires digit",
                )
            )

    def _validate_secret_refs(
        self, config: dict[str, Any], errors: list[dict[str, object]]
    ) -> None:
        storage = as_dict(config.get("storage"))
        auth = as_dict(config.get("auth"))
        model_gateway = as_dict(config.get("model_gateway"))
        model_providers = as_dict(model_gateway.get("providers"))
        secret_refs = [
            ("$.config.storage.access_key_ref", storage.get("access_key_ref"), True),
            ("$.config.storage.secret_key_ref", storage.get("secret_key_ref"), True),
            ("$.config.auth.jwt_signing_key_ref", auth.get("jwt_signing_key_ref"), True),
            ("$.config.model_gateway.auth_token_ref", model_gateway.get("auth_token_ref"), False),
        ]
        for provider_name in ("embedding", "rerank", "llm"):
            provider = as_dict(model_providers.get(provider_name))
            secret_refs.append(
                (
                    f"$.config.model_gateway.providers.{provider_name}.auth_token_ref",
                    provider.get("auth_token_ref"),
                    False,
                )
            )

        for path, value, required in secret_refs:
            if not value and not required:
                continue
            if not isinstance(value, str) or not value.startswith("secret://rag/"):
                errors.append(
                    issue("SETUP_CONFIG_INVALID", path, "secret ref must start with secret://rag/")
                )

    def _validate_cache_policy(
        self, config: dict[str, Any], errors: list[dict[str, object]]
    ) -> None:
        cache = as_dict(config.get("cache"))
        if cache.get("cross_user_final_answer_allowed") is True:
            errors.append(
                issue(
                    "SETUP_CONFIG_INVALID",
                    "$.config.cache.cross_user_final_answer_allowed",
                    "cross-user final answer cache is not allowed in P0",
                )
            )

    def _validate_keyword_search(
        self, config: dict[str, Any], warnings: list[dict[str, object]]
    ) -> None:
        keyword_search = as_dict(config.get("keyword_search"))
        if keyword_search.get("keyword_analyzer") != "zhparser":
            warnings.append(
                issue(
                    "SETUP_KEYWORD_ANALYZER_WARNING",
                    "$.config.keyword_search.keyword_analyzer",
                    "P0 Chinese keyword search expects zhparser",
                    retryable=False,
                )
            )
