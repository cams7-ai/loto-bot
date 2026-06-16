from __future__ import annotations

import httpx

from domain import AutomationSession, ExternalServiceError
from infrastructure.clients import GmailReaderClient, MailSenderClient, NotificationGateway, WhatsAppNotifyClient
from infrastructure.config import Settings
from shared import mask_sensitive_value


def response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload, request=httpx.Request("GET", "http://test"))


def test_mask_sensitive_value():
    assert mask_sensitive_value("123456") == "****56"
    assert mask_sensitive_value("1") == "*"
    assert mask_sensitive_value(None) == ""


def test_gmail_reader_client_reads_code():
    settings = Settings(URL_GMAIL_READER="http://gmail.local")
    transport = httpx.MockTransport(lambda request: response(200, {"code": "123456"}))
    client = GmailReaderClient(settings, httpx.Client(transport=transport))

    assert client.get_validation_code() == "123456"


def test_gmail_reader_client_sends_wait_timeout_and_read_timeout():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["timeout"] = request.extensions["timeout"]
        return response(200, {"code": "123456"})

    settings = Settings(URL_GMAIL_READER="http://gmail.local", VALIDATION_CODE_WAIT_TIMEOUT_SECONDS=45)
    client = GmailReaderClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.get_validation_code() == "123456"
    assert "waitTimeoutSeconds=45" in seen["url"]
    assert seen["timeout"]["read"] == 50


def test_gmail_reader_client_maps_http_timeout():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    settings = Settings(URL_GMAIL_READER="http://gmail.local")
    client = GmailReaderClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))

    try:
        client.get_validation_code()
    except ExternalServiceError as exc:
        assert "Tempo esgotado" in str(exc)
    else:
        raise AssertionError("Erro externo esperado")


def test_gmail_reader_client_rejects_error():
    settings = Settings(URL_GMAIL_READER="http://gmail.local")
    transport = httpx.MockTransport(lambda request: response(500, {"error": {"message": "erro"}}))
    client = GmailReaderClient(settings, httpx.Client(transport=transport))

    try:
        client.get_validation_code()
    except ExternalServiceError as exc:
        assert "código" in str(exc)
    else:
        raise AssertionError("Erro externo esperado")


def test_mail_sender_client_posts_payload():
    seen = {}

    def handler(request):
        seen["payload"] = request.content
        return response(200, {"message": "ok"})

    settings = Settings(URL_MAIL_SENDER="http://mail.local", MAIL_TO="destino@example.com")
    client = MailSenderClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))

    client.send("Assunto", "<p>Body</p>")
    assert b"destino@example.com" in seen["payload"]


def test_whatsapp_notify_client_maps_success_and_error():
    settings = Settings(URL_WHATSAPP_NOTIFY="http://whatsapp.local")
    transport = httpx.MockTransport(lambda request: response(200, {"status": "SESSAO_ABERTA"}))
    client = WhatsAppNotifyClient(settings, httpx.Client(transport=transport))

    assert client.status() == "SESSAO_ABERTA"
    assert client.start_session() == "SESSAO_ABERTA"
    assert client.stop_session() == "SESSAO_ABERTA"
    assert client.send_message("Olá") == "SESSAO_ABERTA"

    error_client = WhatsAppNotifyClient(
        settings,
        httpx.Client(transport=httpx.MockTransport(lambda request: response(500, {"error": {"message": "falhou"}}))),
    )
    try:
        error_client.status()
    except ExternalServiceError as exc:
        assert "falhou" in str(exc)
    else:
        raise AssertionError("Erro externo esperado")


def test_notification_gateway_uses_email_fallback():
    class WhatsApp:
        def start_session(self):
            raise RuntimeError("sem sessão")

        def stop_session(self):
            raise RuntimeError("fechado")

        def status(self):
            return "SESSAO_FECHADA"

        def send_message(self, message):
            return "erro"

    class Mail:
        def __init__(self):
            self.sent = []

        def send(self, subject, body):
            self.sent.append((subject, body))

    session = AutomationSession()
    session.executed_operation = "Teste"
    mail = Mail()
    gateway = NotificationGateway(WhatsApp(), mail)

    gateway.start_whatsapp_session(session)
    gateway.notify_failure(session, "Falha simulada")

    assert session.whatsapp_enabled is False
    assert mail.sent
