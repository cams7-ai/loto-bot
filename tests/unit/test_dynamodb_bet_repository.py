from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from api.dependencies import _build_bet_repository
from application.dto import BetResult, BetSearchFilters, PurchaseResult
from domain import LotteryModality
from infrastructure.config import Settings
from infrastructure.database import BeanieBetRepository, DynamoDbBetRepository


class FakeBatch:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def put_item(self, *, Item: dict) -> None:
        self.items.append(Item)


class FakeTable:
    def __init__(self, pages: list[dict] | None = None, item: dict | None = None) -> None:
        self.written: list[dict] = []
        self.pages = pages or [{"Items": []}]
        self.item = item
        self.scan_calls: list[dict] = []

    def batch_writer(self) -> FakeBatch:
        return FakeBatch(self.written)

    def get_item(self, *, Key: dict) -> dict:
        return {"Item": self.item} if self.item is not None else {}

    def scan(self, **kwargs) -> dict:
        self.scan_calls.append(kwargs)
        return self.pages[len(self.scan_calls) - 1]


class FakeResource:
    def __init__(self, table: FakeTable) -> None:
        self.table = table
        self.names: list[str] = []

    def Table(self, name: str) -> FakeTable:
        self.names.append(name)
        return self.table


def purchase(*bets: BetResult) -> PurchaseResult:
    return PurchaseResult(
        lottery_modality="mega-sena",
        bets=list(bets),
        purchase_number="123456",
        purchase_datetime=datetime(2026, 9, 24, 7, 30, tzinfo=UTC),
        total_purchase=None,
        total_bets_effective=None,
    )


def item(bet_id: str, *, draw: str = "2920", date: datetime | None = None) -> dict:
    return {
        "bet_id": bet_id,
        "lottery_modality": "mega-sena",
        "selected_numbers": ["01", "05", "12", "30", "45", "59"],
        "draw_number": draw,
        "status": "Efetivada",
        "bet_amount": Decimal("6.00"),
        "purchase_number": "123456",
        "bet_date": (date or datetime(2026, 9, 24, 7, 30, tzinfo=UTC)).isoformat(),
    }


def repository(table: FakeTable) -> DynamoDbBetRepository:
    return DynamoDbBetRepository("loto-bot-bets", FakeResource(table))


def test_save_writes_one_item_per_bet_with_native_dynamodb_types() -> None:
    table = FakeTable()
    repo = repository(table)
    repo.save(
        LotteryModality.MEGA_SENA,
        purchase(
            BetResult(["01", "02"], "2920", "Efetivada", Decimal("6")),
            BetResult(["03", "04"], "2921", "Efetivada", Decimal("7.50")),
        ),
    )

    assert len(table.written) == 2
    assert table.written[0]["lottery_modality"] == "mega-sena"
    assert table.written[0]["bet_amount"] == Decimal("6.00")
    assert table.written[0]["purchase_number"] == "123456"
    assert table.written[0]["bet_date"] == "2026-09-24T07:30:00+00:00"
    assert len(table.written[0]["bet_id"]) == 32


def test_save_skips_empty_purchase_and_rejects_missing_amount() -> None:
    table = FakeTable()
    repo = repository(table)
    repo.save(LotteryModality.MEGA_SENA, purchase())
    assert table.written == []

    with pytest.raises(ValueError, match="Valor da aposta é obrigatório"):
        repo.save(LotteryModality.MEGA_SENA, purchase(BetResult([], "1", "x", None)))


def test_find_by_id_maps_item_and_handles_missing_or_invalid_id() -> None:
    result = repository(FakeTable(item=item("abc"))).find_by_id("abc")
    assert result is not None
    assert result.bet_id == "abc"
    assert result.bet_amount == Decimal("6.00")
    assert repository(FakeTable()).find_by_id("missing") is None
    with pytest.raises(ValueError, match="Identificador da aposta inválido"):
        repository(FakeTable()).find_by_id(" ")


def test_find_all_paginates_filters_and_sorts_descending() -> None:
    newest = datetime(2026, 9, 24, 8, tzinfo=UTC)
    oldest = newest - timedelta(days=2)
    table = FakeTable(
        pages=[
            {"Items": [item("old", date=oldest)], "LastEvaluatedKey": {"bet_id": "old"}},
            {"Items": [item("other", draw="1"), item("new", date=newest)]},
        ]
    )
    results = repository(table).find_all(
        BetSearchFilters(
            lottery_modality=LotteryModality.MEGA_SENA,
            draw_number=2920,
            start_date=oldest,
            end_date=newest,
        )
    )

    assert [result.bet_id for result in results] == ["new", "old"]
    assert table.scan_calls == [{}, {"ExclusiveStartKey": {"bet_id": "old"}}]


def test_repository_selection_depends_only_on_integration_mode() -> None:
    assert isinstance(_build_bet_repository(Settings(INTEGRATION_MODE="LOCAL")), BeanieBetRepository)
    assert isinstance(_build_bet_repository(Settings(INTEGRATION_MODE="AWS")), DynamoDbBetRepository)
    with pytest.raises(ValueError, match="Nome da tabela DynamoDB inválido"):
        _build_bet_repository(Settings(INTEGRATION_MODE="AWS", DYNAMODB_TABLE_NAME=" "))


def test_resource_is_created_lazily_with_dualstack(monkeypatch: pytest.MonkeyPatch) -> None:
    table = FakeTable(pages=[{"Items": []}, {"Items": []}])
    resource = FakeResource(table)
    calls: list[tuple[str, object]] = []

    def fake_resource(service_name: str, *, config: object) -> FakeResource:
        calls.append((service_name, config))
        return resource

    monkeypatch.setattr("infrastructure.database.repositories.dynamodb_bet_repository.boto3.resource", fake_resource)
    repo = DynamoDbBetRepository("loto-bot-bets")

    assert repo.find_all(BetSearchFilters()) == []
    assert calls[0][0] == "dynamodb"
    assert calls[0][1].use_dualstack_endpoint is True
    assert repo.find_all(BetSearchFilters()) == []
    assert len(calls) == 1
