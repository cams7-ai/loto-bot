from __future__ import annotations

from typing import Protocol

from application.dto import PortalBetResult, PortalBetSearchFilters
from domain import AutomationSession


class PortalBetQueryPort(Protocol):
    def find_all(self, session: AutomationSession, filters: PortalBetSearchFilters) -> list[PortalBetResult]:
        """Busca no portal as apostas que atendem aos filtros."""
