from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx
import pytest

from api.dependencies import get_container
from api.server import app
from application import AutomationRunResult, PlacedBetResult, SessionStatusResult
from domain import BrowserSessionClosedError, BrowserSessionOpenError, LotteryModality, Operation


class FakeSessionControl:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        return SessionStatusResult("00000000-0000-0000-0000-000000000001", "open", Operation.START_SESSION, True)

    def stop(self):
        self.stopped = True
        return SessionStatusResult("00000000-0000-0000-0000-000000000001", "closed", Operation.END_SESSION, False)

    def status(self):
        return SessionStatusResult("00000000-0000-0000-0000-000000000001", "closed", Operation.UNKNOWN_OPERATION, False)


class FakeRunBetFlow:
    def run(self):
        return AutomationRunResult(
            session_id="00000000-0000-0000-0000-000000000001",
            status="failed",
            message="A confirmação de pagamento real está desabilitada.",
            executed_operation=Operation.CONFIRM_PAYMENT,
            purchase_number="",
        )


class FakeListPlacedBets:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, **filters):
        self.calls.append(filters)
        return [placed_bet_result(bet_amount=Decimal("6"))]


class FakeGetPlacedBet:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, *, bet_id: str):
        self.calls.append(bet_id)
        if bet_id == "invalid":
            raise ValueError("Identificador da aposta inválido.")
        if bet_id == "missing":
            return None
        return placed_bet_result(bet_id=bet_id)


class FakeContainer:
    def __init__(self) -> None:
        self.session_control = FakeSessionControl()
        self.run_bet_flow = FakeRunBetFlow()
        self.list_placed_bets = FakeListPlacedBets()
        self.get_placed_bet = FakeGetPlacedBet()


class FailingSessionControl(FakeSessionControl):
    def start(self):
        raise BrowserSessionOpenError(Operation.START_SESSION)

    def stop(self):
        raise BrowserSessionClosedError(Operation.END_SESSION)


def placed_bet_result(
    bet_id: str = "64ef8f7a6f9a8f0f8f0f8f0f",
    bet_amount: Decimal = Decimal("5.00"),
) -> PlacedBetResult:
    return PlacedBetResult(
        bet_id=bet_id,
        lottery_modality=LotteryModality.MEGA_SENA,
        selected_numbers=["01", "02", "03", "04", "05", "06"],
        draw_number="1234",
        status="Efetivada",
        bet_amount=bet_amount,
        purchase_number="123456",
        bet_date=datetime(2026, 7, 12, 18, 8, 14),
    )


@pytest.fixture(autouse=True)
def override_container():
    fake = FakeContainer()
    app.dependency_overrides[get_container] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_health_and_openapi():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health = await client.get("/health")
        openapi = await client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "application": "LotoBot"}
    assert openapi.status_code == 200
    assert "/api/v1/bets/run" in openapi.json()["paths"]
    assert "/api/v1/history/bets" in openapi.json()["paths"]
    assert "/api/v1/history/bets/{bet_id}" in openapi.json()["paths"]


@pytest.mark.anyio
async def test_openapi_error_responses_match_route_failures():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    paths = response.json()["paths"]

    assert set(paths["/api/v1/sessions/start"]["get"]["responses"]) == {
        "200",
        "400",
        "409",
        "500",
        "502",
        "503",
    }
    assert set(paths["/api/v1/sessions/stop"]["get"]["responses"]) == {"200", "409", "500"}
    assert set(paths["/api/v1/sessions/status"]["get"]["responses"]) == {"200", "500"}
    assert set(paths["/api/v1/bets/run"]["get"]["responses"]) == {
        "200",
        "403",
        "409",
        "429",
        "500",
        "502",
        "503",
    }
    assert set(paths["/api/v1/history/bets"]["get"]["responses"]) == {"200", "400", "500"}
    assert set(paths["/api/v1/history/bets/{bet_id}"]["get"]["responses"]) == {"200", "400", "404", "500"}

    start_409_examples = paths["/api/v1/sessions/start"]["get"]["responses"]["409"]["content"][
        "application/json; charset=utf-8"
    ]["examples"]
    run_409_examples = paths["/api/v1/bets/run"]["get"]["responses"]["409"]["content"][
        "application/json; charset=utf-8"
    ]["examples"]

    assert set(start_409_examples) == {"SESSAO_JA_ABERTA", "SESSAO_FECHADA"}
    assert set(run_409_examples) == {
        "SESSAO_FECHADA",
        "REGISTRO_APOSTA_INDIVIDUAL_FECHADO",
        "APOSTA_TEMPORARIAMENTE_DESABILITADA",
    }
    assert start_409_examples["SESSAO_JA_ABERTA"]["value"]["error"]["status_code"] == 409


