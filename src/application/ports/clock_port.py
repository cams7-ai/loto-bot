from __future__ import annotations

from datetime import date
from typing import Protocol


class ClockPort(Protocol):
    def today(self) -> date:
        """Retorna a data corrente no timezone configurado pela implementação."""
