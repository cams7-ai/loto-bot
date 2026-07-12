from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as DateTime
from decimal import Decimal
from zoneinfo import ZoneInfo

from shared import SAO_PAULO_TIMEZONE


class PortalDataFormatter:
    @staticmethod
    def parse_purchase_datetime(
        date_value: str,
        time_value: str,
    ) -> DateTime:
        return DateTime.strptime(
            f"{date_value} {time_value}",
            "%d/%m/%Y %H:%M:%S",
        ).replace(tzinfo=ZoneInfo(SAO_PAULO_TIMEZONE))

    @staticmethod
    def parse_brl_currency(value: str) -> Decimal | None:
        if not value.strip():
            return None

        normalized_value = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return Decimal(normalized_value)

    @staticmethod
    def format_brl_currency(value: Decimal | None) -> str:
        amount = value or Decimal("0")
        formatted_amount = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R$ {formatted_amount}"


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
        object.__setattr__(self, "amount", PortalDataFormatter.parse_brl_currency(amount))


@dataclass(frozen=True, slots=True, init=False)
class PurchaseDetails:
    number: str
    status: str
    datetime: DateTime

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
        object.__setattr__(self, "datetime", PortalDataFormatter.parse_purchase_datetime(date, time))


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
        object.__setattr__(self, "total_purchase", PortalDataFormatter.parse_brl_currency(total_purchase))
        object.__setattr__(
            self,
            "total_bets_in_processing",
            PortalDataFormatter.parse_brl_currency(total_bets_in_processing),
        )
        object.__setattr__(self, "total_bets_effective", PortalDataFormatter.parse_brl_currency(total_bets_effective))
        object.__setattr__(
            self,
            "total_bets_not_effective",
            PortalDataFormatter.parse_brl_currency(total_bets_not_effective),
        )
        object.__setattr__(self, "total_refunded", PortalDataFormatter.parse_brl_currency(total_refunded))
        object.__setattr__(self, "total_in_refund", PortalDataFormatter.parse_brl_currency(total_in_refund))
