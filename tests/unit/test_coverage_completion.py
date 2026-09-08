from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from bson.decimal128 import Decimal128

import infrastructure.database.connection as connection_module
import infrastructure.database.repositories.beanie_bet_repository as repository_module
from api.exceptions import ApiError
from api.mappers import ApiResponseMapper
from api.parsers import BetRequestParser
from api.routes.bets import check_bet_draws, list_placed_bets, list_portal_bets, run_bet
from api.schemas import BetRunRequest, CheckBetDrawsRequest
from application import (
    BetResult,
    BetSearchFilters,
    ListPortalBetsUseCase,
    LotteryModalityBuilder,
    PortalBetResult,
    PortalBetSearchFilters,
    PurchaseResult,
)
from application.notification import NotificationMessageBuilder
from application.services.playwright_error_message_builder import PlaywrightErrorMessageBuilder
from application.services.portal_bet_filter_catalog import (
    current_and_previous_months,
    invalid_month_year_detail,
    parse_catalog_value,
    parse_portal_lottery_modality,
    parse_portal_month_year,
    parse_positive_int,
)
from domain import (
    AutomationError,
    AutomationSession,
    BrowserSessionClosedError,
    LotteryModality,
    Operation,
    PortalBetRelativePeriod,
    PortalBetStatus,
    PortalYearMonth,
)
from infrastructure import NotificationGateway, Selectors, Settings
from infrastructure.database.connection import MongoDatabase
from infrastructure.database.models import BetModel
from infrastructure.database.repositories.beanie_bet_repository import BeanieBetRepository
from infrastructure.selectors import PortalBetFilterBuilder
from shared import with_sao_paulo_timezone


def purchase(*, bets: list[BetResult] | None = None) -> PurchaseResult:
    return PurchaseResult(
        lottery_modality="Mega-Sena",
        bets=bets or [],
        purchase_number="123",
        purchase_datetime=datetime(2026, 8, 23, 12, 30),
        total_purchase=Decimal("5.00"),
        total_bets_effective=Decimal("5.00"),
    )


def portal_bet() -> PortalBetResult:
    return PortalBetResult(
        purchase_datetime=datetime(2026, 8, 23, 12, 30),
        lottery_modality=LotteryModality.MEGA_SENA,
        selected_numbers=["01", "02"],
        draw_number="100",
        status="Premiada",
    )


def test_response_mapper_rejects_missing_run_result():
    with pytest.raises(ApiError) as captured:
        ApiResponseMapper.run_bet_response(None)
    assert captured.value.status_code == 500


def test_parser_and_selector_small_edges():
    assert BetRequestParser._parse_history_date(None, end_of_day=False) is None
    assert parse_catalog_value("status", None, PortalBetStatus) is None
    assert parse_portal_lottery_modality(None) is None
    assert parse_positive_int(None) is None
    assert LotteryModalityBuilder.get_lottery_modality(None) is None
    assert Selectors.modality_button("inexistente") is None
    assert Selectors.disabled_modality_button("inexistente") is None
    assert "mega-sena" in Selectors.disabled_modality_button("mega-sena")
    assert "Compra" in Selectors.purchase_details_value("Compra")
    assert "Total" in Selectors.purchase_totals_value("Total")


def test_portal_month_catalog_edges():
    today = date(2026, 1, 15)
    assert parse_portal_month_year(None, today) is None
    assert parse_portal_month_year("LAST_7_DAYS", today) is PortalBetRelativePeriod.LAST_7_DAYS
    assert parse_portal_month_year("Janeiro/2026", today) == PortalYearMonth(2026, 1)
    assert PortalBetFilterBuilder.period_label(PortalYearMonth(2026, 1)) == "Janeiro/2026"
    months = current_and_previous_months(today, 2)
    assert months == (PortalYearMonth(2026, 1), PortalYearMonth(2025, 12))

    with pytest.raises(ValueError, match="mês deve estar"):
        parse_portal_month_year("2026-13", today)
    with pytest.raises(ValueError, match="Use YYYY-MM"):
        parse_portal_month_year("mês-inexistente/2026", today)
    with pytest.raises(ValueError, match="janela permitida"):
        parse_portal_month_year("2024-01", today)

    detail = invalid_month_year_detail("2024-01", today)
    assert detail.allowed_values == ["2026-01", "2025-12", "2025-11", "2025-10", "2025-09", "2025-08"]


