"""配置版本路由。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.responses import JSONResponse, Response

from app.api.routes.config_shared import (
    _auth_error_response,
    _authenticate,
    _authenticate_system_admin_config_manager,
    _config_error_response,
    _confirmation_error_response,
    _database_error_response,
    _extract_bearer_token,
    _request_id,
    _version_data,
    _version_list_item_data,
)
from app.api.schemas.common import PaginationData
from app.api.schemas.config import (
    ConfigVersionCreateRequest,
    ConfigVersionListResponse,
    ConfigVersionPatchRequest,
    ConfigVersionPutRequest,
    ConfigVersionResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.runtime import GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-config"])


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

