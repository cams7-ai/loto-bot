from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pytest

from application.dto import PortalBetSearchFilters
from domain import AutomationError
from domain.enums import PortalBetSortOrder, PortalYearMonth
from infrastructure.browser.portal_bets_browser import PortalBetsBrowserMixin


def _row_with_cells(cell_count: int, *, colspan: str | None = None) -> Mock:
    row = Mock()
    cells = Mock()
    cells.count.return_value = cell_count
    cells.first.get_attribute.return_value = colspan
    row.locator.return_value = cells
    return row


def _valid_bet_row() -> Mock:
    row = _row_with_cells(6)
    cells = row.locator.return_value
    cell_items = [Mock() for _ in range(6)]
    cells.nth.side_effect = cell_items
    cell_items[1].locator.return_value.all_inner_texts.return_value = ["24/07/2026", "21:30:00"]
    cell_items[2].inner_text.return_value = "Mega-Sena"
    cell_items[3].locator.return_value.all_inner_texts.return_value = ["01", "02", "03", "04", "05", "06"]
    cell_items[4].inner_text.return_value = "2890"
    cell_items[5].inner_text.return_value = "Aposta\nPaga"
    return row


def test_parse_portal_bet_rows_ignores_auxiliary_colspan_row_and_keeps_bet():
    page = Mock()
    rows = Mock()
    rows.count.return_value = 2
    rows.nth.side_effect = [_row_with_cells(1, colspan="6"), _valid_bet_row()]
    page.locator.return_value = rows

    results = PortalBetsBrowserMixin._parse_portal_bet_rows(page)

    assert len(results) == 1
    assert results[0].lottery_modality == "Mega-Sena"
    assert results[0].selected_numbers == ["01", "02", "03", "04", "05", "06"]
    assert results[0].draw_number == "2890"
    assert results[0].status == "Aposta Paga"


def test_parse_portal_bet_rows_rejects_malformed_bet_row_without_colspan():
    page = Mock()
    rows = Mock()
    rows.count.return_value = 1
    rows.nth.return_value = _row_with_cells(1)
    page.locator.return_value = rows

    with pytest.raises(AutomationError, match="Linha de aposta malformada"):
        PortalBetsBrowserMixin._parse_portal_bet_rows(page)


def test_parse_portal_bet_rows_when_stable_retries_transient_malformed_row(monkeypatch):
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(browser_timeout_seconds=1)
    page = Mock()
    expected_results = [Mock()]
    parse = Mock(side_effect=[AutomationError("Linha de aposta malformada na tabela do portal."), expected_results])
    monkeypatch.setattr(PortalBetsBrowserMixin, "_parse_portal_bet_rows", parse)

    results = browser._parse_portal_bet_rows_when_stable(page)

    assert results == expected_results
    assert parse.call_count == 2
    page.wait_for_timeout.assert_called_once_with(250)


def test_parse_portal_bet_rows_when_stable_retries_transient_locator_timeout(monkeypatch):
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(browser_timeout_seconds=1)
    page = Mock()
    expected_results = [Mock()]
    parse = Mock(side_effect=[TimeoutError("Locator.inner_text: Timeout exceeded"), expected_results])
    monkeypatch.setattr(PortalBetsBrowserMixin, "_parse_portal_bet_rows", parse)

    results = browser._parse_portal_bet_rows_when_stable(page)

    assert results == expected_results
    assert parse.call_count == 2
    page.wait_for_timeout.assert_called_once_with(250)


def test_parse_portal_bet_rows_when_stable_retries_until_month_filter_matches(monkeypatch):
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(browser_timeout_seconds=1)
    page = Mock()
    stale_result = Mock(purchase_datetime=datetime(2026, 5, 31, 13, 57, 34))
    expected_result = Mock(purchase_datetime=datetime(2026, 6, 14, 20, 7, 52))
    parse = Mock(side_effect=[[stale_result], [expected_result], [expected_result]])
    monkeypatch.setattr(PortalBetsBrowserMixin, "_parse_portal_bet_rows", parse)

    results = browser._parse_portal_bet_rows_when_stable(
        page,
        PortalBetSearchFilters(month_year=PortalYearMonth(year=2026, month=6)),
    )

    assert results == [expected_result]
    assert parse.call_count == 3
    assert page.wait_for_timeout.call_count == 2


