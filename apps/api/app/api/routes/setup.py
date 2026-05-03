from __future__ import annotations

from fastapi import APIRouter

from app.modules.setup.service import SetupService

router = APIRouter(prefix="/internal/v1", tags=["setup"])


@router.get("/setup-state")
async def setup_state() -> dict[str, object]:
    return await SetupService().get_state()
