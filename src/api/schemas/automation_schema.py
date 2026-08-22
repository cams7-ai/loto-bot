from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from domain import LotteryModality


class HealthResponse(BaseModel):
    status: str = "ok"
    application: str = "LotoBot"


class OperationResponse(BaseModel):
    session_id: str
    status: str
    executed_operation: str


class SessionStatusResponse(OperationResponse):
    is_open: bool


class SessionControlResponse(OperationResponse):
    message: str
    is_open: bool


class BetRunResponse(OperationResponse):
    message: str
    purchase_number: str


class BetRunRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "selected_lottery_modality": LotteryModality.MEGA_SENA.name,
            }
        },
    )

    selected_lottery_modality: str | None


class PlacedBetResponse(BaseModel):
    bet_id: str
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime


class PortalBetResponse(BaseModel):
    purchase_datetime: datetime
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
