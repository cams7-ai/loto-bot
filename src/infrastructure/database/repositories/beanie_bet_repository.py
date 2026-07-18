"""Repositório Beanie para apostas realizadas."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import anyio
from beanie import PydanticObjectId

from application.dto import BetSearchFilters, PlacedBetResult, PurchaseResult
from application.ports import BetRepositoryPort
from domain import LotteryModality
from infrastructure.database.connection import MongoDatabase
from infrastructure.database.models import BetModel

T = TypeVar("T")


class BeanieBetRepository(BetRepositoryPort):
    def __init__(self, database: MongoDatabase) -> None:
        self._database = database

    def save(self, lottery_modality: LotteryModality, purchase: PurchaseResult) -> None:
        self._run_sync(lambda: self._save(lottery_modality, purchase))

    def find_all(self, filters: BetSearchFilters) -> list[PlacedBetResult]:
        return self._run_sync(lambda: self._find_all(filters))

    def find_by_id(self, bet_id: str) -> PlacedBetResult | None:
        return self._run_sync(lambda: self._find_by_id(bet_id))

    async def _save(self, lottery_modality: LotteryModality, purchase: PurchaseResult) -> None:
        await self._database.ensure_initialized()
        bet_models = [
            BetModel.from_result(lottery_modality=lottery_modality, bet=bet, purchase=purchase) for bet in purchase.bets
        ]
        if not bet_models:
            return

        await BetModel.insert_many(bet_models)

    async def _find_all(self, filters: BetSearchFilters) -> list[PlacedBetResult]:
        await self._database.ensure_initialized()
        expressions = []
        if filters.lottery_modality is not None:
            expressions.append(BetModel.lottery_modality == filters.lottery_modality)
        if filters.draw_number is not None:
            expressions.append(BetModel.draw_number == filters.draw_number)
        if filters.start_date is not None:
            expressions.append(BetModel.bet_date >= filters.start_date)
        if filters.end_date is not None:
            expressions.append(BetModel.bet_date <= filters.end_date)

        bet_models = await BetModel.find(*expressions).sort("-bet_date").to_list()
        return [bet_model.to_search_result() for bet_model in bet_models]

    async def _find_by_id(self, bet_id: str) -> PlacedBetResult | None:
        await self._database.ensure_initialized()
        try:
            object_id = PydanticObjectId(bet_id)
        except Exception as exc:
            raise ValueError("Identificador da aposta inválido.") from exc

        bet_model = await BetModel.find_one(BetModel.bet_id == object_id)
        if bet_model is None:
            return None
        return bet_model.to_search_result()

    def _run_sync(self, action: Callable[[], Awaitable[T]]) -> T:
        try:
            return anyio.from_thread.run(action)
        except RuntimeError as exc:
            if "AnyIO worker thread" not in str(exc):
                raise
            return asyncio.run(self._run_with_close(action))

    async def _run_with_close(self, action: Callable[[], Awaitable[T]]) -> T:
        try:
            return await action()
        finally:
            await self._database.close()
