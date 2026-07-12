from infrastructure.selectors.caixa_selectors import Selectors
from infrastructure.selectors.lottery_modality_builder import LotteryModalityBuilder

get_lottery_modality = LotteryModalityBuilder.get_lottery_modality

__all__ = ["Selectors", "get_lottery_modality"]
