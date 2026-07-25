from __future__ import annotations

from datetime import date

import pytest

from application import ListPortalBetsUseCase, PortalBetFiltersValidationError
from domain import AutomationSession

EXPECTED_FILTER_MESSAGES = [
    "Parâmetro bet_type inválido. Valores permitidos: all, individual, pool.",
    (
        "Parâmetro lottery_modality inválido. Valores permitidos: all, MEGA_SENA, QUINA, "
        "QUINA_ESPECIAL, LOTECA, LOTECA_ESPECIAL, LOTOFACIL, LOTOFACIL_ESPECIAL, "
        "MAIS_MILIONARIA, LOTOMANIA, TIMEMANIA, DUPLA_SENA, DIA_DE_SORTE, SUPER_SETE."
    ),
    "Parâmetro draw_type inválido. Valores permitidos: all, normal, special.",
    "Parâmetro month_year inválido. Use YYYY-MM ou um período relativo permitido.",
    "Parâmetro status inválido. Valores permitidos: all, paid, expired.",
    "Parâmetro sort_by inválido. Valores permitidos: date-asc, date-desc.",
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
            bet_type="all1",
            lottery_modality="all1",
            draw_type="all1",
            month_year="last-91-days",
            status="all1",
            sort_by="date-desc1",
        )

    assert captured.value.messages == EXPECTED_FILTER_MESSAGES
    assert portal_bets.called is False
