"""Caso de uso para listar apostas realizadas."""

from __future__ import annotations

from datetime import datetime

from application.dto import BetSearchFilters, PlacedBetResult
from application.ports import BetRepositoryPort
from domain import LotteryModality


class ListPlacedBetsUseCase:
    def __init__(self, repository: BetRepositoryPort) -> None:
        self._repository = repository

    def run(
        self,
        *,
        lottery_modality: str | None = None,
        draw_number: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[PlacedBetResult]:
        resolved_lottery_modality = self._resolve_lottery_modality(lottery_modality)
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("A data inicial não pode ser maior que a data final.")

        filters = BetSearchFilters(
            lottery_modality=resolved_lottery_modality,
            draw_number=draw_number,
            start_date=start_date,
            end_date=end_date,
        )
        return self._repository.find_all(filters)

    @staticmethod
    def _resolve_lottery_modality(lottery_modality: str | None) -> LotteryModality | None:
        if lottery_modality is None:
            return None

        resolved_lottery_modality = LotteryModality.from_string(lottery_modality)
        if resolved_lottery_modality is None:
            raise ValueError("Modalidade de loteria inválida.")
        return resolved_lottery_modality
