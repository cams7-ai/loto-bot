"""Caso de uso para listar apostas realizadas."""

from application.dto import BetSearchFilters, PlacedBetResult
from application.ports import BetRepositoryPort


class ListPlacedBetsUseCase:
    def __init__(self, repository: BetRepositoryPort) -> None:
        self._repository = repository

    def run(
        self,
        filters: BetSearchFilters,
    ) -> list[PlacedBetResult]:
        return self._repository.find_all(filters)
