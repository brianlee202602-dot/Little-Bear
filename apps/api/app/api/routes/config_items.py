"""配置项路由。"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.routes.config_shared import (
    _auth_error_response,
    _authenticate,
    _authenticate_system_admin_config_manager,
    _config_error_response,
    _confirmation_error_response,
    _database_error_response,
    _extract_bearer_token,
    _item_data,
    _item_list_item_data,
    _request_id,
)
from app.api.schemas.common import PaginationData
from app.api.schemas.config import (
    ConfigItemListResponse,
    ConfigItemResponse,
    ConfigPutRequest,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import HIGH_RISK_CONFIG_KEYS, ConfigService

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
            result = service.list_config_items(session, page=page, page_size=page_size)
    except AuthServiceError as exc:
        return _auth_error_response(exc, stage="config_list")
    except ConfigServiceError as exc:
        return _config_error_response(exc, stage="config_list")
    except SQLAlchemyError as exc:
        return _database_error_response(exc, stage="config_list")

    return ConfigItemListResponse(
        request_id=_request_id(),
        data=[_item_list_item_data(item) for item in result.items],
        pagination=PaginationData(page=page, page_size=page_size, total=result.total),
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

