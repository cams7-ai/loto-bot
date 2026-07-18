"""DTOs da camada de aplicação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from domain import LotteryModality, Operation


@dataclass(frozen=True)
class SessionStatusResult:
    session_id: UUID
    status: str
    executed_operation: Operation
    is_open: bool


@dataclass(frozen=True)
class AutomationRunResult:
    session_id: UUID
    status: str
    message: str
    executed_operation: Operation
    purchase_number: str | None = None


@dataclass(frozen=True)
class BetResult:
    numbers: list[str]
    draw: str
    status: str
    amount: Decimal | None


@dataclass(frozen=True)
class PurchaseResult:
    lottery_modality: str | None
    bets: list[BetResult]
    purchase_number: str
    purchase_datetime: datetime
    total_purchase: Decimal | None
    total_bets_effective: Decimal | None


@dataclass(frozen=True)
class BetSearchFilters:
    lottery_modality: LotteryModality | None = None
    draw_number: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass(frozen=True)
class PlacedBetResult:
    bet_id: str
    lottery_modality: LotteryModality
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime
