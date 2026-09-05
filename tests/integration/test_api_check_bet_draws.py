from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from api.dependencies import get_container
from api.responses import Utf8JSONResponse
from api.server import app
from application import CheckBetDrawsResult
from domain import BrowserSessionClosedError, ExternalServiceError, NotificationChannel, Operation


class FakeCheckBetDraws:
    def __init__(self, result: CheckBetDrawsResult | None = None, error: Exception | None = None) -> None:
        self.result = result or CheckBetDrawsResult(
            matched_bets=1,
            notification_sent=True,
            notification_channel=NotificationChannel.WHATSAPP,
            message="Conferência concluída e notificação enviada pelo WhatsApp.",
        )
        self.error = error
        self.calls = []

    def run(self, command):
        self.calls.append(command)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.anyio
async def test_check_bet_draws_openapi_documents_required_fields_and_named_success_examples() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/bets/check_draws"]["post"]
    request_schema = schema["components"]["schemas"]["CheckBetDrawsRequest"]

    assert request_schema["required"] == ["lottery_modality", "start_date", "end_date"]
    assert set(request_schema["properties"]) == {
        "lottery_modality",
        "start_date",
        "end_date",
        "bet_type",
        "draw_type",
        "month_year",
        "status",
    }
    assert set(operation["responses"]) >= {"200", "400", "409", "500", "502", "503"}
    examples = operation["responses"]["200"]["content"][Utf8JSONResponse.media_type]["examples"]
    assert set(examples) == {"WHATSAPP", "EMAIL", "NONE"}
    assert "422" not in operation["responses"]


@pytest.mark.anyio
async def test_check_bet_draws_route_builds_typed_command_and_serializes_result() -> None:
    use_case = FakeCheckBetDraws()
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(check_bet_draws=use_case)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/bets/check_draws",
                json={
                    "lottery_modality": "ALL",
                    "start_date": "2026-07-27",
                    "end_date": "2026-07-27",
                    "bet_type": "INDIVIDUAL",
                    "draw_type": "ALL",
                    "month_year": "LAST_7_DAYS",
                    "status": "ALL",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "matched_bets": 1,
        "notification_sent": True,
        "notification_channel": "WHATSAPP",
        "message": "Conferência concluída e notificação enviada pelo WhatsApp.",
    }
    command = use_case.calls[0]
    assert command.history_filters.lottery_modality is None
    assert command.history_filters.draw_number is None
    assert command.history_filters.end_date.hour == 23
    assert command.portal_filters.lottery_modality is None
    assert command.portal_filters.sort_by is None
    assert command.portal_filters.has_explicit_filters is True


@pytest.mark.anyio
async def test_check_bet_draws_route_returns_no_matches_result() -> None:
    result = CheckBetDrawsResult(
        0,
        False,
        NotificationChannel.NONE,
        "Conferência concluída. Nenhuma aposta correspondente foi encontrada.",
    )
    use_case = FakeCheckBetDraws(result)
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(check_bet_draws=use_case)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/bets/check_draws",
                json={"lottery_modality": "MEGA_SENA", "start_date": "2026-07-27", "end_date": "2026-07-27"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["notification_channel"] == "NONE"
    assert response.json()["notification_sent"] is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"lottery_modality": None, "start_date": None, "end_date": None},
        {"lottery_modality": "  ", "start_date": "", "end_date": "   "},
    ],
)
async def test_check_bet_draws_route_returns_structured_errors_before_use_case(payload: dict) -> None:
    use_case = FakeCheckBetDraws()
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(check_bet_draws=use_case)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/v1/bets/check_draws", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["message"] == "Campos inválidos"
    assert [detail["field"] for detail in error["details"]] == ["lottery_modality", "start_date", "end_date"]
    assert "timestamp" in error
    assert use_case.calls == []


@pytest.mark.anyio
async def test_check_bet_draws_route_rejects_invalid_field_types_before_use_case() -> None:
    use_case = FakeCheckBetDraws()
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(check_bet_draws=use_case)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/bets/check_draws",
                json={"lottery_modality": 1, "start_date": False, "end_date": []},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error"] == {
        "status_code": 400,
        "code": "REQUISICAO_INVALIDA",
        "message": "Corpo da requisição inválido.",
    }
    assert use_case.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (BrowserSessionClosedError(Operation.END_SESSION), 409, "SESSAO_FECHADA"),
        (
            ExternalServiceError("Falha nos canais", operation=Operation.CHECK_BET_DRAWS),
            503,
            "SERVICO_EXTERNO_INDISPONIVEL",
        ),
    ],
)
async def test_check_bet_draws_route_maps_automation_errors(error, status_code: int, code: str) -> None:
    use_case = FakeCheckBetDraws(error=error)
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(check_bet_draws=use_case)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/bets/check_draws",
                json={"lottery_modality": "MEGA_SENA", "start_date": "2026-07-27", "end_date": "2026-07-27"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
