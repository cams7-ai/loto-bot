from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import infrastructure.browser.playwright_common as common_module
import infrastructure.browser.run_bet_flow_browser as run_browser_module
import infrastructure.browser.session_control_browser as session_browser_module
import infrastructure.clients.notification_gateway as notification_module
from application import PortalBetSearchFilters
from application.use_cases import CheckBetDrawsUseCase, RunBetFlowUseCase
from domain import (
    AutomationError,
    AutomationSession,
    BetsNotAvailableForCaptureError,
    BetTemporarilyDisabledError,
    BrowserSessionClosedError,
    DailyPurchaseLimitError,
    IndividualBetRegistrationClosedError,
    InvalidCPFError,
    LotteryModality,
    NotificationChannel,
    Operation,
    PageRedirectionError,
    PaymentAuthorization,
    PortalDrawType,
)
from infrastructure import NotificationGateway, Settings
from infrastructure.browser.playwright_common import PlaywrightBrowserBase
from infrastructure.browser.portal_bets_browser import PortalBetsBrowserMixin
from infrastructure.browser.portal_data import Bet, PurchaseDetails, PurchaseTotals
from infrastructure.browser.run_bet_flow_browser import RunBetFlowBrowserMixin
from infrastructure.browser.session_control_browser import SessionControlBrowserMixin
from infrastructure.selectors import Selectors


class Locator:
    def __init__(
        self,
        *,
        count=1,
        inner_text="text",
        texts=None,
        text_content=None,
        attribute=None,
        evaluate="",
        wait_error=None,
        fill_error=None,
        select_error=None,
    ):
        self.first = self
        self._count = count
        self._inner_text = inner_text
        self._texts = texts or []
        self._text_content = text_content
        self._attribute = attribute
        self._evaluate = evaluate
        self._wait_error = wait_error
        self._fill_error = fill_error
        self._select_error = select_error
        self.calls = []

    def count(self):
        return self._count

    def inner_text(self):
        if isinstance(self._inner_text, list):
            return self._inner_text.pop(0)
        return self._inner_text

    def all_inner_texts(self):
        return self._texts

    def text_content(self):
        return self._text_content

    def get_attribute(self, name):
        return self._attribute

    def evaluate(self, script):
        return self._evaluate

    def wait_for(self, **kwargs):
        self.calls.append(("wait_for", kwargs))
        if self._wait_error:
            raise self._wait_error

    def scroll_into_view_if_needed(self, **kwargs):
        self.calls.append(("scroll", kwargs))

    def click(self):
        self.calls.append(("click", None))

    def fill(self, value):
        if self._fill_error:
            raise self._fill_error
        self.calls.append(("fill", value))

    def press_sequentially(self, value, delay):
        self.calls.append(("press", value, delay))

    def type(self, value, delay):
        self.calls.append(("type", value, delay))

    def select_option(self, **kwargs):
        if self._select_error:
            raise self._select_error
        self.calls.append(("select", kwargs))


class Page:
    def __init__(self, locators=None, *, url="https://example.test/#/path/123"):
        self.locators = locators or {}
        self.url = url
        self.calls = []

    def locator(self, selector):
        return self.locators.get(selector, Locator())

    def wait_for_timeout(self, timeout):
        self.calls.append(("wait", timeout))

    def wait_for_url(self, pattern, timeout):
        self.calls.append(("wait_for_url", pattern, timeout))

    def goto(self, url, **kwargs):
        self.calls.append(("goto", url, kwargs))

    def wait_for_function(self, script, **kwargs):
        self.calls.append(("wait_for_function", script, kwargs))


def browser_settings(tmp_path=None):
    values = {
        "BROWSER_TIMEOUT_SECONDS": 1,
        "ONLINE_LOTTERY_URL": "https://example.test",
        "ONLINE_LOTTERY_PATH": "/#",
    }
    if tmp_path is not None:
        values["BROWSER_PROFILE_DIR"] = tmp_path
    return Settings(**values)


