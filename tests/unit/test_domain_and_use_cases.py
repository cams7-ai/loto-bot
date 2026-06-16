from __future__ import annotations

from application.use_cases import RunBetFlowUseCase, SessionControlUseCase
from domain import AutomationSession, BrowserSessionClosedError, BrowserSessionOpenError
from domain.value_objects import PaymentAuthorization


class FakeBrowser:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.open = False

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
            if name == "finish_bet":
                return "123456"
            return None

        return method


class FakeNotifier:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.messages: list[str] = []

    def start_whatsapp_session(self, session):
        self.started = True
        session.whatsapp_enabled = True

    def stop_whatsapp_session(self, session):
        self.stopped = True
        session.whatsapp_enabled = False

    def notify_failure(self, session, message):
        self.messages.append(message)


class FakeValidationCodes:
    def get_validation_code(self):
        return "654321"


def test_session_control_lifecycle():
    session = AutomationSession()
    browser = FakeBrowser()
    notifier = FakeNotifier()
    use_case = SessionControlUseCase(session, browser, notifier)

    started = use_case.start()
    assert started.is_open is True
    assert started.status == "open"
    assert session.tab_id == "tab123"
    assert notifier.started is True

    stopped = use_case.stop()
    assert stopped.is_open is False
    assert stopped.status == "closed"
    assert notifier.stopped is True


def test_session_control_rejects_invalid_lifecycle():
    session = AutomationSession()
    use_case = SessionControlUseCase(session, FakeBrowser(), FakeNotifier())

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
    browser = FakeBrowser()
    notifier = FakeNotifier()
    session_control = SessionControlUseCase(session, browser, notifier)
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        validation_codes=FakeValidationCodes(),
        notifier=notifier,
        session_control=session_control,
        payment_authorization=PaymentAuthorization(True),
    )

    result = use_case.run()

    assert result.status == "finished"
    assert result.tracking_code == "123456"
    assert session.valid_code == "654321"
    assert browser.calls[0] == "start"
    assert "confirm_payment" in browser.calls
    assert browser.calls[-1] == "stop"


def test_run_bet_flow_blocks_payment_without_authorization():
    session = AutomationSession()
    browser = FakeBrowser()
    notifier = FakeNotifier()
    session_control = SessionControlUseCase(session, browser, notifier)
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        validation_codes=FakeValidationCodes(),
        notifier=notifier,
        session_control=session_control,
        payment_authorization=PaymentAuthorization(False),
    )

    result = use_case.run()

    assert result.status == "failed"
    assert result.executed_operation == "Confirma o pagamento"
    assert "desabilitada" in result.message
    assert notifier.messages
    assert "confirm_payment" not in browser.calls
    assert browser.calls[-1] == "stop"
