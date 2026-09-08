from __future__ import annotations

from application import LotteryModalityBuilder
from application.dto import PortalBetSearchFilters
from application.services.portal_bet_filter_catalog import portal_year_month_label
from domain import LotteryModality
from domain.enums import (
    PortalBetRelativePeriod,
    PortalBetSortOrder,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
    PortalYearMonth,
)


class PortalLotteryModalityBuilder:
    @staticmethod
    def get_lottery_modality(lottery_modality: LotteryModality | None) -> str:
        return LotteryModalityBuilder.portal_filter_label(lottery_modality)


class PortalBetFilterBuilder:
    @classmethod
    def labels(cls, filters: PortalBetSearchFilters) -> dict[str, str]:
        period = filters.month_year or PortalBetRelativePeriod.LAST_7_DAYS
        return {
            "bet_type": filters.bet_type.value if filters.bet_type else PortalBetType.ALL.value,
            "lottery_modality": PortalLotteryModalityBuilder.get_lottery_modality(filters.lottery_modality),
            "draw_type": filters.draw_type.value if filters.draw_type else PortalDrawType.ALL.value,
            "month_year": cls.period_label(period),
            "status": filters.status.value if filters.status else PortalBetStatus.ALL.value,
            "sort_by": filters.sort_by.value if filters.sort_by else PortalBetSortOrder.DATE_DESC.value,
        }

    @classmethod
    def period_label(cls, period: PortalBetRelativePeriod | PortalYearMonth) -> str:
        if isinstance(period, PortalYearMonth):
            return portal_year_month_label(period)
        return period.value
