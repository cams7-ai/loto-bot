"""Caso de uso para consultar uma aposta realizada."""

from __future__ import annotations

from application.dto import PlacedBetResult
from application.ports import BetRepositoryPort


class GetPlacedBetUseCase:
    def __init__(self, repository: BetRepositoryPort) -> None:
        self._repository = repository

    def run(self, *, bet_id: str) -> PlacedBetResult | None:
        normalized_bet_id = bet_id.strip()
        if not normalized_bet_id:
            raise ValueError("Identificador da aposta é obrigatório.")

        return self._repository.find_by_id(normalized_bet_id)
