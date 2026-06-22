from __future__ import annotations

import logging
import asyncio
import sys
import types
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from application.use_cases import RunBetFlowUseCase, SessionControlUseCase
from api.dependencies import get_container
from api.server import app
from domain import (
    Operation,
    AutomationSession, 
    ExternalServiceError, 
    PaymentAuthorization,
)
from infrastructure import (
    Settings,
    configure_logging,
    GmailReaderClient,
    MailSenderClient,
    NotificationGateway,
    WhatsAppNotifyClient,
    PlaywrightBrowserAutomation,
    Selectors,
)


class NoopNotifier:
    def start_whatsapp_session(self, session):
        pass

    def stop_whatsapp_session(self, session):
        pass

    def notify_failure(self, session, message):
        self.message = message


class BrokenBrowser:
    def start(self, session):
        return "tab"

    def stop(self):
        self.stopped = True

    def access_lottery_portal(self, session):
        raise ValueError("quebrou")


class CodeReader:
    def get_validation_code(self, operation):
        return "123456"


def response(status_code: int, payload: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload or {}, request=httpx.Request("GET", "http://test"))


def test_run_bet_flow_handles_unexpected_exception():
    session = AutomationSession()
    browser = BrokenBrowser()
    notifier = NoopNotifier()
    control = SessionControlUseCase(session, browser, CodeReader(), notifier)
    use_case = RunBetFlowUseCase(session, browser, notifier, control, PaymentAuthorization(True))

    result = use_case.run()

    assert result.status == "failed"
    assert "inesperado" in result.message
    assert browser.stopped is True


def test_clients_error_edges():
    settings = Settings(URL_GMAIL_READER="http://gmail", URL_MAIL_SENDER="http://mail")
    empty_gmail = GmailReaderClient(settings, httpx.Client(transport=httpx.MockTransport(lambda request: response(200, {"code": ""}))))
    failing_mail = MailSenderClient(settings, httpx.Client(transport=httpx.MockTransport(lambda request: response(500, {"error": {}}))))

    try:
        empty_gmail.get_validation_code(Operation.REQUEST_VALIDATION_CODE)
    except ExternalServiceError as exc:
        assert "não retornou" in str(exc)
    else:
        raise AssertionError("Erro esperado")

    try:
        failing_mail.send(Operation.UNKNOWN_OPERATION, "Assunto", "Body")
    except ExternalServiceError as exc:
        assert "e-mail" in str(exc)
    else:
        raise AssertionError("Erro esperado")


def test_whatsapp_send_error_with_invalid_json():
    settings = Settings(URL_WHATSAPP_NOTIFY="http://whatsapp")
    raw = httpx.Response(500, content=b"erro", request=httpx.Request("POST", "http://test"))
    client = WhatsAppNotifyClient(settings, httpx.Client(transport=httpx.MockTransport(lambda request: raw)))

    try:
        client.send_message(Operation.UNKNOWN_OPERATION, "Ola")
    except ExternalServiceError as exc:
        assert "indisponível" in str(exc)
    else:
        raise AssertionError("Erro esperado")


def test_whatsapp_start_and_stop_error_branches():
    settings = Settings(URL_WHATSAPP_NOTIFY="http://whatsapp")
    client = WhatsAppNotifyClient(
        settings,
        httpx.Client(transport=httpx.MockTransport(lambda request: response(500, {"error": {"message": "falhou"}}))),
    )

    for action in (client.start_session, client.stop_session):
        try:
            action(Operation.UNKNOWN_OPERATION)
        except ExternalServiceError as exc:
            assert "falhou" in str(exc)
        else:
            raise AssertionError("Erro externo esperado")


def test_notification_gateway_success_and_stop_warning():
    class WhatsApp:
        def start_session(self, operation):
            return "SESSAO_ABERTA"

        def stop_session(self, operation):
            raise RuntimeError("falha")

        def status(self, operation):
            return "SESSAO_ABERTA"

        def send_message(self, message):
            return "enviado"

    class Mail:
        def send(self, subject, body):
            raise AssertionError("Não deveria enviar e-mail")

    session = AutomationSession()
    session.executed_operation = Operation.UNKNOWN_OPERATION
    gateway = NotificationGateway(WhatsApp(), Mail())

    gateway.start_whatsapp_session(session)
    gateway.notify_failure(session, "ok")
    gateway.stop_whatsapp_session(session)

    assert session.whatsapp_enabled is False


def test_notification_gateway_stop_success_and_disabled_return():
    class WhatsApp:
        def __init__(self):
            self.stopped = False

        def stop_session(self, operation):
            self.stopped = True
            return "SESSAO_FECHADA"

    class Mail:
        def send(self, operation, subject, body):
            pass

    session = AutomationSession()
    whatsapp = WhatsApp()
    gateway = NotificationGateway(whatsapp, Mail())

    gateway.stop_whatsapp_session(session)
    assert whatsapp.stopped is False

    session.whatsapp_enabled = True
    gateway.stop_whatsapp_session(session)
    assert whatsapp.stopped is True
    assert session.whatsapp_enabled is False


