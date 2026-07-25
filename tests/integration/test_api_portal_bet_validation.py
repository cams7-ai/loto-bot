from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from api.dependencies import get_container
from api.server import app
from application import PortalBetFiltersValidationError

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


class InvalidPortalBetFiltersUseCase:
    def run(self, **filters):
        raise PortalBetFiltersValidationError(EXPECTED_FILTER_MESSAGES)


@pytest.mark.anyio
async def test_list_portal_bets_returns_all_filter_validation_messages():
    container = SimpleNamespace(list_portal_bets=InvalidPortalBetFiltersUseCase())
    app.dependency_overrides[get_container] = lambda: container
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/bets",
                params={
                    "bet_type": "all1",
                    "lottery_modality": "all1",
                    "draw_type": "all1",
                    "month_year": "last-91-days",
                    "status": "all1",
                    "sort_by": "date-desc1",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "status_code": 400,
            "code": "REQUISICAO_INVALIDA",
            "messages": EXPECTED_FILTER_MESSAGES,
        }
    }
