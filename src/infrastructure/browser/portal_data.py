from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Bet:
    numbers: list[str]
    draw: str
    status: str
    amount: str


@dataclass(frozen=True, slots=True)
class PurchaseDetails:
    number: str
    status: str
    date: str
    time: str


@dataclass(frozen=True, slots=True)
class PurchaseTotals:
    total_purchase: str
    total_bets_in_processing: str
    total_bets_effective: str
    total_bets_not_effective: str
    total_refunded: str
    total_in_refund: str