def test_playwright_common_all_helpers(monkeypatch):
    page = Page({"missing": Locator(count=0), "present": Locator(inner_text=" value ")})
    assert PlaywrightBrowserBase._optional_inner_text(page, "missing") == ""
    assert PlaywrightBrowserBase._optional_inner_text(page, "present") == "value"

    assert PlaywrightBrowserBase._required_inner_text(page, 1000, "present") == "value"
    empty = Locator(inner_text="")
    page.locators["empty"] = empty
    times = iter([0.0, 0.1, 1.1])
    monkeypatch.setattr(common_module, "monotonic", lambda: next(times))
    assert PlaywrightBrowserBase._required_inner_text(page, 1000, "empty") == ""
    assert page.calls[-1] == ("wait", 100)

    assert PlaywrightBrowserBase._fill(page, "present", "abc") is True
    page.locators["broken"] = Locator(fill_error=RuntimeError("fail"))
    assert PlaywrightBrowserBase._fill(page, "broken", "abc") is False

    element = Locator()
    page.locators["typed"] = element
    assert PlaywrightBrowserBase._type(page, 1000, "typed", "abc") is True
    assert ("press", "abc", 50) in element.calls
    element.press_sequentially = None
    assert PlaywrightBrowserBase._type(page, 1000, "typed", "xyz") is True
    assert ("type", "xyz", 50) in element.calls

    base = PlaywrightBrowserBase(browser_settings())
    with pytest.raises(AutomationError):
        base._require_page()
    base._page = page
    assert base._require_page() is page

    session = AutomationSession()
    callback = Mock()
    PlaywrightBrowserBase._check_redirected_page(page, 1000, session, "/path", callback)
    callback.assert_called_once_with(page.url, session)
    PlaywrightBrowserBase._goto(page, 1000, "https://target")
    assert base._run_on_browser_thread(lambda value: value + 1, 1) == 2
    assert base._timeout_ms == 1000
    assert base._short_timeout_ms == 1000
    base._executor.shutdown()


def test_common_redirect_and_click_failures():
    class BrokenPage(Page):
        def wait_for_url(self, pattern, timeout):
            raise RuntimeError("timeout")

    with pytest.raises(PageRedirectionError):
        PlaywrightBrowserBase._check_redirected_page(BrokenPage(), 1, AutomationSession(), "/expected")

    page = Page({"button": Locator(wait_error=RuntimeError("missing"))})
    assert PlaywrightBrowserBase._click(page, 1, "button") is False


def immediate(browser):
    browser._run_on_browser_thread = lambda action, *args: action(*args)
    return browser


def test_run_bet_browser_public_wrappers_and_happy_path(monkeypatch):
    browser = immediate(RunBetFlowBrowserMixin(browser_settings()))
    browser._page = Page()
    browser._check_redirected_page = Mock()
    browser._click = Mock(return_value=False)
    browser._type = Mock(return_value=True)
    session = AutomationSession()

    browser.select_lottery_modality(session, LotteryModality.MEGA_SENA)
    browser.place_bet(session, LotteryModality.MEGA_SENA)
    browser.confirm_purchase(session)
    browser.confirm_payment()
    browser.check_bet_processing(session)
    monkeypatch.setattr(browser, "_wait_for_purchase_tracking", Mock(return_value="123"))
    assert browser.check_your_purchases(session) == "123"
    assert browser._click.call_count >= 10

    browser._click = Mock(side_effect=[True, True, True, True])
    browser._place_bet(session, LotteryModality.MEGA_SENA)


def test_select_lottery_modality_error_branches(monkeypatch):
    browser = immediate(RunBetFlowBrowserMixin(browser_settings()))
    browser._page = Page()
    browser._check_redirected_page = Mock()
    session = AutomationSession()

    monkeypatch.setattr(run_browser_module.Selectors, "modality_button", Mock(return_value=None))
    with pytest.raises(AutomationError):
        browser._select_lottery_modality(session, LotteryModality.MEGA_SENA)

    monkeypatch.setattr(run_browser_module.Selectors, "modality_button", Mock(return_value="enabled"))
    monkeypatch.setattr(run_browser_module.Selectors, "disabled_modality_button", Mock(return_value="disabled"))
    browser._click = Mock(side_effect=[False, True])
    with pytest.raises(BetTemporarilyDisabledError):
        browser._select_lottery_modality(session, LotteryModality.MEGA_SENA)

    browser._click = Mock(side_effect=[True, True])
    with pytest.raises(IndividualBetRegistrationClosedError):
        browser._select_lottery_modality(session, LotteryModality.MEGA_SENA)