def test_positive_int_rejects_invalid_values():
    for value in ("abc", "0"):
        with pytest.raises(ValueError):
            parse_positive_int(value)


def test_playwright_error_message_builder_all_branches():
    raw = "Locator.click: Timeout 5000ms exceeded. Call log: locator('button')"
    message = PlaywrightErrorMessageBuilder.build_error_message(Operation.PLACE_BET, raw)
    assert "Locator.click" in message
    assert "'button'" in message
    assert "Timeout 5000ms exceeded" in message
    assert PlaywrightErrorMessageBuilder.build_error_message(Operation.PLACE_BET, "sem locator") == "sem locator"
    assert PlaywrightErrorMessageBuilder._extract_event("erro") == "Não identificado"
    assert PlaywrightErrorMessageBuilder._extract_cause("erro") == "Não identificado"


def test_success_notification_builders_with_and_without_bets():
    bet = BetResult(numbers=["01", "02"], draw="100", status="Efetivada", amount=Decimal("5.00"))
    assert "01, 02" in NotificationMessageBuilder.build_success_email_message(purchase(bets=[bet]))
    assert "01, 02" in NotificationMessageBuilder.build_success_whatsapp_message(purchase(bets=[bet]))
    assert "Número da compra" in NotificationMessageBuilder.build_success_whatsapp_message(purchase())


def test_draw_result_message_keeps_unknown_lottery_modality():
    bet = PortalBetResult(
        purchase_datetime=datetime(2026, 8, 23, 12, 30),
        lottery_modality="Modalidade futura",
        selected_numbers=["01", "02"],
        draw_number="100",
        status="Premiada",
    )

    assert "Modalidade: Modalidade futura" in NotificationMessageBuilder.build_draw_results_whatsapp_message([bet])
    assert "Modalidade:</strong> Modalidade futura" in NotificationMessageBuilder.build_draw_results_email_message(
        [bet]
    )


def test_datetime_timezone_naive_and_aware_paths():
    naive = with_sao_paulo_timezone(datetime(2026, 8, 23, 12, 30))
    assert naive.utcoffset() is not None
    aware = with_sao_paulo_timezone(datetime(2026, 8, 23, 15, 30, tzinfo=UTC))
    assert aware.hour == 12
    assert aware.microsecond == 0


def test_settings_remaining_derived_paths(tmp_path):
    settings = Settings(
        BROWSER_PROFILE_DIR=tmp_path,
        ONLINE_LOTTERY_URL="https://example.test",
        ONLINE_LOTTERY_PATH="/#",
        PORTAL_BETS_PATH="/apostas",
        SELECTED_LOTTERY_MODALITY="quina",
        BET_PAGE_PATH="/{lottery_modality}",
        BET_PURCHASE_PATH="/compras/{purchase_number}",
    )
    assert settings.portal_bets_url == "https://example.test/#/apostas"
    assert settings.bet_page_path_with_modality == "/quina"
    assert settings.bet_purchase_path_without_purchase == "/compras/"


@pytest.mark.anyio
async def test_mongo_database_initializes_once_and_closes(monkeypatch):
    client = Mock()
    client.__getitem__ = Mock(return_value="database")
    client.close = AsyncMock()
    client_factory = Mock(return_value=client)
    initialize = AsyncMock()
    monkeypatch.setattr(connection_module, "AsyncMongoClient", client_factory)
    monkeypatch.setattr(connection_module, "init_beanie", initialize)
    database = MongoDatabase("mongodb://test", "loto")

    await database.ensure_initialized()
    await database.ensure_initialized()
    initialize.assert_awaited_once_with(database="database", document_models=[BetModel])
    await database.close()
    client.close.assert_awaited_once()
    await database.close()


