"""Entidade de sessão da automação."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4
from domain.entities.operation import Operation

class AutomationStatus(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    RUNNING = "running"
    FAILED = "failed"
    FINISHED = "finished"

@dataclass
class AutomationSession:
    id: UUID = field(default_factory=uuid4)
    state: UUID = field(default_factory=uuid4)
    nonce: UUID = field(default_factory=uuid4)
    tab_id: str = ""
    execution: str = ""
    executed_operation: Operation = Operation.UNKNOWN_OPERATION
    status: AutomationStatus = AutomationStatus.CLOSED
    valid_code: str | None = None
    whatsapp_enabled: bool = False
    tracking_code: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in {
            AutomationStatus.OPEN,
            AutomationStatus.RUNNING,
            AutomationStatus.FINISHED,
        }

    def mark_open(self, tab_id: str) -> None:
        self.executed_operation = Operation.START_SESSION
        self.status = AutomationStatus.OPEN
        self.tab_id = tab_id

    def mark_running(self, operation: Operation) -> None:
        self.executed_operation = operation
        self.status = AutomationStatus.RUNNING

    def mark_finished(self, tracking_code: str | None = None) -> None:
        self.status = AutomationStatus.FINISHED
        self.tracking_code = tracking_code

    def mark_failed(self, operation: Operation) -> None:
        self.executed_operation = operation
        self.status = AutomationStatus.FAILED

    def mark_closed(self) -> None:
        self.executed_operation = Operation.END_SESSION
        self.status = AutomationStatus.CLOSED
        self.whatsapp_enabled = False
