"""DTOs da camada de aplicação."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SessionStatusResult:
    session_id: UUID
    status: str
    executed_operation: str
    is_open: bool


@dataclass(frozen=True)
class AutomationRunResult:
    session_id: UUID
    status: str
    message: str
    executed_operation: str
    tracking_code: str | None = None