@pytest.mark.anyio
async def test_session_routes_delegate_to_use_case(override_container):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        start = await client.get("/api/v1/sessions/start")
        status = await client.get("/api/v1/sessions/status")
        stop = await client.get("/api/v1/sessions/stop")

    assert start.status_code == 200
    assert start.json()["is_open"] is True
    assert start.json()["message"] == "Sessão de navegador iniciada com sucesso"
    assert status.json()["status"] == "closed"
    assert stop.json()["is_open"] is False
    assert override_container.session_control.started is True
    assert override_container.session_control.stopped is True


@pytest.mark.anyio
async def test_run_bet_route_returns_failed_flow_without_real_network():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/bets/run")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["executed_operation"] == "Confirma o pagamento"


@pytest.mark.anyio
async def test_list_placed_bets_route_returns_serialized_bets(override_container):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/history/bets")

    assert response.status_code == 200
    assert response.json() == [
        {
            "bet_id": "64ef8f7a6f9a8f0f8f0f8f0f",
            "lottery_modality": "mega-sena",
            "selected_numbers": ["01", "02", "03", "04", "05", "06"],
            "draw_number": "1234",
            "status": "Efetivada",
            "bet_amount": "6.00",
            "purchase_number": "123456",
            "bet_date": "2026-07-12T18:08:14",
        }
    ]
    assert override_container.list_placed_bets.calls[0] == {
        "lottery_modality": None,
        "draw_number": None,
        "start_date": None,
        "end_date": None,
    }


@pytest.mark.anyio
async def test_list_placed_bets_route_forwards_query_filters(override_container):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/history/bets",
            params={
                "lottery_modality": "mega-sena",
                "draw_number": "1234",
                "start_date": "2026-07-01T00:00:00",
                "end_date": "2026-07-31T23:59:59",
            },
        )

    assert response.status_code == 200
    assert override_container.list_placed_bets.calls[0] == {
        "lottery_modality": "mega-sena",
        "draw_number": "1234",
        "start_date": datetime(2026, 7, 1, 0, 0, 0),
        "end_date": datetime(2026, 7, 31, 23, 59, 59),
    }


@pytest.mark.anyio
async def test_get_placed_bet_route_returns_serialized_bet(override_container):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/history/bets/64ef8f7a6f9a8f0f8f0f8f0f")

    assert response.status_code == 200
    assert response.json()["bet_id"] == "64ef8f7a6f9a8f0f8f0f8f0f"
    assert response.json()["lottery_modality"] == "mega-sena"
    assert override_container.get_placed_bet.calls == ["64ef8f7a6f9a8f0f8f0f8f0f"]


@pytest.mark.anyio
async def test_get_placed_bet_route_returns_not_found_when_bet_does_not_exist():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/history/bets/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROTA_NAO_ENCONTRADA"


@pytest.mark.anyio
async def test_get_placed_bet_route_returns_bad_request_when_bet_id_is_invalid():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/history/bets/invalid")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUISICAO_INVALIDA"


@pytest.mark.anyio
async def test_not_found_uses_standard_error_shape():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROTA_NAO_ENCONTRADA"


@pytest.mark.anyio
async def test_session_routes_map_automation_errors():
    fake = FakeContainer()
    fake.session_control = FailingSessionControl()
    app.dependency_overrides[get_container] = lambda: fake
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        start = await client.get("/api/v1/sessions/start")
        stop = await client.get("/api/v1/sessions/stop")

    assert start.status_code == 409
    assert start.json()["error"]["code"] == "SESSAO_JA_ABERTA"
    assert stop.status_code == 409
    assert stop.json()["error"]["code"] == "SESSAO_FECHADA"