def test_notification_gateway_does_not_call_disabled_whatsapp():
    class WhatsApp:
        def start_session(self, operation):
            raise AssertionError("WhatsApp não deveria ser chamado")

    class Mail:
        pass

    session = AutomationSession()
    NotificationGateway(WhatsApp(), Mail(), whatsapp_enabled=False).start_whatsapp_session(session)

    assert session.whatsapp_enabled is False


def test_notification_gateway_whatsapp_exception_and_mail_error():
    class WhatsApp:
        def status(self, operation):
            raise RuntimeError("sem status")

    class Mail:
        def send(self, operation, subject, body):
            raise RuntimeError("sem e-mail")

    session = AutomationSession()
    session.whatsapp_enabled = True
    session.executed_operation = Operation.UNKNOWN_OPERATION
    gateway = NotificationGateway(WhatsApp(), Mail())

    gateway.notify_failure(session, "Falha")


def test_settings_selectors_and_logging(monkeypatch):
    settings = Settings(URL_HOME="http://home", URL_LOGIN_CAIXA="http://login", EXECUTION="exec")
    assert "tab" in settings.authentication_url("tab")
    assert "execution=dynamic" in settings.authentication_url("tab", "dynamic")
    assert "state" in settings.cpf_url("state", "nonce")
    assert "not(@tabindex='-1')" in Selectors.modality_button("mega-sena")
    assert Selectors.card_selector("1234")

    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    logging.getLogger("teste").info("mensagem")


def test_get_container_and_cached_openapi():
    assert get_container() is not None
    first = app.openapi()
    second = app.openapi()
    assert first is second


def test_lotobot_browser_settings_parse_like_whatsapp_notify(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        LOTTOBOT_BROWSER_PROFILE_DIR="perfil-local",
        LOTTOBOT_BROWSER_HEADLESS="sim",
        LOTTOBOT_BROWSER_TIMEOUT_SECONDS=45,
    )

    assert settings.browser_headless is True
    assert settings.browser_timeout_seconds == 45
    project_root = Path(__file__).resolve().parents[2]
    assert settings.browser_profile_dir == (project_root / "perfil-local").resolve()
    assert Settings(LOTTOBOT_BROWSER_HEADLESS="").browser_headless is False


def test_lotobot_browser_settings_reject_invalid_values():
    with pytest.raises(ValidationError):
        Settings(LOTTOBOT_BROWSER_HEADLESS="talvez")

    with pytest.raises(ValidationError):
        Settings(LOTTOBOT_BROWSER_TIMEOUT_SECONDS=0)


def test_playwright_browser_uses_lotobot_browser_constants(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    class FakePage:
        url = "http://local/acompanhamento/123"

    class FakeContext:
        pages: list[FakePage] = []

        def __init__(self, kwargs):
            self.kwargs = kwargs
            self.timeout = None
            self.script = None
            self.closed = False

        def set_default_timeout(self, timeout):
            self.timeout = timeout
            captured["timeout"] = timeout

        def add_init_script(self, script):
            self.script = script
            captured["script"] = script

        def new_page(self):
            page = FakePage()
            self.pages.append(page)
            return page

        def close(self):
            self.closed = True
            captured["closed"] = True

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            captured["kwargs"] = kwargs
            context = FakeContext(kwargs)
            captured["context"] = context
            return context

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()
            self.stopped = False

        def stop(self):
            self.stopped = True
            captured["stopped"] = True

    class FakeSyncPlaywright:
        def start(self):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                raise AssertionError("sync_playwright started inside an asyncio loop")

            playwright = FakePlaywright()
            captured["playwright"] = playwright
            return playwright

    fake_sync_api = types.ModuleType("playwright.sync_api")
    fake_sync_api.sync_playwright = lambda: FakeSyncPlaywright()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)

    settings = Settings(
        LOTTOBOT_BROWSER_PROFILE_DIR=tmp_path / "lotobot-profile",
        LOTTOBOT_BROWSER_HEADLESS=True,
        LOTTOBOT_BROWSER_TIMEOUT_SECONDS=12,
    )
    browser = PlaywrightBrowserAutomation(settings)
    session = AutomationSession()

    async def start_inside_asyncio_loop():
        return browser.start(session)

    tab_id = asyncio.run(start_inside_asyncio_loop())
    browser.stop()

    kwargs = captured["kwargs"]
    assert tab_id
    assert settings.browser_profile_dir.exists()
    assert kwargs["user_data_dir"] == str(settings.browser_profile_dir)
    assert kwargs["headless"] is True
    assert kwargs["viewport"] == {"width": 1280, "height": 900}
    assert "--window-size=1280,900" in kwargs["args"]
    assert kwargs["locale"] == "pt-BR"
    assert "Chrome/122.0.0.0" in kwargs["user_agent"]
    assert captured["timeout"] == 12000
    assert "navigator" in captured["script"]
    assert captured["closed"] is True
    assert captured["stopped"] is True


