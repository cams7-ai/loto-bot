"""Serviço de aplicação para persistir apostas realizadas."""

from __future__ import annotations

from application.dto import PurchaseResult
from application.ports import BetRepositoryPort
from domain import LotteryModality


class PlacedBetService:
    def __init__(self, repository: BetRepositoryPort, selected_lottery_modality: str) -> None:
        self._repository = repository
        self._selected_lottery_modality = selected_lottery_modality

    def save(self, purchase: PurchaseResult, selected_lottery_modality: LotteryModality | None = None) -> None:
        lottery_modality = selected_lottery_modality or LotteryModality.from_string(self._selected_lottery_modality)
        if lottery_modality is None:
            raise ValueError("Modalidade de loteria inválida.")

        self._repository.save(lottery_modality, purchase)
