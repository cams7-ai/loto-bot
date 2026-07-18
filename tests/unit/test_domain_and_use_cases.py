from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from threading import Event

from bson.decimal128 import Decimal128

import application.use_cases.session_control as session_control_module
from application import (
    GetPlacedBetUseCase,
    ListPlacedBetsUseCase,
    PlacedBetService,
    RunBetFlowUseCase,
    SessionControlUseCase,
)
from application.dto import BetResult, BetSearchFilters, PlacedBetResult, PurchaseResult
from domain import (
    BROWSER_SESSION_CLOSED,
    BROWSER_SESSION_OPEN,
    OPERATION_CANNOT_BE_COMPLETED,
    AutomationError,
    AutomationSession,
    BrowserSessionClosedError,
    BrowserSessionOpenError,
    ErrorCode,
    LotteryModality,
    Operation,
    PaymentAuthorization,
)
from infrastructure.database.models import BetModel


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
            if name == "check_your_purchases":
                return "123456"
            if name == "finish_bet":
                return PurchaseResult(
                    lottery_modality="mega-sena",
                    bets=[
                        BetResult(
                            numbers=["01", "02", "03", "04", "05", "06"],
                            draw="1234",
                            status="Efetivada",
                            amount=Decimal("5.00"),
                        )
                    ],
                    purchase_number="123456",
                    purchase_datetime=datetime(2026, 7, 12, 18, 8, 14),
                    total_purchase=Decimal("5.00"),
                    total_bets_effective=Decimal("5.00"),
                )
            return None

        return method

    def is_already_authenticated(self):
        self.calls.append("is_already_authenticated")
        return self.authenticated

    def is_authenticated(self):
        self.calls.append("is_authenticated")
        return self.authenticated

    def is_valid_cpf(self):
        self.calls.append("is_valid_cpf")
        return True

    def validation_code_lookup_lead(self):
        self.calls.append("validation_code_lookup_lead")
        return 1000


class FakeNotifier:
    def __init__(self, failure_response: object | None = "enviado") -> None:
        self.started = False
        self.stopped = False
        self.messages: list[str] = []
        self.success_notifications: list[PurchaseResult] = []
        self.failure_response = failure_response

    def start_whatsapp_session(self, session):
        self.started = True
        session.whatsapp_enabled = True

    def stop_whatsapp_session(self, session):
        self.stopped = True
        session.whatsapp_enabled = False

    def notify_failure(self, whatsapp_enabled, error):
        self.whatsapp_enabled = whatsapp_enabled
        self.error_code = error.code
        self.messages.append(str(error))
        return self.failure_response is not None

    def notify_success(self, session, purchase):
        self.success_notifications.append(purchase)


class FakeValidationCodes:
    def __init__(self) -> None:
        self.calls: list[Operation] = []

    def get_validation_code(self, operation):
        self.calls.append(operation)
        return "654321"


class FakeBetRepository:
    def __init__(self, save_error: Exception | None = None) -> None:
        self.saved: list[tuple[LotteryModality, PurchaseResult]] = []
        self.filters: BetSearchFilters | None = None
        self.requested_bet_id: str | None = None
        self.save_error = save_error
        self.search_results = [
            PlacedBetResult(
                bet_id="64ef8f7a6f9a8f0f8f0f8f0f",
                lottery_modality=LotteryModality.MEGA_SENA,
                selected_numbers=["01", "02", "03", "04", "05", "06"],
                draw_number="1234",
                status="Efetivada",
                bet_amount=Decimal("5.00"),
                purchase_number="123456",
                bet_date=datetime(2026, 7, 12, 18, 8, 14),
            )
        ]

    def save(self, lottery_modality, purchase):
        if self.save_error is not None:
            raise self.save_error
        self.saved.append((lottery_modality, purchase))

    def find_all(self, filters):
        self.filters = filters
        return self.search_results

    def find_by_id(self, bet_id):
        self.requested_bet_id = bet_id
        return self.search_results[0]


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

    def is_authenticated(self):
        self.calls.append("is_authenticated")
        raise self._error


class InvalidCpfOnValidationCodeBrowser(FakeBrowser):
    def is_valid_cpf(self):
        self.calls.append("is_valid_cpf")
        return False


class AuthenticatedBrowser(FakeBrowser):
    def is_authenticated(self):
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
    assert browser.calls[0] == "start"
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


def test_session_control_waits_minimum_time_before_requesting_validation_code(monkeypatch):
    session = AutomationSession()
    browser = FakeBrowser()
    sleeps: list[float] = []
    timestamps = iter([10.0, 10.25])
    request_started = Event()
    request_started.set()
    monkeypatch.setattr(session_control_module, "monotonic", lambda: next(timestamps))
    monkeypatch.setattr(session_control_module, "sleep", sleeps.append)
    use_case = SessionControlUseCase(session, browser, FakeValidationCodes(), FakeNotifier())

    use_case._wait_for_validation_code_request_start(request_started)

    assert sleeps == [0.75]


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
        assert str(exc) == OPERATION_CANNOT_BE_COMPLETED
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
        assert BROWSER_SESSION_CLOSED in str(exc)
    else:
        raise AssertionError("A sessão fechada deveria ser recusada")

    use_case.start()
    try:
        use_case.start()
    except BrowserSessionOpenError as exc:
        assert BROWSER_SESSION_OPEN in str(exc)
    else:
        raise AssertionError("A sessão aberta deveria ser recusada")


