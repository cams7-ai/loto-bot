from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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


class PlacedBetResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "bet_id": "64ef8f7a6f9a8f0f8f0f8f0f",
                "lottery_modality": "mega-sena",
                "selected_numbers": ["01", "02", "03", "04", "05", "06"],
                "draw_number": "1234",
                "status": "Efetivada",
                "bet_amount": "123.45",
                "purchase_number": "123456",
                "bet_date": "2026-07-12T18:08:14-03:00",
            }
        },
    )

    bet_id: str
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal = Field(examples=["123.45"])
    purchase_number: str
    bet_date: datetime
