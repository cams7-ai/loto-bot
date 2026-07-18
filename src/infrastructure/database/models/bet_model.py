"""Modelo MongoDB para apostas realizadas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from beanie import Document, PydanticObjectId
from bson.decimal128 import Decimal128
from pydantic import field_validator

from application.dto import BetResult, PlacedBetResult, PurchaseResult
from domain import LotteryModality


class BetModel(Document):
    bet_id: PydanticObjectId
    lottery_modality: LotteryModality
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime

    class Settings:
        name = "bets"
        indexes = [
            [("bet_id", 1)],
            [("lottery_modality", 1), ("bet_date", -1)],
            [("draw_number", 1)],
            [("bet_date", -1)],
        ]

    @field_validator("bet_amount", mode="before")
    @classmethod
    def parse_decimal128(cls, value: object) -> object:
        if isinstance(value, Decimal128):
            return value.to_decimal()
        return value

    @classmethod
    def from_result(
        cls,
        *,
        lottery_modality: LotteryModality,
        bet: BetResult,
        purchase: PurchaseResult,
    ) -> BetModel:
        if bet.amount is None:
            raise ValueError("Valor da aposta é obrigatório para persistência.")

        return cls(
            bet_id=PydanticObjectId(),
            lottery_modality=lottery_modality,
            selected_numbers=bet.numbers,
            draw_number=bet.draw,
            status=bet.status,
            bet_amount=bet.amount,
            purchase_number=purchase.purchase_number,
            bet_date=purchase.purchase_datetime,
        )

    def to_search_result(self) -> PlacedBetResult:
        return PlacedBetResult(
            bet_id=str(self.bet_id),
            lottery_modality=self.lottery_modality,
            selected_numbers=self.selected_numbers,
            draw_number=self.draw_number,
            status=self.status,
            bet_amount=self.bet_amount,
            purchase_number=self.purchase_number,
            bet_date=self.bet_date,
        )
