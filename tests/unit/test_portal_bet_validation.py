from __future__ import annotations

from datetime import date

import pytest

from api.parsers import BetRequestParser
from application import PortalBetFiltersValidationError, PortalBetSearchFilters
from domain import (
    LotteryModality,
    PortalBetSortOrder,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
    PortalYearMonth,
)

EXPECTED_FILTER_DETAILS = [
    {
        "field": "bet_type",
        "rejected_value": "abc",
        "allowed_values": ["ALL", "INDIVIDUAL", "POOL"],
        "message": "Valor inválido.",
    },
    {
        "field": "lottery_modality",
        "rejected_value": "abc",
        "allowed_values": [
            "ALL",
            "MEGA_SENA",
            "QUINA",
            "QUINA_ESPECIAL",
            "LOTECA",
            "LOTECA_ESPECIAL",
            "LOTOFACIL",
            "LOTOFACIL_ESPECIAL",
            "MAIS_MILIONARIA",
            "LOTOMANIA",
            "TIMEMANIA",
            "DUPLA_SENA",
            "DIA_DE_SORTE",
            "SUPER_SETE",
        ],
        "message": "Valor inválido.",
    },
    {
        "field": "draw_type",
        "rejected_value": "abc",
        "allowed_values": ["ALL", "NORMAL", "SPECIAL"],
        "message": "Valor inválido.",
    },
    {
        "field": "month_year",
        "rejected_value": "abc",
        "message": "Valor inválido. Utilize o formato YYYY-MM ou um período relativo válido.",
    },
    {
        "field": "status",
        "rejected_value": "abc",
        "allowed_values": ["ALL", "PAID", "EXPIRED"],
        "message": "Valor inválido.",
    },
    {
        "field": "sort_by",
        "rejected_value": "abc",
        "allowed_values": ["DATE_ASC", "DATE_DESC"],
        "message": "Valor inválido.",
    },
]


def test_parse_portal_bet_filters_accumulates_all_validation_messages():
    with pytest.raises(PortalBetFiltersValidationError) as captured:
        BetRequestParser.parse_portal_bet_filters(
            today=date(2026, 7, 24),
            bet_type="abc",
            lottery_modality="abc",
            draw_type="abc",
            month_year="abc",
            status="abc",
            sort_by="abc",
        )

    assert [detail.to_dict() for detail in captured.value.details] == EXPECTED_FILTER_DETAILS


def test_parse_portal_bet_filters_returns_domain_filters():
    filters = BetRequestParser.parse_portal_bet_filters(
        today=date(2026, 7, 24),
        bet_type="INDIVIDUAL",
        lottery_modality="MEGA_SENA",
        draw_type="NORMAL",
        month_year="2026-07",
        status="PAID",
        sort_by="DATE_DESC",
    )

    assert filters == PortalBetSearchFilters(
        bet_type=PortalBetType.INDIVIDUAL,
        lottery_modality=LotteryModality.MEGA_SENA,
        draw_type=PortalDrawType.NORMAL,
        month_year=PortalYearMonth(2026, 7),
        status=PortalBetStatus.PAID,
        sort_by=PortalBetSortOrder.DATE_DESC,
        has_explicit_filters=True,
    )
