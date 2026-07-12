"""DTOs da camada de aplicação."""

from __future__ import annotations

from dataclasses import dataclass
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
