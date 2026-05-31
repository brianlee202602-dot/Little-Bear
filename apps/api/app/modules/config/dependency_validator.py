"""Config schema and external dependency validation."""

from __future__ import annotations

from typing import Any

from app.modules.config.schemas import ConfigValidationResult
from app.modules.config.utils import schema_errors
from sqlalchemy.orm import Session


class ConfigDependencyValidator:
    """Validates config schema and required runtime dependencies."""

    def validate_config_and_dependencies(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> tuple[ConfigValidationResult, Any | None]:
        errors = schema_errors(config)
        if errors:
            return ConfigValidationResult(valid=False, errors=errors, warnings=[]), None

        bootstrap_result = self.run_dependency_validation(session, config=config)
        return (
            ConfigValidationResult(
                valid=not bootstrap_result["errors"],
                errors=bootstrap_result["errors"],
                warnings=bootstrap_result["warnings"],
            ),
            bootstrap_result["bootstrap_result"],
        )

    def run_dependency_validation(
        self,
        session: Session,
        *,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        from app.modules.setup.bootstrap_service import ServiceBootstrapService

        result = ServiceBootstrapService().bootstrap(session, config=config)
        errors: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []
        for check in result.checks:
            item: dict[str, object] = {
                "error_code": "CONFIG_DEPENDENCY_FAILED",
                "path": check.name,
                "message": check.message,
                "retryable": True,
                "status": check.status,
                "required": check.required,
            }
            if check.passed:
                continue
            if check.required:
                errors.append(item)
            else:
                warnings.append(item)
        return {"errors": errors, "warnings": warnings, "bootstrap_result": result}

    def persist_bootstrap_state(self, session: Session, *, bootstrap_result: Any | None) -> None:
        from app.modules.setup.bootstrap_service import ServiceBootstrapService

        if bootstrap_result is not None:
            ServiceBootstrapService().persist_result(session, bootstrap_result)
