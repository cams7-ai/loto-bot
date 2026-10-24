from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from api.dependencies import get_container
from api.server import app
from application import SessionControlUseCase
from application.ports import BrowserAutomationPort, NotificationPort, ValidationCodePort
from domain import AutomationError, AutomationSession, Operation, PageRedirectionError
from infrastructure import NotificationGateway, Settings, WhatsAppNotifyClient


@pytest.mark.anyio
@pytest.mark.parametrize("notification_result", ["enviado", "falhou", "exception", "mail_failure"])
@pytest.mark.parametrize("unexpected_error", [False, True])
async def test_start_failure_notifies_then_stops_whatsapp_and_allows_retry(notification_result, unexpected_error):
    events = []
    remote_session = {"is_open": False}

    def whatsapp_handler(request):
        path = request.url.path
        events.append(path)
        if path == "/whatsapp/session/start":
            assert remote_session["is_open"] is False
            remote_session["is_open"] = True
            return httpx.Response(200, json={"status": "SESSAO_ABERTA"})
        if path == "/whatsapp/session/stop":
            remote_session["is_open"] = False
            return httpx.Response(200, json={"status": "SESSAO_FECHADA"})
        if path == "/whatsapp/session/status":
            return httpx.Response(200, json={"status": "SESSAO_ABERTA"})
        assert path == "/whatsapp/messages/send"
        assert remote_session["is_open"] is True
        if notification_result in {"exception", "mail_failure"}:
            raise httpx.ConnectError("WhatsApp indisponível", request=request)
        return httpx.Response(200, json={"status": notification_result})

    def send_mail(*args):
        events.append("mail")
        if notification_result == "mail_failure":
            raise RuntimeError("E-mail indisponível")

    session = AutomationSession()
    browser = Mock(spec=BrowserAutomationPort)
    browser.is_authenticated.return_value = False
    error = (
        RuntimeError("falha inesperada")
        if unexpected_error
        else PageRedirectionError("/termos-de-uso", Operation.ACCEPT_TERMS)
    )
    browser.accept_terms.side_effect = error
    browser.stop.side_effect = lambda: events.append("browser:stop")
    settings = Settings(_env_file=None, WHATSAPP_NOTIFY_URL="http://whatsapp.test")
    with httpx.Client(transport=httpx.MockTransport(whatsapp_handler)) as whatsapp_http:
        gateway = NotificationGateway(
            WhatsAppNotifyClient(settings, whatsapp_http),
            SimpleNamespace(send=send_mail),
            whatsapp_enabled=True,
        )
        use_case = SessionControlUseCase(session, browser, Mock(spec=ValidationCodePort), gateway)
        app.dependency_overrides[get_container] = lambda: SimpleNamespace(session_control=use_case)
        try:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/v1/sessions/start")

                assert response.status_code == (500 if unexpected_error else 502)
                if not unexpected_error:
                    assert response.json()["error"]["code"] == "ERRO_NO_REDIRECIONAMENTO_DA_PAGINA"
                    assert response.json()["error"]["message"] == str(error)
                expected = ["/whatsapp/session/start", "/whatsapp/session/status", "/whatsapp/messages/send"]
                if notification_result != "enviado":
                    expected.append("mail")
                assert events == [*expected, "browser:stop", "/whatsapp/session/stop"]
                assert remote_session["is_open"] is False
                assert session.is_open is False
                assert session.whatsapp_enabled is False

                browser.is_authenticated.return_value = True
                retry = await client.get("/api/v1/sessions/start")
                assert retry.status_code == 200
                assert retry.json()["is_open"] is True
                assert remote_session["is_open"] is True
                stopped = await client.get("/api/v1/sessions/stop")
                assert stopped.status_code == 200
                assert remote_session["is_open"] is False
        finally:
            app.dependency_overrides.clear()


@pytest.mark.parametrize("failing_step", ["notify_failure", "browser_stop", "whatsapp_stop", "whatsapp_start"])
def test_start_preserves_original_error_and_attempts_cleanup_when_secondary_step_fails(failing_step):
    session = AutomationSession()
    browser = Mock(spec=BrowserAutomationPort)
    notifier = Mock(spec=NotificationPort)
    error = PageRedirectionError("/termos-de-uso", Operation.ACCEPT_TERMS)
    browser.is_authenticated.return_value = False
    browser.accept_terms.side_effect = error

    def start_whatsapp(current_session):
        current_session.whatsapp_enabled = True
        if failing_step == "whatsapp_start":
            raise error

    notifier.start_whatsapp_session.side_effect = start_whatsapp
    if failing_step == "notify_failure":
        notifier.notify_failure.side_effect = RuntimeError("Falha na notificação")
    elif failing_step == "browser_stop":
        browser.stop.side_effect = RuntimeError("Falha ao fechar navegador")
    elif failing_step == "whatsapp_stop":
        notifier.stop_whatsapp_session.side_effect = RuntimeError("Falha ao encerrar WhatsApp")
    use_case = SessionControlUseCase(session, browser, Mock(spec=ValidationCodePort), notifier)

    with pytest.raises(AutomationError) as raised:
        use_case.start()

    assert raised.value is error
    notifier.notify_failure.assert_called_once_with(True, error)
    browser.stop.assert_called_once_with()
    notifier.stop_whatsapp_session.assert_called_once_with(session)
    assert session.is_open is False
    assert session.whatsapp_enabled is False
