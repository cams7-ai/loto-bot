from __future__ import annotations

from datetime import date, datetime

from shared import sao_paulo_timezone


class SaoPauloClock:
    def today(self) -> date:
        """Retorna a data atual no timezone de São Paulo."""
        return datetime.now(sao_paulo_timezone()).date()
