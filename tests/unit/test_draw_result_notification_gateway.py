from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from application import PortalBetResult
from domain import AutomationSession, ExternalServiceError, NotificationChannel, Operation
from infrastructure.clients.notification_gateway import NotificationGateway


def portal_bet() -> PortalBetResult:
    return PortalBetResult(
        purchase_datetime=datetime(2026, 7, 27, 23, 14, 44, tzinfo=ZoneInfo("America/Sao_Paulo")),
        lottery_modality="MEGA_SENA",
        selected_numbers=["02", "20", "28", "48", "57", "59"],
        draw_number="3037",
        status="Concurso não apurado",
    )


class WhatsApp:
    def __init__(
        self,
        *,
        status: str = "SESSAO_ABERTA",
        response: str = "enviado",
        error: Exception | None = None,
    ) -> None:
        self.session_status = status
        self.response = response
        self.error = error
        self.status_calls: list[Operation] = []
        self.messages: list[tuple[Operation, str]] = []

    def status(self, operation):
        self.status_calls.append(operation)
        if self.error is not None:
            raise self.error
        return self.session_status

    def send_message(self, operation, message):
        self.messages.append((operation, message))
        if self.error is not None:
            raise self.error
        return self.response


@dataclass
class Mail:
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.sent: list[tuple[Operation, str, str]] = []

    def send(self, operation, subject, body):
        if self.error is not None:
            raise self.error
        self.sent.append((operation, subject, body))


def open_session(*, whatsapp_enabled: bool) -> AutomationSession:
    session = AutomationSession()
    session.mark_open()
    session.whatsapp_enabled = whatsapp_enabled
    return session


def test_draw_result_notification_uses_whatsapp_without_email() -> None:
    whatsapp = WhatsApp()
    mail = Mail()
    gateway = NotificationGateway(whatsapp, mail, whatsapp_enabled=True)

    channel = gateway.notify_draw_results(open_session(whatsapp_enabled=True), [portal_bet()])

    assert channel is NotificationChannel.WHATSAPP
    assert whatsapp.status_calls == [Operation.CHECK_BET_DRAWS]
    assert whatsapp.messages[0][0] is Operation.CHECK_BET_DRAWS
    assert mail.sent == []


@pytest.mark.parametrize(
    "whatsapp",
    [
        WhatsApp(status="SESSAO_FECHADA"),
        WhatsApp(response="erro"),
        WhatsApp(error=RuntimeError("indisponível")),
    ],
)
def test_draw_result_notification_falls_back_to_email(whatsapp: WhatsApp) -> None:
    mail = Mail()
    gateway = NotificationGateway(whatsapp, mail, whatsapp_enabled=True)

    channel = gateway.notify_draw_results(open_session(whatsapp_enabled=True), [portal_bet()])

    assert channel is NotificationChannel.EMAIL
    assert mail.sent[0][0] is Operation.CHECK_BET_DRAWS
    assert mail.sent[0][1] == "LotoBot - resultado da conferência de apostas"
    assert "Resultado da conferência" in mail.sent[0][2]


def test_draw_result_notification_skips_disabled_whatsapp() -> None:
    whatsapp = WhatsApp()
    mail = Mail()
    gateway = NotificationGateway(whatsapp, mail, whatsapp_enabled=False)

    channel = gateway.notify_draw_results(open_session(whatsapp_enabled=False), [portal_bet()])

    assert channel is NotificationChannel.EMAIL
    assert whatsapp.status_calls == []
    assert whatsapp.messages == []


@pytest.mark.parametrize(
    "error",
    [
        ExternalServiceError("mail falhou", operation=Operation.CHECK_BET_DRAWS),
        RuntimeError("mail falhou"),
    ],
)
def test_draw_result_notification_propagates_typed_email_failure(error: Exception) -> None:
    gateway = NotificationGateway(WhatsApp(status="SESSAO_FECHADA"), Mail(error), whatsapp_enabled=True)

    with pytest.raises(ExternalServiceError):
        gateway.notify_draw_results(open_session(whatsapp_enabled=True), [portal_bet()])
