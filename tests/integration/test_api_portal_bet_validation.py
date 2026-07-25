from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from api.dependencies import get_container
from api.server import app
from application import PortalBetFiltersValidationError, ValidationErrorDetail
from domain.enums import Operation

EXPECTED_FILTER_DETAILS = [
    ValidationErrorDetail("bet_type", "all1", "Valor inválido.", ["all", "individual", "pool"]),
    ValidationErrorDetail(
        "lottery_modality",
        "all1",
        "Valor inválido.",
        [
            "all",
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
    ),
    ValidationErrorDetail("draw_type", "all1", "Valor inválido.", ["all", "normal", "special"]),
    ValidationErrorDetail(
        "month_year",
        "last-91-days",
        "Valor inválido. Utilize o formato YYYY-MM ou um período relativo válido.",
    ),
    ValidationErrorDetail("status", "all1", "Valor inválido.", ["all", "paid", "expired"]),
    ValidationErrorDetail("sort_by", "date-desc1", "Valor inválido.", ["date-asc", "date-desc"]),
]


class InvalidPortalBetFiltersUseCase:
    def run(self, **filters):
        raise PortalBetFiltersValidationError(EXPECTED_FILTER_DETAILS)


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
    error = response.json()["error"]
    assert error["status_code"] == 400
    assert error["code"] == "REQUISICAO_INVALIDA"
    assert error["message"] == "Parâmetros inválidos"
    assert error["details"] == [detail.to_dict() for detail in EXPECTED_FILTER_DETAILS]
    assert "timestamp" in error
    assert "messages" not in error
    assert "fields" not in error


@pytest.mark.anyio
async def test_list_portal_bets_validates_query_before_closed_browser_session():
    container = get_container()
    container.session.mark_closed(Operation.END_SESSION)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/bets",
            params={
                "bet_type": "abc",
                "lottery_modality": "abc",
                "draw_type": "abc",
                "month_year": "abc",
                "status": "abc",
                "sort_by": "abc",
            },
        )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["status_code"] == 400
    assert error["code"] == "REQUISICAO_INVALIDA"
    assert error["message"] == "Parâmetros inválidos"
    assert [detail["field"] for detail in error["details"]] == [
        "bet_type",
        "lottery_modality",
        "draw_type",
        "month_year",
        "status",
        "sort_by",
    ]
