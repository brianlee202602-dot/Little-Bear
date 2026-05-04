from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request
from starlette.responses import JSONResponse

from app.api.schemas.setup import (
    SetupConfigValidationData,
    SetupConfigValidationResponse,
    SetupInitializationData,
    SetupInitializationResponse,
    SetupStateData,
    SetupStateResponse,
)
from app.db.session import session_scope
from app.modules.setup.initialize_service import (
    SetupInitializationError,
    SetupInitializationService,
)
from app.modules.setup.service import SetupService
from app.shared.context import get_request_context

router = APIRouter(prefix="/internal/v1", tags=["setup"])


@router.get("/setup-state", response_model=SetupStateResponse)
async def setup_state() -> SetupStateResponse:
    state = SetupService().load_state()
    request_context = get_request_context()
    request_id = request_context.request_id if request_context else "req_unknown"
    return SetupStateResponse(
        request_id=request_id,
        data=SetupStateData.model_validate(state.to_response_data()),
    )


@router.post("/setup-config-validations", response_model=SetupConfigValidationResponse)
async def setup_config_validations(request: Request) -> SetupConfigValidationResponse:
    payload = await request.json()
    request_id = _request_id()
    validation = SetupInitializationService().validate_payload(_ensure_payload_object(payload))
    return SetupConfigValidationResponse(
        request_id=request_id,
        data=SetupConfigValidationData(
            valid=validation.valid,
            errors=validation.errors,
            warnings=validation.warnings,
        ),
    )


@router.put("/setup-initialization", response_model=SetupInitializationResponse)
async def setup_initialization(
    request: Request,
    x_setup_confirm: str | None = Header(default=None),
) -> SetupInitializationResponse | JSONResponse:
    request_id = _request_id()
    if x_setup_confirm != "initialize":
        return _error_response(
            request_id,
            "SETUP_CONFIRMATION_REQUIRED",
            "setup initialization requires x-setup-confirm: initialize",
            status_code=428,
        )

    payload = _ensure_payload_object(await request.json())
    service = SetupInitializationService()
    try:
        with session_scope() as session:
            result = service.initialize(session, payload)
    except SetupInitializationError as exc:
        return _error_response(
            request_id,
            exc.error_code,
            exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return SetupInitializationResponse(
        request_id=request_id,
        data=SetupInitializationData(
            initialized=result.initialized,
            active_config_version=result.active_config_version,
            enterprise_id=result.enterprise_id,
            admin_user_id=result.admin_user_id,
        ),
    )


def _request_id() -> str:
    request_context = get_request_context()
    return request_context.request_id if request_context else "req_unknown"


def _ensure_payload_object(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _error_response(
    request_id: str,
    error_code: str,
    message: str,
    *,
    status_code: int,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": request_id,
            "error_code": error_code,
            "message": message,
            "stage": "setup_initialization",
            "retryable": False,
            "details": details or {},
        },
    )
