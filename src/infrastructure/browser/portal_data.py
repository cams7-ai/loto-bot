from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as DateTime
from zoneinfo import ZoneInfo

from shared import SAO_PAULO_TIMEZONE


def purchase_datetime(
    purchase_date: str,
    purchase_time: str,
) -> DateTime:
    return DateTime.strptime(
        f"{purchase_date} {purchase_time}",
        "%d/%m/%Y %H:%M:%S",
    ).replace(tzinfo=ZoneInfo(SAO_PAULO_TIMEZONE))


@dataclass(frozen=True, slots=True)
class Bet:
    numbers: list[str]
    draw: str
    status: str
    amount: str


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
        object.__setattr__(self, "datetime", purchase_datetime(date, time))


@dataclass(frozen=True, slots=True)
class PurchaseTotals:
    total_purchase: str
    total_bets_in_processing: str
    total_bets_effective: str
    total_bets_not_effective: str
    total_refunded: str
    total_in_refund: str
