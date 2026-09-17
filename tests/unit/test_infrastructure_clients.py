from __future__ import annotations

import json
import sys
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from domain import (
    AutomationError,
    AutomationSession,
    ExternalServiceError,
    Operation,
)
from infrastructure import (
    GmailReaderClient,
    MailSenderClient,
    NotificationGateway,
    Settings,
    WhatsAppNotifyClient,
)
from shared import mask_sensitive_value


def response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload, request=httpx.Request("GET", "http://test"))


def test_mask_sensitive_value():
    assert mask_sensitive_value("123456") == "****56"
    assert mask_sensitive_value("1") == "*"
    assert mask_sensitive_value(None) == ""


def test_integration_mode_accepts_only_local_or_aws():
    assert Settings(INTEGRATION_MODE="LOCAL").integration_mode == "LOCAL"
    assert Settings(INTEGRATION_MODE="AWS").integration_mode == "AWS"
    with pytest.raises(ValidationError):
        Settings(INTEGRATION_MODE="OTHER")


class FakeLambdaClient:
    def __init__(self, payload: dict | None = None, error: Exception | None = None, function_error: str | None = None):
        self.payload = payload or {"statusCode": 200, "body": json.dumps({"code": "123456"})}
        self.error = error
        self.function_error = function_error
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        result = {"Payload": BytesIO(json.dumps(self.payload).encode())}
        if self.function_error:
            result["FunctionError"] = self.function_error
        return result


def test_aws_clients_are_created_lazily(monkeypatch):
    lambda_client = FakeLambdaClient()
    boto3 = SimpleNamespace(client=lambda service: lambda_client if service == "lambda" else None)
    monkeypatch.setitem(sys.modules, "boto3", boto3)

    settings = Settings(INTEGRATION_MODE="AWS")
    gmail_client = GmailReaderClient(settings)
    mail_client = MailSenderClient(settings)

    assert gmail_client._lambda_client() is lambda_client
    assert mail_client._lambda_client() is lambda_client


def test_http_clients_are_created_lazily(monkeypatch):
    created_clients = []

    def build_client(*, timeout):
        client = SimpleNamespace(timeout=timeout)
        created_clients.append(client)
        return client

    monkeypatch.setattr(httpx, "Client", build_client)
    settings = Settings(INTEGRATION_MODE="LOCAL", VALIDATION_CODE_WAIT_TIMEOUT_SECONDS=15)

    assert GmailReaderClient(settings)._http_client().timeout == 20
    assert MailSenderClient(settings)._http_client().timeout == 10
    assert len(created_clients) == 2


def test_gmail_reader_client_reads_code():
    lambda_client = FakeLambdaClient()
    settings = Settings(INTEGRATION_MODE="AWS", GMAIL_READER_FUNCTION_NAME="gmail-reader")
    client = GmailReaderClient(settings, lambda_client)

    assert client.get_validation_code(Operation.REQUEST_VALIDATION_CODE) == "123456"
    assert lambda_client.calls[0]["FunctionName"] == "gmail-reader"


def test_gmail_reader_client_sends_wait_timeout_and_read_timeout():
    lambda_client = FakeLambdaClient()
    settings = Settings(
        INTEGRATION_MODE="AWS", GMAIL_READER_FUNCTION_NAME="gmail-reader", VALIDATION_CODE_WAIT_TIMEOUT_SECONDS=15
    )
    client = GmailReaderClient(settings, lambda_client)

    assert client.get_validation_code(Operation.REQUEST_VALIDATION_CODE) == "123456"
    assert json.loads(lambda_client.calls[0]["Payload"])["waitTimeoutSeconds"] == 15


def test_gmail_reader_client_maps_http_timeout():
    settings = Settings(INTEGRATION_MODE="AWS", GMAIL_READER_FUNCTION_NAME="gmail-reader")
    client = GmailReaderClient(settings, FakeLambdaClient(error=TimeoutError()))

    try:
        client.get_validation_code(Operation.REQUEST_VALIDATION_CODE)
    except ExternalServiceError as exc:
        assert "Tempo esgotado" in str(exc)
    else:
        raise AssertionError("Erro externo esperado")


def test_gmail_reader_client_rejects_error():
    settings = Settings(INTEGRATION_MODE="AWS", GMAIL_READER_FUNCTION_NAME="gmail-reader")
    client = GmailReaderClient(settings, FakeLambdaClient(payload={"statusCode": 500, "body": "{}"}))

    try:
        client.get_validation_code(Operation.REQUEST_VALIDATION_CODE)
    except ExternalServiceError as exc:
        assert "código" in str(exc)
    else:
        raise AssertionError("Erro externo esperado")


