"""Repositorio DynamoDB para apostas realizadas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config

from application.dto import BetSearchFilters, PlacedBetResult, PurchaseResult
from application.ports import BetRepositoryPort
from domain import LotteryModality
from shared import with_utc


class DynamoDbBetRepository(BetRepositoryPort):
    def __init__(self, table_name: str, resource: Any | None = None) -> None:
        if not table_name.strip():
            raise ValueError("Nome da tabela DynamoDB inválido.")
        self._table_name = table_name
        self._resource = resource
        self._table_instance: Any | None = None

    def save(self, lottery_modality: LotteryModality, purchase: PurchaseResult) -> None:
        if not purchase.bets:
            return

        items = []
        for bet in purchase.bets:
            if bet.amount is None:
                raise ValueError("Valor da aposta é obrigatório para persistência.")
            items.append(
                {
                    "bet_id": uuid4().hex,
                    "lottery_modality": lottery_modality.value,
                    "selected_numbers": list(bet.numbers),
                    "draw_number": str(bet.draw),
                    "status": bet.status,
                    "bet_amount": Decimal(str(bet.amount)).quantize(Decimal("0.01")),
                    "purchase_number": purchase.purchase_number,
                    "bet_date": purchase.purchase_datetime.isoformat(),
                }
            )

        with self._table().batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)

    def find_by_id(self, bet_id: str) -> PlacedBetResult | None:
        if not bet_id.strip():
            raise ValueError("Identificador da aposta inválido.")
        item = self._table().get_item(Key={"bet_id": bet_id}).get("Item")
        return self._to_result(item) if item is not None else None

    def find_all(self, filters: BetSearchFilters) -> list[PlacedBetResult]:
        # TODO: substituir o scan por GSIs para modalidade/data, concurso e compra quando o volume justificar.
        items: list[dict[str, Any]] = []
        scan_arguments: dict[str, Any] = {}
        while True:
            response = self._table().scan(**scan_arguments)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_arguments = {"ExclusiveStartKey": last_key}

        results = [self._to_result(item) for item in items]
        return sorted(
            (result for result in results if self._matches(result, filters)),
            key=lambda result: result.bet_date,
            reverse=True,
        )

    def _table(self) -> Any:
        if self._table_instance is None:
            if self._resource is None:
                self._resource = boto3.resource(
                    "dynamodb",
                    config=Config(use_dualstack_endpoint=True),
                )
            self._table_instance = self._resource.Table(self._table_name)
        return self._table_instance

    @staticmethod
    def _matches(result: PlacedBetResult, filters: BetSearchFilters) -> bool:
        return not (
            (filters.lottery_modality is not None and result.lottery_modality != filters.lottery_modality)
            or (filters.draw_number is not None and result.draw_number != str(filters.draw_number))
            or (filters.start_date is not None and result.bet_date < with_utc(filters.start_date))
            or (filters.end_date is not None and result.bet_date > with_utc(filters.end_date))
        )

    @staticmethod
    def _to_result(item: dict[str, Any]) -> PlacedBetResult:
        return PlacedBetResult(
            bet_id=str(item["bet_id"]),
            lottery_modality=LotteryModality(str(item["lottery_modality"])),
            selected_numbers=[str(number) for number in item["selected_numbers"]],
            draw_number=str(item["draw_number"]),
            status=str(item["status"]),
            bet_amount=Decimal(str(item["bet_amount"])).quantize(Decimal("0.01")),
            purchase_number=str(item["purchase_number"]),
            bet_date=with_utc(datetime.fromisoformat(str(item["bet_date"])), remove_microseconds=True),
        )