def test_parse_portal_bet_rows_when_stable_retries_until_sort_filter_matches(monkeypatch):
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(browser_timeout_seconds=1)
    page = Mock()
    newer_result = Mock(purchase_datetime=datetime(2026, 7, 24, 14, 23, 57))
    older_result = Mock(purchase_datetime=datetime(2026, 7, 18, 16, 23, 34))
    parse = Mock(side_effect=[[newer_result, older_result], [older_result, newer_result], [older_result, newer_result]])
    monkeypatch.setattr(PortalBetsBrowserMixin, "_parse_portal_bet_rows", parse)

    results = browser._parse_portal_bet_rows_when_stable(
        page,
        PortalBetSearchFilters(sort_by=PortalBetSortOrder.DATE_ASC),
    )

    assert results == [older_result, newer_result]
    assert parse.call_count == 3
    assert page.wait_for_timeout.call_count == 2


def test_parse_portal_bet_rows_when_stable_retries_until_result_count_settles(monkeypatch):
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(browser_timeout_seconds=1)
    page = Mock()
    first_result = Mock(
        purchase_datetime=datetime(2026, 7, 24, 14, 23, 57),
        lottery_modality="Mega-Sena",
        selected_numbers=["01", "06", "30", "32", "45", "54"],
        draw_number="3036",
        status="Concurso nao apurado",
    )
    second_result = Mock(
        purchase_datetime=datetime(2026, 7, 19, 12, 33, 9),
        lottery_modality="Mega-Sena",
        selected_numbers=["09", "18", "33", "40", "47", "53"],
        draw_number="3034",
        status="Aposta nao premiada",
    )
    full_results = [first_result, second_result]
    parse = Mock(side_effect=[[first_result], full_results, full_results])
    monkeypatch.setattr(PortalBetsBrowserMixin, "_parse_portal_bet_rows", parse)

    results = browser._parse_portal_bet_rows_when_stable(
        page,
        PortalBetSearchFilters(sort_by=PortalBetSortOrder.DATE_DESC),
    )

    assert results == full_results
    assert parse.call_count == 3
    assert page.wait_for_timeout.call_count == 2


def test_select_option_when_available_retries_until_filter_option_is_ready():
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(browser_timeout_seconds=1)
    page = Mock()
    element = Mock()
    element.select_option.side_effect = [Exception("option not ready"), None]
    page.locator.return_value = element

    browser._select_option_when_available(page, "//select[@id='tipoConcurso']", "Especial")

    assert element.select_option.call_count == 2
    page.wait_for_timeout.assert_called_once_with(250)


def test_find_all_portal_bets_rejects_when_apply_filter_button_cannot_be_clicked(monkeypatch):
    browser = object.__new__(PortalBetsBrowserMixin)
    browser._settings = Mock(
        portal_bets_url="https://example.test/bets",
        portal_bets_path="/bets",
        browser_timeout_seconds=1,
    )
    browser._require_page = Mock(return_value=Mock())
    browser._goto = Mock()
    browser._check_redirected_page = Mock()
    browser._filters_are_selected = Mock(return_value=False)
    browser._select_filters = Mock()
    browser._click = Mock(return_value=False)
    monkeypatch.setattr(PortalBetsBrowserMixin, "_parse_portal_bet_rows", Mock())

    with pytest.raises(AutomationError, match="aplicar os filtros"):
        browser._find_all_portal_bets(Mock(), PortalBetSearchFilters(has_explicit_filters=True))


def test_filters_are_selected_compares_draw_type_when_filter_exists(monkeypatch):
    page = Mock()
    draw_type = Mock()
    draw_type.count.return_value = 1

    def selected_label(_: Mock, selector: str) -> str:
        return {
            "//select[@id='tipoAposta']": "Aposta Individual",
            "//select[@id='modalidades']": "Mega-Sena",
            "//select[@id='periodos']": "Ultimos 90 dias",
            "//select[@id='situacoes']": "Todas",
            "//select[@id='ordenacoes']": "Data Decrescente",
            "//select[@id='tipoConcurso']": "Especial",
        }[selector]

    page.locator.return_value = draw_type
    browser = object.__new__(PortalBetsBrowserMixin)
    labels = {
        "bet_type": "Aposta Individual",
        "lottery_modality": "Mega-Sena",
        "draw_type": "Normal",
        "month_year": "Ultimos 90 dias",
        "status": "Todas",
        "sort_by": "Data Decrescente",
    }
    monkeypatch.setattr(PortalBetsBrowserMixin, "_selected_label", selected_label)
    assert browser._filters_are_selected(page, labels) is False
