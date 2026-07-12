from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from infrastructure.browser.portal_data import PurchaseDetails, purchase_datetime


def test_purchase_datetime_uses_sao_paulo_timezone() -> None:
    result = purchase_datetime("12/07/2026", "18:08:14")

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
    assert details.datetime == datetime(2026, 7, 12, 18, 8, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert not hasattr(details, "date")
    assert not hasattr(details, "time")
