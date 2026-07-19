from __future__ import annotations

from enum import Enum


class LotteryModality(Enum):
    MEGA_SENA = "mega-sena"
    QUINA = "quina"
    QUINA_ESPECIAL = "quina/especial"
    LOTECA = "loteca"
    LOTECA_ESPECIAL = "loteca/especial"
    LOTOFACIL = "lotofacil"
    MAIS_MILIONARIA = "mais-milionaria"
    LOTOMANIA = "lotomania"
    TIMEMANIA = "timemania"
    DUPLA_SENA = "dupla-sena"
    DIA_DE_SORTE = "dia-de-sorte"
    SUPER_SETE = "super-sete"

    @classmethod
    def from_string(cls, value: str) -> LotteryModality | None:
        normalized_value = value.strip()
        for lottery_modality in cls:
            if lottery_modality.value == normalized_value:
                return lottery_modality
        return None