def test_run_bet_flow_finishes_when_payment_is_authorized():
    session = AutomationSession()
    session.mark_open()
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
    assert result.purchase_number == "123456"
    assert browser.calls[0] == "access_authenticated_home"
    assert "confirm_payment" in browser.calls
    assert browser.calls[-1] == "finish_bet"
    assert notifier.success_notifications[0].purchase_number == "123456"


def test_run_bet_flow_persists_purchase_when_service_is_configured():
    session = AutomationSession()
    session.mark_open()
    browser = FakeBrowser()
    notifier = FakeNotifier()
    repository = FakeBetRepository()
    persistence = PlacedBetService(repository=repository, selected_lottery_modality="mega-sena")
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(True),
        bet_persistence=persistence,
    )

    result = use_case.run()

    assert result.status == "finished"
    assert repository.saved[0][0] == LotteryModality.MEGA_SENA
    assert repository.saved[0][1].purchase_number == "123456"
    assert notifier.success_notifications[0].purchase_number == "123456"


def test_run_bet_flow_does_not_fail_when_persistence_fails_after_purchase():
    session = AutomationSession()
    session.mark_open()
    browser = FakeBrowser()
    notifier = FakeNotifier()
    repository = FakeBetRepository(save_error=ValueError("mongo indisponível"))
    persistence = PlacedBetService(repository=repository, selected_lottery_modality="mega-sena")
    use_case = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(True),
        bet_persistence=persistence,
    )

    result = use_case.run()

    assert result.status == "finished"
    assert notifier.success_notifications[0].purchase_number == "123456"
    assert session.status.value == "finished"


def test_run_bet_flow_starts_code_lookup_before_requesting_validation_code(monkeypatch):
    session = AutomationSession()
    session.mark_open()
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
    session.mark_open()
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


def test_placed_bet_service_delegates_purchase_with_resolved_modality():
    repository = FakeBetRepository()
    service = PlacedBetService(repository=repository, selected_lottery_modality="mega-sena")
    purchase = FakeBrowser().finish_bet()

    service.save(purchase)

    assert repository.saved == [(LotteryModality.MEGA_SENA, purchase)]


def test_placed_bet_service_rejects_invalid_modality():
    service = PlacedBetService(repository=FakeBetRepository(), selected_lottery_modality="invalida")

    try:
        service.save(FakeBrowser().finish_bet())
    except ValueError as exc:
        assert "Modalidade" in str(exc)
    else:
        raise AssertionError("Modalidade inválida deveria ser recusada")


def test_list_placed_bets_use_case_builds_filters():
    repository = FakeBetRepository()
    use_case = ListPlacedBetsUseCase(repository=repository)
    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 7, 31)

    results = use_case.run(
        lottery_modality="mega-sena",
        draw_number="1234",
        start_date=start_date,
        end_date=end_date,
    )

    assert results == repository.search_results
    assert repository.filters == BetSearchFilters(
        lottery_modality=LotteryModality.MEGA_SENA,
        draw_number="1234",
        start_date=start_date,
        end_date=end_date,
    )


def test_list_placed_bets_use_case_rejects_invalid_date_range():
    use_case = ListPlacedBetsUseCase(repository=FakeBetRepository())

    try:
        use_case.run(start_date=datetime(2026, 7, 31), end_date=datetime(2026, 7, 1))
    except ValueError as exc:
        assert "data inicial" in str(exc)
    else:
        raise AssertionError("Intervalo inválido deveria ser recusado")


def test_get_placed_bet_use_case_delegates_search_by_bet_id():
    repository = FakeBetRepository()
    use_case = GetPlacedBetUseCase(repository=repository)

    result = use_case.run(bet_id="64ef8f7a6f9a8f0f8f0f8f0f")

    assert result == repository.search_results[0]
    assert repository.requested_bet_id == "64ef8f7a6f9a8f0f8f0f8f0f"


def test_get_placed_bet_use_case_rejects_empty_bet_id():
    use_case = GetPlacedBetUseCase(repository=FakeBetRepository())

    try:
        use_case.run(bet_id="   ")
    except ValueError as exc:
        assert "obrigatório" in str(exc)
    else:
        raise AssertionError("Identificador vazio deveria ser recusado")


def test_bet_model_converts_mongodb_decimal128_to_decimal():
    assert BetModel.parse_decimal128(Decimal128("123.45")) == Decimal("123.45")
