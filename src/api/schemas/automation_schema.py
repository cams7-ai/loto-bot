from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain import SUPPORTED_BET_RUN_LOTTERY_MODALITIES, LotteryModality


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


class BetRunRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "selected_lottery_modality": LotteryModality.MEGA_SENA.name,
            }
        },
    )

    selected_lottery_modality: LotteryModality | None = Field(
        default=None,
        description=(
            "Modalidade opcional para executar a aposta. Quando omitida, a aplicação usa SELECTED_LOTTERY_MODALITY."
        ),
        examples=[LotteryModality.MEGA_SENA.name],
    )

    @field_validator("selected_lottery_modality", mode="before")
    @classmethod
    def parse_lottery_modality_name(cls, value: object) -> object:
        if isinstance(value, str) and value in LotteryModality.__members__:
            return LotteryModality[value]
        return value

    @field_validator("selected_lottery_modality")
    @classmethod
    def validate_supported_lottery_modality(cls, value: LotteryModality | None) -> LotteryModality | None:
        if value is not None and value not in SUPPORTED_BET_RUN_LOTTERY_MODALITIES:
            supported = ", ".join(lottery_modality.name for lottery_modality in SUPPORTED_BET_RUN_LOTTERY_MODALITIES)
            raise ValueError(f"Modalidade de loteria inválida. Use uma das seguintes: {supported}.")
        return value


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
