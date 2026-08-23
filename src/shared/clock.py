from datetime import date, datetime

from shared.datetime_utils import sao_paulo_timezone


class SaoPauloClock:
    @staticmethod
    def today() -> date:
        """Retorna a data atual no timezone de São Paulo."""
        return datetime.now(sao_paulo_timezone()).date()
