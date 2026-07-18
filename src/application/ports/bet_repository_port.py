"""Porta de persistência de apostas realizadas."""

from __future__ import annotations

from typing import Protocol

from application.dto import BetSearchFilters, PlacedBetResult, PurchaseResult
from domain import LotteryModality


class BetRepositoryPort(Protocol):
    def save(self, lottery_modality: LotteryModality, purchase: PurchaseResult) -> None:
        """Persiste as apostas de uma compra."""

    def find_all(self, filters: BetSearchFilters) -> list[PlacedBetResult]:
        """Busca apostas pelos filtros informados."""

    def find_by_id(self, bet_id: str) -> PlacedBetResult | None:
        """Busca uma aposta pelo identificador persistido."""
