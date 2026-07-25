from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PortalBetType(Enum):
    ALL = "all"
    INDIVIDUAL = "individual"
    POOL = "pool"


class PortalDrawType(Enum):
    ALL = "all"
    NORMAL = "normal"
    SPECIAL = "special"


class PortalBetRelativePeriod(Enum):
    LAST_7_DAYS = "last-7-days"
    LAST_15_DAYS = "last-15-days"
    LAST_30_DAYS = "last-30-days"
    LAST_45_DAYS = "last-45-days"
    LAST_90_DAYS = "last-90-days"


class PortalBetStatus(Enum):
    ALL = "all"
    PAID = "paid"
    EXPIRED = "expired"


class PortalBetSortOrder(Enum):
    DATE_ASC = "date-asc"
    DATE_DESC = "date-desc"


@dataclass(frozen=True, order=True)
class PortalYearMonth:
    year: int
    month: int

    @property
    def canonical_value(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