def test_confirm_purchase_alert_branches():
    browser = immediate(RunBetFlowBrowserMixin(browser_settings()))
    browser._page = Page()
    browser._check_redirected_page = Mock()
    session = AutomationSession()
    browser._click = Mock(side_effect=[False, True])
    with pytest.raises(DailyPurchaseLimitError):
        browser._confirm_purchase(session)
    browser._click = Mock(side_effect=[False, False, True])
    with pytest.raises(BetsNotAvailableForCaptureError):
        browser._confirm_purchase(session)


def test_purchase_tracking_success_failure_and_extraction():
    browser = RunBetFlowBrowserMixin(browser_settings())
    page = Page(url="https://example.test/#/acompanhamento/987/")
    assert browser._wait_for_purchase_tracking(page, 1000, "/acompanhamento/", AutomationSession()) == "987"
    assert browser.extract_purchase_number(page.url) == "987"

    def fail(*args, **kwargs):
        raise RuntimeError("timeout")

    page.wait_for_function = fail
    with pytest.raises(PageRedirectionError):
        browser._wait_for_purchase_tracking(page, 1, "/missing/", AutomationSession())


class Cells:
    def __init__(self, texts):
        self.items = [Locator(inner_text=text) for text in texts]

    def nth(self, index):
        return self.items[index]


class BetRow:
    def locator(self, selector):
        if selector == "span.margemVolante":
            return Locator(texts=[" 01 ", "", "02"])
        return Cells(["unused", "100", "Efetivada", "R$ 5,00"])


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def count(self):
        return len(self.rows)

    def nth(self, index):
        return self.rows[index]


def test_run_bet_purchase_parsers_and_finish(monkeypatch):
    browser = immediate(RunBetFlowBrowserMixin(browser_settings()))
    page = Page({Selectors.BET_TABLE_ROWS: Rows([BetRow()])})
    browser._page = page
    values = iter(
        [
            "123",
            "Efetivada",
            "23/08/2026",
            "12:30:00",
            "R$ 5,00",
            "R$ 0,00",
            "R$ 5,00",
            "R$ 0,00",
            "R$ 0,00",
        ]
    )
    browser._required_inner_text = Mock(side_effect=lambda *args: next(values))
    browser._optional_inner_text = Mock(return_value="R$ 0,00")
    details = browser._get_purchase_details(page, 1000)
    assert details == PurchaseDetails(number="123", status="Efetivada", date="23/08/2026", time="12:30:00")
    totals = browser._get_purchase_totals(page, 1000)
    assert totals.total_purchase == Decimal("5.00")
    bets = browser._get_bets(page)
    assert bets == [Bet(numbers=["01", "02"], draw="100", status="Efetivada", amount="R$ 5,00")]

    browser._check_redirected_page = Mock()
    browser._get_purchase_details = Mock(return_value=details)
    browser._get_purchase_totals = Mock(return_value=totals)
    browser._get_bets = Mock(return_value=bets)
    result = browser.finish_bet(AutomationSession(), LotteryModality.MEGA_SENA)
    assert result.purchase_number == "123"
    assert result.bets[0].numbers == ["01", "02"]


def test_portal_data_totals_constructor():
    totals = PurchaseTotals(
        total_purchase="R$ 10,00",
        total_bets_in_processing="R$ 1,00",
        total_bets_effective="R$ 8,00",
        total_bets_not_effective="R$ 1,00",
        total_refunded="R$ 2,00",
        total_in_refund="R$ 3,00",
    )
    assert totals.total_purchase == Decimal("10.00")
    assert totals.total_in_refund == Decimal("3.00")


