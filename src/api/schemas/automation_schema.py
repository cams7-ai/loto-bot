from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from domain import LotteryModality


class HealthResponse(BaseModel):
    status: str = "ok"
    application: str = "LotoBot"


class OperationResponse(BaseModel):
    session_id: str
    status: str
    executed_operation: str


class SessionStatusResponse(OperationResponse):
    model_config = ConfigDict(populate_by_name=True)

    is_open: bool


class SessionControlResponse(OperationResponse):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    is_open: bool


class BetRunResponse(OperationResponse):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    purchase_number: str | None


class BetRunRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "selected_lottery_modality": LotteryModality.MEGA_SENA.name,
            }
        },
    )

    selected_lottery_modality: str | None = Field(
        default=None,
        description=(
            "Modalidade opcional para execução da aposta. "
            "Se não informada, "
            "a aplicação utilizará o valor definido na variável de ambiente SELECTED_LOTTERY_MODALITY."
        ),
        examples=[LotteryModality.MEGA_SENA.name],
    )


class PlacedBetResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "bet_id": "64ef8f7a6f9a8f0f8f0f8f0f",
                "lottery_modality": LotteryModality.MEGA_SENA.name,
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
    lottery_modality: str | None
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal = Field(examples=["123.45"])
    purchase_number: str
    bet_date: datetime


class PortalBetResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "purchase_datetime": "2026-07-19T12:33:09-03:00",
                "lottery_modality": LotteryModality.MEGA_SENA.name,
                "selected_numbers": ["09", "18", "33", "40", "47", "53"],
                "draw_number": "3034",
                "status": "Aposta não premiada",
            }
        },
    )

    purchase_datetime: datetime | None
    lottery_modality: str | None
    selected_numbers: list[str]
    draw_number: str
    status: str
