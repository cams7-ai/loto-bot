from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from domain import BrlCurrencyFormatter
from infrastructure.browser.portal_data import (
    Bet,
    PortalDataFormatter,
    PurchaseDetails,
)


def test_purchase_datetime_uses_sao_paulo_timezone() -> None:
    result = PortalDataFormatter.parse_purchase_datetime("12/07/2026", "18:08:14")

    assert result == datetime(2026, 7, 12, 18, 8, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_purchase_details_converts_date_and_time_to_datetime() -> None:
    details = PurchaseDetails(
        number="123456",
        status="Efetivada",
        date="12/07/2026",
        time="18:08:14",
    )

    assert details.number == "123456"
    assert details.status == "Efetivada"
    assert details.bet_date == datetime(2026, 7, 12, 18, 8, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert not hasattr(details, "date")
    assert not hasattr(details, "time")


def test_parse_brl_currency_returns_none_for_empty_string() -> None:
    assert BrlCurrencyFormatter.parse_brl_currency("") is None
    assert BrlCurrencyFormatter.parse_brl_currency("   ") is None


def test_bet_amount_accepts_empty_string() -> None:
    bet = Bet(numbers=["01", "02"], draw="1234", status="Não efetivada", amount="")

    assert bet.amount is None


def test_parse_brl_currency_converts_brl_string_to_decimal() -> None:
    assert BrlCurrencyFormatter.parse_brl_currency("R$ 1.234,56") == Decimal("1234.56")


def test_format_brl_currency() -> None:
    assert BrlCurrencyFormatter.format_brl_currency(Decimal("1234.56")) == "R$ 1.234,56"
    assert BrlCurrencyFormatter.format_brl_currency(Decimal("0")) == "R$ 0,00"
    assert BrlCurrencyFormatter.format_brl_currency(None) == "R$ 0,00"