def test_bet_model_conversion_and_validation(monkeypatch):
    assert BetModel.parse_decimal128(Decimal128("1.23")) == Decimal("1.23")
    assert BetModel.parse_decimal128("1.23") == "1.23"
    empty_amount = BetResult(numbers=["01"], draw="10", status="ok", amount=None)
    with pytest.raises(ValueError, match="obrigatório"):
        BetModel.from_result(lottery_modality=LotteryModality.MEGA_SENA, bet=empty_amount, purchase=purchase())

    monkeypatch.setattr(BetModel, "get_pymongo_collection", Mock(return_value=Mock()))
    bet = BetResult(numbers=["01"], draw="10", status="ok", amount=Decimal("1.239"))
    model = BetModel.from_result(lottery_modality=LotteryModality.MEGA_SENA, bet=bet, purchase=purchase(bets=[bet]))
    result = model.to_result()
    assert result.bet_amount == Decimal("1.24")
    assert result.lottery_modality is LotteryModality.MEGA_SENA
    assert result.bet_date.utcoffset() is not None


def test_repository_public_methods_delegate_to_sync_runner(monkeypatch):
    repository = BeanieBetRepository(Mock())
    runner = Mock(side_effect=[None, ["all"], "one"])
    monkeypatch.setattr(repository, "_run_sync", runner)
    repository.save(LotteryModality.MEGA_SENA, purchase())
    assert repository.find_all(BetSearchFilters()) == ["all"]
    assert repository.find_by_id("id") == "one"
    assert runner.call_count == 3


class FakeField:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return (self.name, "eq", other)

    def __ge__(self, other):
        return (self.name, "ge", other)

    def __le__(self, other):
        return (self.name, "le", other)


class FakeQuery:
    def __init__(self, models):
        self.models = models
        self.sort_value = None

    def sort(self, value):
        self.sort_value = value
        return self

    async def to_list(self):
        return self.models


@pytest.mark.anyio
async def test_repository_async_operations(monkeypatch):
    database = SimpleNamespace(ensure_initialized=AsyncMock(), close=AsyncMock())
    repository = BeanieBetRepository(database)
    converted = SimpleNamespace(to_result=Mock(return_value="converted"))
    query = FakeQuery([converted])
    fake_model = SimpleNamespace(
        lottery_modality=FakeField("lottery_modality"),
        draw_number=FakeField("draw_number"),
        bet_date=FakeField("bet_date"),
        bet_id=FakeField("bet_id"),
        from_result=Mock(return_value=converted),
        insert_many=AsyncMock(),
        find=Mock(return_value=query),
        find_one=AsyncMock(return_value=converted),
    )
    monkeypatch.setattr(repository_module, "BetModel", fake_model)

    await repository._save(LotteryModality.MEGA_SENA, purchase())
    fake_model.insert_many.assert_not_awaited()
    bet = BetResult(numbers=["01"], draw="10", status="ok", amount=Decimal("1"))
    await repository._save(LotteryModality.MEGA_SENA, purchase(bets=[bet]))
    fake_model.insert_many.assert_awaited_once_with([converted])

    filters = BetSearchFilters(
        lottery_modality=LotteryModality.MEGA_SENA,
        draw_number=10,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 31),
    )
    assert await repository._find_all(filters) == ["converted"]
    assert len(fake_model.find.call_args.args) == 4
    assert query.sort_value == "-bet_date"

    valid_id = "64ef8f7a6f9a8f0f8f0f8f0f"
    assert await repository._find_by_id(valid_id) == "converted"
    fake_model.find_one.return_value = None
    assert await repository._find_by_id(valid_id) is None
    with pytest.raises(ValueError, match="inválido"):
        await repository._find_by_id("invalid")


@pytest.mark.anyio
async def test_repository_run_with_close_closes_on_success_and_failure():
    database = SimpleNamespace(close=AsyncMock())
    repository = BeanieBetRepository(database)

    async def success():
        return "ok"

    assert await repository._run_with_close(success) == "ok"

    async def failure():
        raise ValueError("fail")

    with pytest.raises(ValueError, match="fail"):
        await repository._run_with_close(failure)
    assert database.close.await_count == 2


