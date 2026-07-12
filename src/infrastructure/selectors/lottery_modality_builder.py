from domain import LotteryModality


class LotteryModalityBuilder:
    @staticmethod
    def get_lottery_modality(lottery_modality: LotteryModality | None) -> str | None:
        if lottery_modality is None:
            return None

        modality = {
            LotteryModality.MEGA_SENA: "mega-sena",
            LotteryModality.QUINA: "quina",
            LotteryModality.QUINA_ESPECIAL: "quina de são joão",
            LotteryModality.LOTECA: "loteca",
            LotteryModality.LOTECA_ESPECIAL: "loteca especial",
            LotteryModality.LOTOFACIL: "lotofácil",
            LotteryModality.MAIS_MILIONARIA: "+milionária",
            LotteryModality.LOTOMANIA: "lotomania",
            LotteryModality.TIMEMANIA: "timemania",
            LotteryModality.DUPLA_SENA: "dupla sena",
            LotteryModality.DIA_DE_SORTE: "dia de sorte",
            LotteryModality.SUPER_SETE: "super sete"
        }
        return modality.get(lottery_modality, None)
