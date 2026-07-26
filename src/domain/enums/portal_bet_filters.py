from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PortalBetType(Enum):
    ALL = "Todas"
    INDIVIDUAL = "Aposta Individual"
    POOL = "Aposta Bolão"


class PortalDrawType(Enum):
    ALL = "Todos"
    NORMAL = "Normal"
    SPECIAL = "Especial"


class PortalBetRelativePeriod(Enum):
    LAST_7_DAYS = "Últimos 7 dias"
    LAST_15_DAYS = "Últimos 15 dias"
    LAST_30_DAYS = "Últimos 30 dias"
    LAST_45_DAYS = "Últimos 45 dias"
    LAST_90_DAYS = "Últimos 90 dias"


class PortalBetStatus(Enum):
    ALL = "Todas"
    PAID = "Pagas"
    EXPIRED = "Prescritas"


class PortalBetSortOrder(Enum):
    DATE_ASC = "Data Crescente"
    DATE_DESC = "Data Decrescente"


@dataclass(frozen=True, order=True)
class PortalYearMonth:
    year: int
    month: int

    @property
    def canonical_value(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