def test_repository_run_sync_both_runtime_error_paths(monkeypatch):
    repository = BeanieBetRepository(SimpleNamespace(close=AsyncMock()))

    async def action():
        return "fallback"

    monkeypatch.setattr(
        repository_module.anyio.from_thread, "run", Mock(side_effect=RuntimeError("AnyIO worker thread"))
    )
    assert repository._run_sync(action) == "fallback"

    monkeypatch.setattr(repository_module.anyio.from_thread, "run", Mock(side_effect=RuntimeError("different")))
    with pytest.raises(RuntimeError, match="different"):
        repository._run_sync(action)


class PortalBrowser:
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error

    def find_all(self, session, filters):
        if self.error:
            raise self.error
        return self.result


def test_list_portal_bets_use_case_success_and_errors():
    filters = PortalBetSearchFilters()
    session = AutomationSession()
    with pytest.raises(BrowserSessionClosedError):
        ListPortalBetsUseCase(session, PortalBrowser()).run(filters)

    session.mark_open()
    source = portal_bet()
    results = ListPortalBetsUseCase(session, PortalBrowser([source])).run(filters)
    assert results == [source]
    assert session.is_open

    with pytest.raises(ValueError):
        ListPortalBetsUseCase(session, PortalBrowser(error=ValueError("invalid"))).run(filters)
    assert session.is_open

    with pytest.raises(AutomationError):
        ListPortalBetsUseCase(
            session, PortalBrowser(error=AutomationError("automation", operation=Operation.LIST_PORTAL_BETS))
        ).run(filters)
    assert session.status.value == "Falhou"

    session.mark_open()
    with pytest.raises(AutomationError, match="unexpected"):
        ListPortalBetsUseCase(session, PortalBrowser(error=RuntimeError("unexpected"))).run(filters)


def test_notification_gateway_success_paths_and_fallback_mail_error(monkeypatch):
    whatsapp = SimpleNamespace(status=Mock(return_value="SESSAO_ABERTA"), send_message=Mock(return_value="enviado"))
    mail = SimpleNamespace(send=Mock())
    gateway = NotificationGateway(whatsapp, mail)
    session = AutomationSession()
    session.mark_open()
    session.whatsapp_enabled = True
    gateway.notify_success(session, purchase())
    assert whatsapp.send_message.called
    assert mail.send.called

    whatsapp.status.side_effect = RuntimeError("offline")
    gateway.notify_success(session, purchase())
    mail.send.side_effect = RuntimeError("mail offline")
    gateway.notify_success(session, purchase())

    mail.send.reset_mock(side_effect=True)
    error = AutomationError("failure", operation=Operation.PLACE_BET)
    mail.send.side_effect = RuntimeError("mail offline")
    assert gateway.notify_failure(False, error) is False


def test_routes_remaining_error_mappings(monkeypatch):
    automation_error = AutomationError("failure", operation=Operation.PLACE_BET)
    run_container = SimpleNamespace(run_bet_flow=SimpleNamespace(run=Mock(side_effect=automation_error)))
    with pytest.raises(ApiError):
        run_bet(BetRunRequest(selected_lottery_modality="MEGA_SENA"), run_container)

    check_container = SimpleNamespace(check_bet_draws=SimpleNamespace(run=Mock(side_effect=ValueError("invalid"))))
    request = CheckBetDrawsRequest(lottery_modality="MEGA_SENA", start_date="2026-08-01", end_date="2026-08-23")
    with pytest.raises(ApiError) as captured:
        check_bet_draws(request, check_container)
    assert captured.value.status_code == 400

    monkeypatch.setattr(BetRequestParser, "parse_portal_bet_filters", Mock(side_effect=ValueError("invalid")))
    with pytest.raises(ApiError) as captured:
        list_portal_bets(container=SimpleNamespace())
    assert captured.value.status_code == 400

    monkeypatch.setattr(BetRequestParser, "parse_portal_bet_filters", Mock(return_value=PortalBetSearchFilters()))
    container = SimpleNamespace(list_portal_bets=SimpleNamespace(run=Mock(side_effect=automation_error)))
    with pytest.raises(ApiError):
        list_portal_bets(container=container)

    monkeypatch.setattr(BetRequestParser, "parse_placed_bet_filters", Mock(side_effect=ValueError("invalid")))
    with pytest.raises(ApiError) as captured:
        list_placed_bets(container=SimpleNamespace())
    assert captured.value.status_code == 400
