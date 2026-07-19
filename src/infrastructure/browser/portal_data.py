from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain import BrlCurrencyFormatter
from shared import parse_sao_paulo_datetime


class PortalDataFormatter:
    @staticmethod
    def parse_purchase_datetime(
        date_value: str,
        time_value: str,
    ) -> datetime:
        return parse_sao_paulo_datetime(date_value, time_value)


@dataclass(frozen=True, slots=True)
class Bet:
    numbers: list[str]
    draw: str
    status: str
    amount: Decimal | None

    def __init__(
        self,
        *,
        numbers: list[str],
        draw: str,
        status: str,
        amount: str,
    ) -> None:
        object.__setattr__(self, "numbers", numbers)
        object.__setattr__(self, "draw", draw)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "amount", BrlCurrencyFormatter.parse_brl_currency(amount))


@dataclass(frozen=True, slots=True, init=False)
class PurchaseDetails:
    number: str
    status: str
    bet_date: datetime

    def __init__(
        self,
        *,
        number: str,
        status: str,
        date: str,
        time: str,
    ) -> None:
        object.__setattr__(self, "number", number)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "bet_date", PortalDataFormatter.parse_purchase_datetime(date, time))


@dataclass(frozen=True, slots=True)
class PurchaseTotals:
    total_purchase: Decimal | None
    total_bets_in_processing: Decimal | None
    total_bets_effective: Decimal | None
    total_bets_not_effective: Decimal | None
    total_refunded: Decimal | None
    total_in_refund: Decimal | None

    def __init__(
        self,
        *,
        total_purchase: str,
        total_bets_in_processing: str,
        total_bets_effective: str,
        total_bets_not_effective: str,
        total_refunded: str,
        total_in_refund: str,
    ) -> None:
        object.__setattr__(self, "total_purchase", BrlCurrencyFormatter.parse_brl_currency(total_purchase))
        object.__setattr__(
            self,
            "total_bets_in_processing",
            BrlCurrencyFormatter.parse_brl_currency(total_bets_in_processing),
        )
        object.__setattr__(self, "total_bets_effective", BrlCurrencyFormatter.parse_brl_currency(total_bets_effective))
        object.__setattr__(
            self,
            "total_bets_not_effective",
            BrlCurrencyFormatter.parse_brl_currency(total_bets_not_effective),
        )
        object.__setattr__(self, "total_refunded", BrlCurrencyFormatter.parse_brl_currency(total_refunded))
        object.__setattr__(self, "total_in_refund", BrlCurrencyFormatter.parse_brl_currency(total_in_refund))