def test_session_browser_start_cleanup_and_start_failure(monkeypatch, tmp_path):
    browser = SessionControlBrowserMixin(browser_settings(tmp_path))
    executor = SimpleNamespace(shutdown=Mock())
    browser._executor = executor
    browser._run_on_browser_thread = Mock(side_effect=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        browser.start(AutomationSession())
    executor.shutdown.assert_called_once_with(wait=True)
    assert browser._executor is None

    browser = SessionControlBrowserMixin(browser_settings(tmp_path))
    stop = Mock()
    browser._stop = stop
    monkeypatch.setattr(session_browser_module, "logging", SimpleNamespace(debug=Mock()))
    import infrastructure.browser.playwright_browser as playwright_browser

    monkeypatch.setattr(playwright_browser, "sync_playwright", Mock(side_effect=RuntimeError("start fail")))
    with pytest.raises(AutomationError):
        browser._start(AutomationSession())
    stop.assert_called_once()


def test_session_browser_misc_lifecycle_helpers():
    assert SessionControlBrowserMixin._launch_args(False) == ["--start-maximized"]
    SessionControlBrowserMixin._add_init_script(None)
    context = SimpleNamespace(add_init_script=Mock(side_effect=RuntimeError("blocked")))
    SessionControlBrowserMixin._add_init_script(context)

    browser = SessionControlBrowserMixin(browser_settings())
    stop = Mock()
    browser._stop = stop
    browser.stop()
    stop.assert_called_once()


def test_session_browser_access_authentication_and_terms():
    browser = immediate(SessionControlBrowserMixin(browser_settings()))
    page = Page()
    browser._page = page
    browser._goto = Mock()
    browser._click = Mock(return_value=True)
    browser.access_home()
    browser.access_authenticated_home()
    assert browser._goto.call_count == 2

    browser._disable_notification = Mock(return_value=True)
    browser._accept_terms_of_use = Mock(return_value=True)
    browser._click_login_button = Mock(return_value=True)
    assert browser.is_already_authenticated() is True
    assert browser.is_authenticated() is True

    browser._disable_notification = SessionControlBrowserMixin._disable_notification.__get__(browser)
    browser._accept_terms_of_use = SessionControlBrowserMixin._accept_terms_of_use.__get__(browser)
    browser._click = Mock(side_effect=[True, True, True, True])
    assert browser._disable_notification(page, 1000) is True
    assert browser._accept_terms_of_use(page, 1000) is True
    browser._click = Mock(return_value=False)
    assert browser._disable_notification(page, 1000) is False
    assert browser._accept_terms_of_use(page, 1000) is False

    browser._check_redirected_page = Mock()
    browser._click = Mock(return_value=True)
    browser.accept_terms(AutomationSession())


def test_session_browser_cpf_validation_and_submission():
    browser = immediate(SessionControlBrowserMixin(browser_settings()))
    page = Page()
    browser._page = page
    browser._check_redirected_page = Mock()
    browser._fill = Mock(return_value=True)
    browser._click = Mock(return_value=True)
    browser._raise_if_invalid_cpf = Mock()
    browser.submit_cpf(AutomationSession())

    valid = Page({Selectors.CPF_INVALID_ALERT: Locator(wait_error=RuntimeError("not visible"))})
    SessionControlBrowserMixin._raise_if_invalid_cpf(valid, 1)
    invalid = Page({Selectors.CPF_INVALID_ALERT: Locator()})
    with pytest.raises(InvalidCPFError):
        SessionControlBrowserMixin._raise_if_invalid_cpf(invalid, 1)

    assert browser.is_valid_cpf() is True
    browser._page = Page({Selectors.RECEIVE_CODE_BUTTON: Locator(wait_error=RuntimeError("missing"))})
    assert browser.is_valid_cpf() is False
    assert browser.validation_code_lookup_lead() == browser._settings.validation_code_lookup_lead_seconds * 1000


def test_session_browser_code_password_cart_and_forbidden():
    browser = immediate(SessionControlBrowserMixin(browser_settings()))
    page = Page({Selectors.SHOPPING_CART_BUTTON: Locator(text_content="Carrinho 3")})
    browser._page = page
    browser._check_redirected_page = Mock()
    browser._raise_if_forbidden = Mock()
    browser._click = Mock(return_value=True)
    browser._fill = Mock(return_value=True)
    browser._raise_if_invalid_password = Mock()
    session = AutomationSession()
    browser.request_validation_code(session)
    browser.submit_validation_code(session, "123456")
    browser.submit_password(session)
    assert browser._fill.call_count == 2

    browser._clear_shopping_cart = Mock()
    browser.clear_shopping_cart(session)
    browser._clear_shopping_cart.assert_called_once()
    assert browser._shopping_cart_items_count(page) == 3
    assert (
        browser._shopping_cart_items_count(Page({Selectors.SHOPPING_CART_BUTTON: Locator(text_content="vazio")})) == 0
    )

    browser._clear_shopping_cart = SessionControlBrowserMixin._clear_shopping_cart.__get__(browser)
    browser._clear_shopping_cart(page, 1000, 500, "/carrinho", session)

    SessionControlBrowserMixin._raise_if_forbidden(Page(), Operation.REQUEST_VALIDATION_CODE)
    forbidden = Page({"h1.error-header__title": Locator(inner_text=" Forbidden ")})
    with pytest.raises(AutomationError):
        SessionControlBrowserMixin._raise_if_forbidden(forbidden, Operation.REQUEST_VALIDATION_CODE)


def test_portal_browser_find_wait_and_stability(monkeypatch):
    browser = immediate(PortalBetsBrowserMixin(browser_settings()))
    page = Page()
    browser._page = page
    browser._goto = Mock()
    browser._check_redirected_page = Mock()
    browser._filters_are_selected = Mock(return_value=True)
    browser._click = Mock(return_value=True)
    browser._wait_for_portal_bets_table = Mock(return_value=False)
    assert browser.find_all(AutomationSession(), PortalBetSearchFilters()) == []

    browser._wait_for_portal_bets_table = Mock(return_value=True)
    browser._parse_portal_bet_rows_when_stable = Mock(return_value=["row"])
    assert browser.find_all(AutomationSession(), PortalBetSearchFilters()) == ["row"]
    browser._click = Mock(return_value=False)
    with pytest.raises(AutomationError):
        browser.find_all(AutomationSession(), PortalBetSearchFilters())

    assert PortalBetsBrowserMixin(browser_settings())._wait_for_portal_bets_table(Page()) is True
    broken = Page({Selectors.PORTAL_BETS_TABLE: Locator(wait_error=RuntimeError("missing"))})
    assert PortalBetsBrowserMixin(browser_settings())._wait_for_portal_bets_table(broken) is False

    browser = PortalBetsBrowserMixin(browser_settings())
    browser._parse_portal_bet_rows = Mock(side_effect=[["old"], ["new"]])
    browser._results_match_filters = Mock(return_value=True)
    browser._results_signature = Mock(side_effect=[("old",), ("new",)])
    browser._settings.browser_timeout_seconds = 0
    assert browser._parse_portal_bet_rows_when_stable(Page(), PortalBetSearchFilters()) == ["old"]

    browser._parse_portal_bet_rows = Mock(side_effect=RuntimeError("unstable"))
    with pytest.raises(AutomationError, match="instavel"):
        browser._parse_portal_bet_rows_when_stable(Page(), None)
    browser._parse_portal_bet_rows = Mock(side_effect=AutomationError("filter stale"))
    with pytest.raises(AutomationError, match="filter stale"):
        browser._parse_portal_bet_rows_when_stable(Page(), None)

    browser._settings.browser_timeout_seconds = -1
    assert browser._parse_portal_bet_rows_when_stable(Page(), None) == []


def test_portal_selected_labels_and_filter_selection(monkeypatch):
    selected = Locator(evaluate="Selecionado")
    page = Page({"select": selected})
    assert PortalBetsBrowserMixin._selected_label(page, "select") == "Selecionado"
    selected._evaluate = ""
    page.locators["select/option[@selected]"] = Locator(inner_text="Fallback")
    assert PortalBetsBrowserMixin._selected_label(page, "select") == "Fallback"
    page.locators["select"] = Locator(count=0)
    page.locators["select/option[@selected]"] = Locator(count=0)
    assert PortalBetsBrowserMixin._selected_label(page, "select") == ""

    browser = PortalBetsBrowserMixin(browser_settings())
    browser._select_option_when_available = Mock()
    filters = PortalBetSearchFilters(draw_type=PortalDrawType.NORMAL)
    browser._select_filters(
        Page(),
        {
            "bet_type": "Todas",
            "lottery_modality": "Todas",
            "draw_type": "Normal",
            "month_year": "7 dias",
            "status": "Todas",
            "sort_by": "Data",
        },
        filters,
    )
    assert browser._select_option_when_available.call_count == 6

    browser._select_option_when_available.reset_mock()
    browser._select_filters(
        Page({Selectors.PORTAL_DRAW_TYPE_FILTER: Locator(count=1)}),
        {
            "bet_type": "Todas",
            "lottery_modality": "Todas",
            "draw_type": "Todos",
            "month_year": "7 dias",
            "status": "Todas",
            "sort_by": "Data",
        },
        PortalBetSearchFilters(),
    )
    assert browser._select_option_when_available.call_count == 6

    def fail_period(page, selector, label, error_message=None):
        if selector == Selectors.PORTAL_PERIOD_FILTER:
            raise RuntimeError("missing")

    browser._select_option_when_available = fail_period
    with pytest.raises(ValueError, match="month_year"):
        browser._select_filters(
            Page(),
            {
                "bet_type": "Todas",
                "lottery_modality": "Todas",
                "draw_type": "Todos",
                "month_year": "7 dias",
                "status": "Todas",
                "sort_by": "Data",
            },
            PortalBetSearchFilters(),
        )


def test_portal_select_option_failure_types():
    browser = PortalBetsBrowserMixin(browser_settings())
    browser._settings.browser_timeout_seconds = 0
    page = Page({"select": Locator(select_error=RuntimeError("missing"))})
    with pytest.raises(ValueError, match="custom"):
        browser._select_option_when_available(page, "select", "Label", "custom")
    with pytest.raises(AutomationError, match="indisponivel"):
        browser._select_option_when_available(page, "select", "Label")
    assert page.calls


class PortalCell:
    def __init__(self, text="", *, date_parts=None, numbers=None):
        self.text = text
        self.date_parts = date_parts or []
        self.numbers = numbers or []

    def inner_text(self):
        return self.text

    def locator(self, selector):
        return Locator(texts=self.date_parts if selector == "h6" else self.numbers)


class PortalCells:
    def __init__(self, items, count=None, colspan=None):
        self.items = items
        self._count = count if count is not None else len(items)
        self.first = SimpleNamespace(get_attribute=Mock(return_value=colspan))

    def count(self):
        return self._count

    def nth(self, index):
        return self.items[index]


class PortalRow:
    def __init__(self, cells):
        self.cells = cells

    def locator(self, selector):
        return self.cells


def portal_rows_page(cells_list):
    rows = Rows([PortalRow(cells) for cells in cells_list])
    return Page({Selectors.PORTAL_BETS_TABLE_ROWS: rows})


def test_portal_row_parser_error_edges():
    auxiliary = PortalCells([PortalCell()], count=1, colspan="6")
    assert PortalBetsBrowserMixin._parse_portal_bet_rows(portal_rows_page([auxiliary])) == []

    malformed = PortalCells([PortalCell()] * 5)
    with pytest.raises(AutomationError, match="malformada"):
        PortalBetsBrowserMixin._parse_portal_bet_rows(portal_rows_page([malformed]))

    missing_date = PortalCells([PortalCell()] * 6)
    with pytest.raises(AutomationError, match="Data e hora"):
        PortalBetsBrowserMixin._parse_portal_bet_rows(portal_rows_page([missing_date]))

    items = [
        PortalCell(),
        PortalCell(date_parts=["23/08/2026", "12:00:00"]),
        PortalCell("Mega-Sena"),
        PortalCell(numbers=[]),
        PortalCell("100"),
        PortalCell("Paga"),
    ]
    with pytest.raises(AutomationError, match="incompleta"):
        PortalBetsBrowserMixin._parse_portal_bet_rows(portal_rows_page([PortalCells(items)]))


def test_use_case_remaining_edges():
    session = AutomationSession()
    run = RunBetFlowUseCase(session, SimpleNamespace(), SimpleNamespace(), PaymentAuthorization(True))
    with pytest.raises(BrowserSessionClosedError):
        run.run()
    session.mark_open()
    with pytest.raises(AutomationError):
        run._resolve_lottery_modality(LotteryModality.LOTECA)

    assert (
        CheckBetDrawsUseCase._notification_message(NotificationChannel.WHATSAPP)
        == "Conferência concluída e notificação enviada pelo WhatsApp."
    )


def test_notification_gateway_stop_warning_and_timezone_fallback(monkeypatch):
    whatsapp = SimpleNamespace(stop_session=Mock(side_effect=RuntimeError("offline")))
    mail = SimpleNamespace(send=Mock())
    gateway = NotificationGateway(whatsapp, mail)
    session = AutomationSession()
    session.whatsapp_enabled = True
    gateway.stop_whatsapp_session(session)
    assert session.whatsapp_enabled is False

    monkeypatch.setattr(
        notification_module, "sao_paulo_timezone", Mock(side_effect=notification_module.ZoneInfoNotFoundError)
    )
    error = AutomationError("failure", operation=Operation.PLACE_BET)
    assert gateway.notify_failure(False, error) is False
    assert mail.send.called

    failing_start = SimpleNamespace(start_session=Mock(side_effect=RuntimeError("offline")))
    enabled_gateway = NotificationGateway(failing_start, mail, whatsapp_enabled=True)
    enabled_gateway.start_whatsapp_session(session)
    assert session.whatsapp_enabled is False
