from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from domain import LotteryModality, NotificationChannel


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


class CheckBetDrawsRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "required": ["lottery_modality", "start_date", "end_date"],
            "properties": {
                "lottery_modality": {"type": "string", "examples": [LotteryModality.MEGA_SENA.name, "ALL"]},
                "start_date": {"type": "string", "format": "date", "examples": ["2026-07-27"]},
                "end_date": {"type": "string", "format": "date", "examples": ["2026-07-27"]},
                "bet_type": {"type": ["string", "null"], "examples": ["INDIVIDUAL"]},
                "draw_type": {"type": ["string", "null"], "examples": ["ALL"]},
                "month_year": {"type": ["string", "null"], "examples": ["LAST_7_DAYS"]},
                "status": {"type": ["string", "null"], "examples": ["ALL"]},
            },
        },
    )

    lottery_modality: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bet_type: str | None = None
    draw_type: str | None = None
    month_year: str | None = None
    status: str | None = None


class CheckBetDrawsResponse(BaseModel):
    matched_bets: int
    notification_sent: bool
    notification_channel: NotificationChannel
    message: str


class PlacedBetResponse(BaseModel):
    bet_id: str
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: str


class PortalBetResponse(BaseModel):
    purchase_datetime: str
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
