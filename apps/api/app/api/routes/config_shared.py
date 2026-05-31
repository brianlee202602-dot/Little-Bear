"""配置管理路由共享工具。"""

from __future__ import annotations

from functools import partial

from app.api.dependencies.auth import authenticate_required_scope as _authenticate
from app.api.dependencies.auth import current_request_id as _request_id
from app.api.dependencies.auth import extract_bearer_token as _extract_bearer_token
from app.api.errors import (
    confirmation_required_response,
    database_error_response,
    service_error_response,
)
from app.api.schemas.config import (
    ConfigItemData,
    ConfigItemListItemData,
    ConfigValidationData,
    ConfigVersionData,
    ConfigVersionListItemData,
)
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.schemas import AuthContext
from app.modules.config.schemas import ConfigItem, ConfigValidationResult, ConfigVersion

_auth_error_response = service_error_response
_config_error_response = service_error_response
_confirmation_error_response = partial(
    confirmation_required_response,
    error_code="CONFIG_CONFIRMATION_REQUIRED",
    details={"required_header": "x-config-confirm"},
)
_database_error_response = partial(
    database_error_response,
    error_code="CONFIG_DATABASE_ERROR",
    message="config database operation failed",
)


def authenticate_system_admin_config_manager(session: object, token: str | None) -> AuthContext:
    auth_context = _authenticate(session, token, required_scope="config:manage")
    has_system_admin_role = any(
        role.code == "system_admin" and role.status == "active"
        for role in auth_context.user.roles
    )
    if not has_system_admin_role:
        raise AuthServiceError(
            "AUTH_SYSTEM_ADMIN_REQUIRED",
            "config management requires active system_admin role",
            status_code=403,
            details={"required_role": "system_admin", "required_scope": "config:manage"},
        )
    return auth_context


def item_data(item: ConfigItem) -> ConfigItemData:
    return ConfigItemData(
        key=item.key,
        value_json=item.value_json,
        scope_type=item.scope_type,
        status=item.status,
        version=item.version,
    )


def item_list_item_data(item: ConfigItem) -> ConfigItemListItemData:
    return ConfigItemListItemData(
        key=item.key,
        scope_type=item.scope_type,
        status=item.status,
        version=item.version,
    )


def version_data(version: ConfigVersion) -> ConfigVersionData:
    return ConfigVersionData(
        version=version.version,
        status=version.status,
        risk_level=version.risk_level,
        created_by=version.created_by,
        config=version.config,
        created_at=version.created_at,
        updated_at=version.updated_at,
        activated_at=version.activated_at,
    )


def version_list_item_data(version: ConfigVersion) -> ConfigVersionListItemData:
    return ConfigVersionListItemData(
        version=version.version,
        status=version.status,
        risk_level=version.risk_level,
        created_by=version.created_by,
        created_at=version.created_at,
        updated_at=version.updated_at,
        activated_at=version.activated_at,
    )


def validation_data(result: ConfigValidationResult) -> ConfigValidationData:
    return ConfigValidationData(
        valid=result.valid,
        errors=result.errors,
        warnings=result.warnings,
    )


_authenticate_system_admin_config_manager = authenticate_system_admin_config_manager
_item_data = item_data
_item_list_item_data = item_list_item_data
_version_data = version_data
_version_list_item_data = version_list_item_data
_validation_data = validation_data

__all__ = [
    "_auth_error_response",
    "_authenticate",
    "_authenticate_system_admin_config_manager",
    "_config_error_response",
    "_confirmation_error_response",
    "_database_error_response",
    "_extract_bearer_token",
    "_item_data",
    "_item_list_item_data",
    "_request_id",
    "_validation_data",
    "_version_data",
    "_version_list_item_data",
    "authenticate_system_admin_config_manager",
]

