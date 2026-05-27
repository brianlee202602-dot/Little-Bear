"""Config Admin API。

管理后台通过这里读取 active_config 分组、保存配置草稿、执行发布前校验，并把已校验
的 draft 原子发布为新的 active_config 版本。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse, Response

from app.api.schemas.config import (
    ConfigItemData,
    ConfigItemListResponse,
    ConfigItemResponse,
    ConfigPutRequest,
    ConfigValidationData,
    ConfigValidationRequest,
    ConfigValidationResponse,
    ConfigVersionCreateRequest,
    ConfigVersionData,
    ConfigVersionListItemData,
    ConfigVersionListResponse,
    ConfigVersionPatchRequest,
    ConfigVersionPutRequest,
    ConfigVersionResponse,
    PaginationData,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.runtime import GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER
from app.modules.auth.schemas import AuthContext
from app.modules.auth.service import AuthService
from app.modules.config.errors import ConfigServiceError
from app.modules.config.schemas import ConfigItem, ConfigValidationResult, ConfigVersion
from app.modules.config.service import HIGH_RISK_CONFIG_KEYS, ConfigService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-config"])


@router.get("/configs", response_model=ConfigItemListResponse)
async def list_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ConfigItemListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            _authenticate(session, token, required_scope="config:read")
            items = service.list_config_items(session)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_list")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_list")

    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return ConfigItemListResponse(
        request_id=_request_id(),
        data=[_item_data(item) for item in page_items],
        pagination=PaginationData(page=page, page_size=page_size, total=len(items)),
    )


@router.get("/configs/{key}", response_model=ConfigItemResponse)
async def get_config(
    key: str,
    authorization: str | None = Header(default=None),
) -> ConfigItemResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            _authenticate(session, token, required_scope="config:read")
            item = service.get_config_item(session, key)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_get")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_get")
    return ConfigItemResponse(request_id=_request_id(), data=_item_data(item))


@router.put("/configs/{key}", response_model=ConfigItemResponse)
async def put_config(
    key: str,
    payload: ConfigPutRequest,
    authorization: str | None = Header(default=None),
    x_config_confirm: str | None = Header(default=None),
) -> ConfigItemResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            auth_context = _authenticate_system_admin_config_manager(session, token)
            if key in HIGH_RISK_CONFIG_KEYS and x_config_confirm != "save-draft":
                return _confirmation_error_response(
                    stage="config_save_draft",
                    message="high-risk config requires x-config-confirm: save-draft",
                )
            item = service.save_config_draft(
                session,
                key=key,
                value_json=payload.value_json,
                actor_user_id=auth_context.user.id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_save_draft")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_save_draft")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_save_draft")
    return ConfigItemResponse(request_id=_request_id(), data=_item_data(item))


@router.get("/config-versions", response_model=ConfigVersionListResponse)
async def list_config_versions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ConfigVersionListResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            _authenticate(session, token, required_scope="config:read")
            versions = service.list_config_versions(session, page=page, page_size=page_size)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_version_list")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_version_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_version_list")
    return ConfigVersionListResponse(
        request_id=_request_id(),
        data=[_version_list_item_data(version) for version in versions.items],
        pagination=PaginationData(page=page, page_size=page_size, total=versions.total),
    )


@router.post("/config-versions", response_model=ConfigVersionResponse)
async def create_config_version(
    payload: ConfigVersionCreateRequest,
    authorization: str | None = Header(default=None),
    x_config_confirm: str | None = Header(default=None),
) -> ConfigVersionResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            auth_context = _authenticate_system_admin_config_manager(session, token)
            if x_config_confirm != "save-draft":
                return _confirmation_error_response(
                    stage="config_version_create",
                    message="creating config version requires x-config-confirm: save-draft",
                )
            version = service.create_config_version(
                session,
                config=payload.config,
                actor_user_id=auth_context.user.id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_version_create")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_version_create")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_version_create")
    return ConfigVersionResponse(request_id=_request_id(), data=_version_data(version))


@router.get("/config-versions/{version}", response_model=ConfigVersionResponse)
async def get_config_version(
    version: int,
    authorization: str | None = Header(default=None),
) -> ConfigVersionResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            _authenticate(session, token, required_scope="config:read")
            item = service.get_config_version(session, version)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_version_get")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_version_get")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_version_get")
    return ConfigVersionResponse(request_id=_request_id(), data=_version_data(item))


@router.put("/config-versions/{version}", response_model=ConfigVersionResponse)
async def put_config_version(
    version: int,
    payload: ConfigVersionPutRequest,
    authorization: str | None = Header(default=None),
    x_config_confirm: str | None = Header(default=None),
) -> ConfigVersionResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            auth_context = _authenticate_system_admin_config_manager(session, token)
            if x_config_confirm != "save-draft":
                return _confirmation_error_response(
                    stage="config_version_update",
                    message="updating config version requires x-config-confirm: save-draft",
                )
            item = service.update_config_version(
                session,
                version=version,
                config=payload.config,
                actor_user_id=auth_context.user.id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_version_update")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_version_update")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_version_update")
    return ConfigVersionResponse(request_id=_request_id(), data=_version_data(item))


@router.patch("/config-versions/{version}", response_model=ConfigVersionResponse)
async def patch_config_version(
    version: int,
    payload: ConfigVersionPatchRequest,
    authorization: str | None = Header(default=None),
    x_config_confirm: str | None = Header(default=None),
) -> ConfigVersionResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    stage = "config_publish" if payload.status == "active" else "config_archive"
    service = ConfigService()
    try:
        with session_scope() as session:
            auth_context = _authenticate_system_admin_config_manager(session, token)
            if payload.status == "active":
                if x_config_confirm != "publish":
                    return _confirmation_error_response(
                        stage="config_publish",
                        message="publishing config requires x-config-confirm: publish",
                    )
                item = service.publish_config_version(
                    session,
                    version=version,
                    actor_user_id=auth_context.user.id,
                )
                GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER.invalidate()
            else:
                if x_config_confirm != "archive":
                    return _confirmation_error_response(
                        stage="config_archive",
                        message="archiving config requires x-config-confirm: archive",
                    )
                item = service.archive_config_version(
                    session,
                    version=version,
                    actor_user_id=auth_context.user.id,
                )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage=stage)
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage=stage)
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage=stage)
    return ConfigVersionResponse(request_id=_request_id(), data=_version_data(item))


@router.delete(
    "/config-versions/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_config_version(
    version: int,
    authorization: str | None = Header(default=None),
    x_config_confirm: str | None = Header(default=None),
) -> Response:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            auth_context = _authenticate_system_admin_config_manager(session, token)
            if x_config_confirm != "archive":
                return _confirmation_error_response(
                    stage="config_archive",
                    message="archiving config version requires x-config-confirm: archive",
                )
            service.archive_config_version(
                session,
                version=version,
                actor_user_id=auth_context.user.id,
            )
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_archive")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_archive")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_archive")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/config-validations", response_model=ConfigValidationResponse)
async def create_config_validation(
    payload: ConfigValidationRequest,
    authorization: str | None = Header(default=None),
) -> ConfigValidationResponse | JSONResponse:
    token = _extract_bearer_token(authorization)
    service = ConfigService()
    try:
        with session_scope() as session:
            _authenticate_system_admin_config_manager(session, token)
            result = service.validate_config_payload(session, config=payload.config)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_validation")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_validation")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_validation")
    return ConfigValidationResponse(request_id=_request_id(), data=_validation_data(result))


def _authenticate(session: object, token: str | None, *, required_scope: str) -> AuthContext:
    return AuthService().authenticate_access_token(
        session,
        access_token=token or "",
        required_scope=required_scope,
    )


def _authenticate_system_admin_config_manager(session: object, token: str | None) -> AuthContext:
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


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _request_id() -> str:
    request_context = get_request_context()
    return request_context.request_id if request_context else "req_unknown"


def _item_data(item: ConfigItem) -> ConfigItemData:
    return ConfigItemData(
        key=item.key,
        value_json=item.value_json,
        scope_type=item.scope_type,
        status=item.status,
        version=item.version,
    )


def _version_data(version: ConfigVersion) -> ConfigVersionData:
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


def _version_list_item_data(version: ConfigVersion) -> ConfigVersionListItemData:
    return ConfigVersionListItemData(
        version=version.version,
        status=version.status,
        risk_level=version.risk_level,
        created_by=version.created_by,
        created_at=version.created_at,
        updated_at=version.updated_at,
        activated_at=version.activated_at,
    )


def _validation_data(result: ConfigValidationResult) -> ConfigValidationData:
    return ConfigValidationData(
        valid=result.valid,
        errors=result.errors,
        warnings=result.warnings,
    )


def _auth_error_response(exc: AuthServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _config_error_response(exc: ConfigServiceError, *, stage: str) -> JSONResponse:
    return JSONResponse(
        status_code=_config_status_code(exc),
        content={
            "request_id": _request_id(),
            "error_code": exc.error_code,
            "message": exc.message,
            "stage": stage,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _confirmation_error_response(*, stage: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_428_PRECONDITION_REQUIRED,
        content={
            "request_id": _request_id(),
            "error_code": "CONFIG_CONFIRMATION_REQUIRED",
            "message": message,
            "stage": stage,
            "retryable": False,
            "details": {"required_header": "x-config-confirm"},
        },
    )


def _database_error_response(exc: SQLAlchemyError, *, stage: str) -> JSONResponse:
    original = getattr(exc, "orig", None) or exc.__cause__
    return JSONResponse(
        status_code=500,
        content={
            "request_id": _request_id(),
            "error_code": "CONFIG_DATABASE_ERROR",
            "message": "config database operation failed",
            "stage": stage,
            "retryable": True,
            "details": {
                "database_error": {
                    "type": exc.__class__.__name__,
                    "driver": original.__class__.__name__ if original is not None else None,
                }
            },
        },
    )


def _config_status_code(exc: ConfigServiceError) -> int:
    if exc.error_code in {"CONFIG_KEY_NOT_FOUND", "CONFIG_VERSION_NOT_FOUND"}:
        return 404
    if exc.error_code in {
        "CONFIG_VERSION_NOT_PUBLISHABLE",
        "CONFIG_VERSION_ARCHIVE_UNSUPPORTED",
        "CONFIG_VERSION_NOT_DISCARDABLE",
    }:
        return 409
    if exc.error_code in {
        "CONFIG_ACTIVE_CONFIG_UNAVAILABLE",
        "CONFIG_ACTIVE_MISSING",
        "CONFIG_DEPENDENCY_FAILED",
        "CONFIG_STATE_UNAVAILABLE",
        "CONFIG_VERSION_PAYLOAD_MISSING",
        "CONFIG_VERSION_UNAVAILABLE",
    }:
        return 503
    return 400