def test_playwright_browser_syncs_dynamic_login_execution_from_current_url():
    settings = Settings(URL_LOGIN_CAIXA="http://login", EXECUTION="<EXECUTION_ID_DA_SESSAO>")
    browser = PlaywrightBrowserAutomation(settings)

    class FakePage:
        url = (
            "https://login.caixa.gov.br/auth/realms/internet/login-actions/authenticate"
            "?session_code=abc&execution=exec-real&client_id=cli-web-lce&tab_id=tab-real"
        )

        def wait_for_url(self, pattern, timeout):
            self.pattern = pattern
            self.timeout = timeout

    session = AutomationSession()
    browser._page = FakePage()

    browser._sync_auth_session_from_current_url(session)

    assert session.execution == "exec-real"
    assert session.tab_id == "tab-real"
    assert settings.authentication_url(session.tab_id, session.execution).endswith("execution=exec-real&client_id=cli-web-lce&tab_id=tab-real")


def test_playwright_browser_syncs_dynamic_login_ignores_missing_query_params():
    browser = PlaywrightBrowserAutomation(Settings())

    class FakePage:
        url = "https://login.caixa.gov.br/auth/realms/internet/login-actions/authenticate"

        def wait_for_url(self, pattern, timeout):
            pass

    session = AutomationSession(tab_id="tab-original", execution="exec-original")
    browser._page = FakePage()

    browser._sync_auth_session_from_current_url(session)

    assert session.execution == "exec-original"
    assert session.tab_id == "tab-original"


def test_playwright_browser_checks_authentication_on_browser_thread():
    settings = Settings()
    browser = PlaywrightBrowserAutomation(settings)
    calls = []

    def run_on_browser_thread(action, *args):
        calls.append((action.__name__, args))
        return action(*args)

    browser._run_on_browser_thread = run_on_browser_thread
    def fake_is_authenticated(session):
        return True

    browser._is_authenticated = fake_is_authenticated

    assert browser.is_authenticated(AutomationSession()) is True
    assert calls[0][0] == "fake_is_authenticated"


def test_playwright_browser_authentication_check_uses_login_marker():
    browser = PlaywrightBrowserAutomation(Settings())
    actions = []

    class Locator:
        first = None

        def __init__(self):
            self.first = self

        def wait_for(self, *, state, timeout):
            actions.append((state, timeout))

    class Page:
        def locator(self, selector):
            actions.append(selector)
            return Locator()

    browser._page = Page()

    assert browser._is_authenticated(False) is True
    assert actions == [
        Selectors.LOGGED_IN_LOGIN_BUTTON,
        ("visible", 5000),
    ]


def test_playwright_browser_authentication_check_returns_false_after_timeout():
    browser = PlaywrightBrowserAutomation(Settings())

    class Locator:
        first = None

        def __init__(self):
            self.first = self

        def wait_for(self, **kwargs):
            raise TimeoutError

    class Page:
        def locator(self, selector):
            return Locator()

    browser._page = Page()

    assert browser._is_authenticated(AutomationSession()) is False


def test_playwright_browser_continues_login_without_direct_authenticate_goto():
    settings = Settings()
    browser = PlaywrightBrowserAutomation(settings)
    actions = []

    def fail_goto(url):
        raise AssertionError(f"Nao deveria navegar diretamente para {url}")

    browser._goto = fail_goto
    browser._raise_if_forbidden = lambda operation: actions.append(("check", operation))
    browser._click = lambda selector: actions.append(("click", selector))
    browser._fill = lambda selector, value: actions.append(("fill", selector, value))

    session = AutomationSession(tab_id="tab", execution="exec")
    browser._request_validation_code(session)
    browser._submit_validation_code(session, "123456")
    browser._submit_password(session)

    assert ("click", Selectors.RECEIVE_CODE_BUTTON) in actions
    assert ("fill", Selectors.CODE_FIELD, "123456") in actions
    assert ("fill", Selectors.PASSWORD_FIELD, settings.senha) in actions


def test_playwright_browser_retries_payment_until_confirmation_modal_is_visible():
    browser = PlaywrightBrowserAutomation(Settings())
    clicks = []

    class PaymentButton:
        first = None

        def __init__(self):
            self.first = self

        def click(self, **kwargs):
            clicks.append(kwargs)

    class ConfirmationButton:
        first = None

        def __init__(self):
            self.first = self
            self.waits = 0

        def wait_for(self, **kwargs):
            self.waits += 1
            if self.waits == 1:
                raise TimeoutError

        def click(self):
            clicks.append("confirmed")

    payment = PaymentButton()
    confirmation = ConfirmationButton()

    class Page:
        url = "http://lottery/#/mega-sena"

        def locator(self, selector):
            return payment if selector == Selectors.GO_TO_PAYMENT_BUTTON else confirmation

        def wait_for_timeout(self, timeout):
            clicks.append(("pause", timeout))

    browser._page = Page()

    browser._confirm_purchase(AutomationSession())

    assert clicks.count({"no_wait_after": True}) == 2
    assert clicks[-1] == "confirmed"
