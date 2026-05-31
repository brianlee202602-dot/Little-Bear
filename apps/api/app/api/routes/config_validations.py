"""配置校验路由。"""

from __future__ import annotations

from fastapi import APIRouter, Header
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.routes.config_shared import (
    _auth_error_response,
    _authenticate_system_admin_config_manager,
    _config_error_response,
    _database_error_response,
    _extract_bearer_token,
    _request_id,
    _validation_data,
)
from app.api.schemas.config import (
    ConfigValidationRequest,
    ConfigValidationResponse,
)
from app.db.session import session_scope
from app.modules.auth.errors import AuthServiceError
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService

router = APIRouter(prefix="/internal/v1/admin", tags=["admin-config"])


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

