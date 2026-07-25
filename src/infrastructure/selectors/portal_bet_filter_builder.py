from __future__ import annotations

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
        labels = {
            None: "Todas",
            LotteryModality.DIA_DE_SORTE: "Dia de Sorte",
            LotteryModality.DUPLA_SENA: "Dupla Sena",
            LotteryModality.LOTECA: "Loteca",
            LotteryModality.LOTOFACIL: "Lotofácil",
            LotteryModality.LOTOMANIA: "Lotomania",
            LotteryModality.MAIS_MILIONARIA: "+Milionária",
            LotteryModality.MEGA_SENA: "Mega-Sena",
            LotteryModality.QUINA: "Quina",
            LotteryModality.SUPER_SETE: "Super Sete",
            LotteryModality.TIMEMANIA: "Timemania",
        }
        return labels[lottery_modality]


class PortalBetFilterBuilder:
    DEFAULT_BET_TYPE = PortalBetType.ALL
    DEFAULT_DRAW_TYPE = PortalDrawType.ALL
    DEFAULT_MONTH_YEAR = PortalBetRelativePeriod.LAST_7_DAYS
    DEFAULT_STATUS = PortalBetStatus.ALL
    DEFAULT_SORT_BY = PortalBetSortOrder.DATE_DESC

    BET_TYPE_LABELS = {
        PortalBetType.ALL: "Todas",
        PortalBetType.INDIVIDUAL: "Aposta Individual",
        PortalBetType.POOL: "Aposta Bolão",
    }
    DRAW_TYPE_LABELS = {
        PortalDrawType.ALL: "Todos",
        PortalDrawType.NORMAL: "Normal",
        PortalDrawType.SPECIAL: "Especial",
    }
    RELATIVE_PERIOD_LABELS = {
        PortalBetRelativePeriod.LAST_7_DAYS: "Últimos 7 dias",
        PortalBetRelativePeriod.LAST_15_DAYS: "Últimos 15 dias",
        PortalBetRelativePeriod.LAST_30_DAYS: "Últimos 30 dias",
        PortalBetRelativePeriod.LAST_45_DAYS: "Últimos 45 dias",
        PortalBetRelativePeriod.LAST_90_DAYS: "Últimos 90 dias",
    }
    STATUS_LABELS = {
        PortalBetStatus.ALL: "Todas",
        PortalBetStatus.PAID: "Pagas",
        PortalBetStatus.EXPIRED: "Prescritas",
    }
    SORT_LABELS = {
        PortalBetSortOrder.DATE_ASC: "Data Crescente",
        PortalBetSortOrder.DATE_DESC: "Data Decrescente",
    }

    @classmethod
    def labels(cls, filters: PortalBetSearchFilters) -> dict[str, str]:
        period = filters.month_year or cls.DEFAULT_MONTH_YEAR
        return {
            "bet_type": cls.BET_TYPE_LABELS[filters.bet_type or cls.DEFAULT_BET_TYPE],
            "lottery_modality": PortalLotteryModalityBuilder.get_lottery_modality(filters.lottery_modality),
            "draw_type": cls.DRAW_TYPE_LABELS[filters.draw_type or cls.DEFAULT_DRAW_TYPE],
            "month_year": cls.period_label(period),
            "status": cls.STATUS_LABELS[filters.status or cls.DEFAULT_STATUS],
            "sort_by": cls.SORT_LABELS[filters.sort_by or cls.DEFAULT_SORT_BY],
        }

    @classmethod
    def period_label(cls, period: PortalBetRelativePeriod | PortalYearMonth) -> str:
        if isinstance(period, PortalYearMonth):
            return portal_year_month_label(period)
        return cls.RELATIVE_PERIOD_LABELS[period]
