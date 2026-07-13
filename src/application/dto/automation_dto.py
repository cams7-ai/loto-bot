"""DTOs da camada de aplicação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from domain import Operation


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
    tracking_code: str | None = None


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
    purchase_details_number: str
    purchase_details_datetime: datetime
    total_purchase: Decimal | None
    total_bets_effective: Decimal | None
