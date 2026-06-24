from __future__ import annotations

from threading import Event

import application.use_cases.session_control as session_control_module
from application import RunBetFlowUseCase, SessionControlUseCase
from domain import (
    Operation, 
    AutomationSession, 
    AutomationError, 
    BrowserSessionClosedError, 
    BrowserSessionOpenError, 
    ErrorCode,
    PaymentAuthorization,
)


class FakeBrowser:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.open = False
        self.authenticated = False

    def start(self, session):
        self.open = True
        self.calls.append("start")
        return "tab123"

    def stop(self):
        self.open = False
        self.calls.append("stop")

    def __getattr__(self, name):
        def method(*args):
            self.calls.append(name)
            if name == "submit_password":
                self.authenticated = True
            if name == "finish_bet":
                return "123456"
            return None

        return method

    def is_authenticated(self, click_login_button):
        self.calls.append("is_authenticated")
        return self.authenticated

    def is_valid_cpf(self):
        self.calls.append("is_valid_cpf")
        return True


class FakeNotifier:
    def __init__(self, failure_response: object | None = "enviado") -> None:
        self.started = False
        self.stopped = False
        self.messages: list[str] = []
        self.failure_response = failure_response

    def start_whatsapp_session(self, session):
        self.started = True
        session.whatsapp_enabled = True

    def stop_whatsapp_session(self, session):
        self.stopped = True
        session.whatsapp_enabled = False

    def notify_failure(self, session, error_code, whatsapp_message, mail_message):
        self.error_code = error_code
        self.messages.append(whatsapp_message)
        return self.failure_response is not None


class FakeValidationCodes:
    def __init__(self) -> None:
        self.calls: list[Operation] = []

    def get_validation_code(self, operation):
        self.calls.append(operation)
        return "654321"


class WaitingValidationCodes:
    def __init__(self, calls: list[str], code_requested: Event) -> None:
        self._calls = calls
        self._code_requested = code_requested

    def get_validation_code(self, operation):
        self._calls.append("get_validation_code")
        return "654321"


class ValidationCodeRequestBrowser(FakeBrowser):
    def __init__(self, code_requested: Event) -> None:
        super().__init__()
        self._code_requested = code_requested

    def request_validation_code(self, session):
        self.calls.append("request_validation_code")
        self._code_requested.set()


class AuthenticationErrorBrowser(FakeBrowser):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def is_authenticated(self, session):
        self.calls.append("is_authenticated")
        raise self._error


class InvalidCpfOnValidationCodeBrowser(FakeBrowser):
    def is_valid_cpf(self):
        self.calls.append("is_valid_cpf")
        return False


class AuthenticatedBrowser(FakeBrowser):
    def is_authenticated(self, session):
        self.calls.append("is_authenticated")
        return True


def test_session_control_lifecycle(monkeypatch):
    session = AutomationSession()
    browser = FakeBrowser()
    notifier = FakeNotifier()
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), notifier)

    started = use_case.start()
    assert started.is_open is True
    assert started.status == "open"
    assert session.tab_id == "tab123"
    assert notifier.started is True

    stopped = use_case.stop()
    assert stopped.is_open is False
    assert stopped.status == "closed"
    assert notifier.stopped is True


def test_session_control_skips_authentication_steps_when_already_authenticated(monkeypatch):
    session = AutomationSession()
    browser = AuthenticatedBrowser()
    notifier = FakeNotifier()
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), notifier)

    started = use_case.start()

    assert started.status == "open"
    assert "is_authenticated" in browser.calls
    assert "access_lottery_portal" not in browser.calls
    assert "accept_terms" not in browser.calls
    assert "submit_cpf" not in browser.calls
    assert "request_validation_code" not in browser.calls
    assert "submit_validation_code" not in browser.calls
    assert "submit_password" not in browser.calls


def test_session_control_closes_session_when_authentication_fails_with_automation_error(monkeypatch):
    session = AutomationSession()
    browser = AuthenticationErrorBrowser(AutomationError("falha", operation=Operation.ACCESS_LOTTERY_PORTAL))
    notifier = FakeNotifier()
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), notifier)

    try:
        use_case.start()
    except AutomationError as exc:
        assert "falha" in str(exc)
    else:
        raise AssertionError("Erro esperado")

    assert session.status.value == "closed"
    assert browser.open is False
    assert browser.calls[-1] == "stop"
    assert notifier.stopped is True


