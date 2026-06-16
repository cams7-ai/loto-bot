from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    application: str = "LotoBot"


class SessionStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    status: str
    executed_operation: str = Field(alias="executedOperation")
    is_open: bool = Field(alias="isOpen")


class SessionControlResponse(SessionStatusResponse):
    message: str


class BetRunResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    status: str
    message: str
    executed_operation: str = Field(alias="executedOperation")
    tracking_code: str | None = Field(default=None, alias="codigoAcompanhamento")
