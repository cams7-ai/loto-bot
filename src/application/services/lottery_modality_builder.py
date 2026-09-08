import re

from application.services.portal_bet_filter_catalog import normalize_public_value
from domain import LotteryModality


class LotteryModalityBuilder:
    _BET_CARD_LABELS = {
        LotteryModality.MEGA_SENA: "mega-sena",
        LotteryModality.QUINA: "quina",
        LotteryModality.QUINA_ESPECIAL: "quina de são joão",
        LotteryModality.LOTECA: "loteca",
        LotteryModality.LOTECA_ESPECIAL: "loteca especial",
        LotteryModality.LOTOFACIL: "lotofácil",
        LotteryModality.LOTOFACIL_ESPECIAL: "lotofácil da independência",
        LotteryModality.MAIS_MILIONARIA: "+milionária",
        LotteryModality.LOTOMANIA: "lotomania",
        LotteryModality.TIMEMANIA: "timemania",
        LotteryModality.DUPLA_SENA: "dupla sena",
        LotteryModality.DIA_DE_SORTE: "dia de sorte",
        LotteryModality.SUPER_SETE: "super sete",
    }
    _PORTAL_FILTER_LABELS = {
        LotteryModality.MEGA_SENA: "Mega-Sena",
        LotteryModality.QUINA: "Quina",
        LotteryModality.QUINA_ESPECIAL: "Quina de São João",
        LotteryModality.LOTECA: "Loteca",
        LotteryModality.LOTECA_ESPECIAL: "Loteca Especial",
        LotteryModality.LOTOFACIL: "Lotofácil",
        LotteryModality.LOTOFACIL_ESPECIAL: "Lotofácil da Independência",
        LotteryModality.MAIS_MILIONARIA: "+Milionária",
        LotteryModality.LOTOMANIA: "Lotomania",
        LotteryModality.TIMEMANIA: "Timemania",
        LotteryModality.DUPLA_SENA: "Dupla Sena",
        LotteryModality.DIA_DE_SORTE: "Dia de Sorte",
        LotteryModality.SUPER_SETE: "Super Sete",
    }

    @classmethod
    def get_lottery_modality(cls, lottery_modality: LotteryModality | None) -> str | None:
        if lottery_modality is None:
            return None
        return cls._BET_CARD_LABELS[lottery_modality]

    @classmethod
    def portal_filter_label(cls, lottery_modality: LotteryModality | None) -> str:
        if lottery_modality is None:
            return "Todas"
        return cls._PORTAL_FILTER_LABELS[lottery_modality]

    @classmethod
    def from_portal_label(cls, value: str) -> LotteryModality | None:
        normalized = cls._normalized(value)
        for modality in LotteryModality:
            aliases = {
                modality.name,
                modality.value,
                cls._BET_CARD_LABELS[modality],
                cls._PORTAL_FILTER_LABELS[modality],
            }
            if normalized in {cls._normalized(alias) for alias in aliases}:
                return modality
        return None

    @staticmethod
    def _normalized(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", normalize_public_value(value))
