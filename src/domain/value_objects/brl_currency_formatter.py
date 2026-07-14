from __future__ import annotations

from decimal import Decimal


class BrlCurrencyFormatter:
    @staticmethod
    def parse_brl_currency(value: str) -> Decimal | None:
        if not value.strip():
            return None

        normalized_value = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return Decimal(normalized_value)

    @staticmethod
    def format_brl_currency(value: Decimal | None) -> str:
        amount = value or Decimal("0")
        formatted_amount = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R$ {formatted_amount}"
