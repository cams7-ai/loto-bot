from __future__ import annotations

from datetime import date

import pytest

from application import ListPortalBetsUseCase, PortalBetFiltersValidationError
from domain import AutomationSession

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


class FixedClock:
    def today(self) -> date:
        return date(2026, 7, 24)


class RecordingPortalBetQuery:
    def __init__(self) -> None:
        self.called = False

    def find_all(self, session, filters):
        self.called = True
        return []


def test_list_portal_bets_accumulates_all_filter_validation_messages():
    session = AutomationSession()
    session.mark_open()
    portal_bets = RecordingPortalBetQuery()
    use_case = ListPortalBetsUseCase(session=session, portal_bets=portal_bets, clock=FixedClock())

    with pytest.raises(PortalBetFiltersValidationError) as captured:
        use_case.run(
            bet_type="abc",
            lottery_modality="abc",
            draw_type="abc",
            month_year="abc",
            status="abc",
            sort_by="abc",
        )

    assert [detail.to_dict() for detail in captured.value.details] == EXPECTED_FILTER_DETAILS
    assert portal_bets.called is False


def test_list_portal_bets_validates_filters_before_browser_session_state():
    session = AutomationSession()
    portal_bets = RecordingPortalBetQuery()
    use_case = ListPortalBetsUseCase(session=session, portal_bets=portal_bets, clock=FixedClock())

    with pytest.raises(PortalBetFiltersValidationError) as captured:
        use_case.run(
            bet_type="abc",
            lottery_modality="abc",
            draw_type="abc",
            month_year="abc",
            status="abc",
            sort_by="abc",
        )

    assert [detail.to_dict() for detail in captured.value.details] == EXPECTED_FILTER_DETAILS
    assert portal_bets.called is False
