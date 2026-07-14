from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str = "ok"
    application: str = "LotoBot"


class SessionStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str
    status: str
    executed_operation: str
    is_open: bool


class SessionControlResponse(SessionStatusResponse):
    message: str


class BetRunResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str
    status: str
    message: str
    executed_operation: str
    purchase_number: str