def test_session_control_closes_session_when_authentication_fails_unexpectedly(monkeypatch):
    session = AutomationSession()
    browser = AuthenticationErrorBrowser(ValueError("quebrou"))
    notifier = FakeNotifier()
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), notifier)

    try:
        use_case.start()
    except AutomationError as exc:
        assert "quebrou" in str(exc)
        assert exc.operation == Operation.ACCESS_LOTTERY_PORTAL
    else:
        raise AssertionError("Erro esperado")

    assert session.status.value == "closed"
    assert browser.open is False
    assert browser.calls[-1] == "stop"
    assert notifier.stopped is True


def test_session_control_keeps_whatsapp_session_when_failure_notification_has_no_response(monkeypatch):
    session = AutomationSession()
    browser = AuthenticationErrorBrowser(AutomationError("falha", operation=Operation.ACCESS_LOTTERY_PORTAL))
    notifier = FakeNotifier(failure_response=None)
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), notifier)

    try:
        use_case.start()
    except AutomationError:
        pass
    else:
        raise AssertionError("Erro esperado")

    assert session.status.value == "closed"
    assert browser.open is False
    assert browser.calls[-1] == "stop"
    assert notifier.stopped is False


def test_session_control_does_not_read_code_for_invalid_cpf(monkeypatch):
    session = AutomationSession()
    browser = InvalidCpfOnValidationCodeBrowser()
    validation_codes = FakeValidationCodes()
    notifier = FakeNotifier()
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, validation_codes, notifier)

    try:
        use_case.start()
    except AutomationError as exc:
        assert str(exc) == "O CPF é inválido"
        assert exc.operation == Operation.SUBMIT_CPF
    else:
        raise AssertionError("Erro esperado")

    assert validation_codes.calls == []
    assert "request_validation_code" not in browser.calls
    assert notifier.messages
    assert session.status.value == "closed"
    assert browser.open is False


def test_session_control_rejects_invalid_lifecycle(monkeypatch):
    session = AutomationSession()
    browser = FakeBrowser()
    monkeypatch.setattr(session_control_module, "sleep", lambda seconds: browser.calls.append(f"sleep:{seconds}"))
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), FakeNotifier())

    try:
        use_case.stop()
    except BrowserSessionClosedError as exc:
        assert "fechada" in str(exc)
    else:
        raise AssertionError("A sessão fechada deveria ser recusada")

    use_case.start()
    try:
        use_case.start()
    except BrowserSessionOpenError as exc:
        assert "aberta" in str(exc)
    else:
        raise AssertionError("A sessão aberta deveria ser recusada")


def test_run_bet_flow_finishes_when_payment_is_authorized():
    session = AutomationSession()
    session.mark_open("tab123")
    browser = FakeBrowser()
    notifier = FakeNotifier()
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(True),
    )

    result = use_case.run()

    assert result.status == "finished"
    assert result.tracking_code == "123456"
    assert browser.calls[0] == "access_home"
    assert "confirm_payment" in browser.calls
    assert browser.calls[-1] == "stop"


def test_run_bet_flow_starts_code_lookup_before_requesting_validation_code(monkeypatch):
    session = AutomationSession()
    session.mark_open("tab123")
    code_requested = Event()
    browser = ValidationCodeRequestBrowser(code_requested)
    notifier = FakeNotifier()
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(True),
    )

    result = use_case.run()

    assert result.status == "finished"
    assert "request_validation_code" not in browser.calls
    assert session.valid_code is None


def test_run_bet_flow_blocks_payment_without_authorization():
    session = AutomationSession()
    session.mark_open("tab123")
    browser = FakeBrowser()
    notifier = FakeNotifier()
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(False),
    )

    try:
        use_case.run()
    except AutomationError as exc:
        assert exc.operation == Operation.CONFIRM_PAYMENT
        assert exc.code == ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE
        assert "desabilitada" in str(exc)
    else:
        raise AssertionError("Erro esperado")

    assert notifier.messages
    assert "confirm_payment" not in browser.calls
    assert session.status.value == "failed"
