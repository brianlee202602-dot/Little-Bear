"""管理后台通用响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AcceptedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    job_id: str | None = None


class AcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: AcceptedData