def test_mail_sender_client_posts_payload():
    lambda_client = FakeLambdaClient(payload={"statusCode": 200, "body": "{}"})
    settings = Settings(INTEGRATION_MODE="AWS", MAIL_SENDER_FUNCTION_NAME="mail-sender", MAIL_TO="destino@example.com")
    client = MailSenderClient(settings, lambda_client)

    client.send(Operation.UNKNOWN_OPERATION, "Assunto", "<p>Body</p>")
    assert lambda_client.calls[0]["FunctionName"] == "mail-sender"
    assert json.loads(lambda_client.calls[0]["Payload"])["to"] == "destino@example.com"


def test_gmail_reader_client_uses_http_api_in_local_mode():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return response(200, {"code": "654321"})

    settings = Settings(
        INTEGRATION_MODE="LOCAL", GMAIL_READER_URL="http://gmail.local", VALIDATION_CODE_WAIT_TIMEOUT_SECONDS=15
    )
    client = GmailReaderClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.get_validation_code(Operation.REQUEST_VALIDATION_CODE) == "654321"
    assert seen["url"] == "http://gmail.local/api/v1/validation-code?waitTimeoutSeconds=15"


def test_gmail_reader_client_rejects_http_error_in_local_mode():
    settings = Settings(INTEGRATION_MODE="LOCAL", GMAIL_READER_URL="http://gmail.local")
    transport = httpx.MockTransport(lambda request: response(500, {"message": "error"}))
    client = GmailReaderClient(settings, httpx.Client(transport=transport))

    with pytest.raises(ExternalServiceError):
        client.get_validation_code(Operation.REQUEST_VALIDATION_CODE)


def test_mail_sender_client_uses_http_api_in_local_mode():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return response(200, {"message": "ok"})

    settings = Settings(INTEGRATION_MODE="LOCAL", MAIL_SENDER_URL="http://mail.local", MAIL_TO="to@example.com")
    client = MailSenderClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))

    client.send(Operation.UNKNOWN_OPERATION, "Assunto", "Mensagem")
    assert seen["url"] == "http://mail.local/api/v1/mail/send"
    assert seen["payload"]["to"] == "to@example.com"


def test_whatsapp_notify_client_maps_success_and_error():
    settings = Settings(WHATSAPP_NOTIFY_URL="http://whatsapp.local")
    transport = httpx.MockTransport(lambda request: response(200, {"status": "SESSAO_ABERTA"}))
    client = WhatsAppNotifyClient(settings, httpx.Client(transport=transport))

    assert client.status(Operation.UNKNOWN_OPERATION) == "SESSAO_ABERTA"
    assert client.start_session(Operation.UNKNOWN_OPERATION) == "SESSAO_ABERTA"
    assert client.stop_session(Operation.UNKNOWN_OPERATION) == "SESSAO_ABERTA"
    assert client.send_message(Operation.UNKNOWN_OPERATION, "Ola") == "SESSAO_ABERTA"

    error_client = WhatsAppNotifyClient(
        settings,
        httpx.Client(transport=httpx.MockTransport(lambda request: response(500, {"error": {"message": "falhou"}}))),
    )
    try:
        error_client.status(Operation.UNKNOWN_OPERATION)
    except ExternalServiceError as exc:
        assert "falhou" in str(exc)
    else:
        raise AssertionError("Erro externo esperado")


def test_notification_gateway_uses_email_fallback():
    class WhatsApp:
        def start_session(self, operation):
            raise RuntimeError("sem sessão")

        def stop_session(self, operation):
            raise RuntimeError("fechado")

        def status(self, operation):
            return "SESSAO_FECHADA"

        def send_message(self, operation, message):
            return "erro"

    class Mail:
        def __init__(self):
            self.sent = []

        def send(self, operation, subject, body):
            self.sent.append((operation, subject, body))

    session = AutomationSession()
    session.executed_operation = Operation.UNKNOWN_OPERATION
    mail = Mail()
    gateway = NotificationGateway(WhatsApp(), mail)

    gateway.start_whatsapp_session(session)
    gateway.notify_failure(
        session.whatsapp_enabled,
        AutomationError("Mensagem de falha", operation=Operation.UNKNOWN_OPERATION),
    )

    assert session.whatsapp_enabled is False
    assert mail.sent
