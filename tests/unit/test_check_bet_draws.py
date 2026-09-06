from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from api.parsers import BetRequestParser
from api.schemas import CheckBetDrawsRequest
from application import (
    BetSearchFilters,
    CheckBetDrawsCommand,
    CheckBetDrawsUseCase,
    PlacedBetResult,
    PortalBetFiltersValidationError,
    PortalBetResult,
    PortalBetSearchFilters,
    build_draw_results_email_message,
    build_draw_results_whatsapp_message,
)
from domain import (
    AutomationSession,
    AutomationStatus,
    ExternalServiceError,
    LotteryModality,
    NotificationChannel,
    Operation,
    PortalBetRelativePeriod,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
)


def placed_bet(
    *,
    modality: LotteryModality = LotteryModality.MEGA_SENA,
    numbers: list[str] | None = None,
    draw: str = "3037",
    status: str = "Efetivada",
) -> PlacedBetResult:
    return PlacedBetResult(
        bet_id="6a67e5db2e00e3a0eebf0e02",
        lottery_modality=modality,
        selected_numbers=numbers or ["02", "20", "28", "48", "57", "59"],
        draw_number=draw,
        status=status,
        bet_amount=Decimal("6.00"),
        purchase_number="561353958",
        bet_date=datetime(2026, 7, 27, 23, 14, 44),
    )


def portal_bet(
    *,
    modality: LotteryModality | str = "MEGA_SENA",
    numbers: list[str] | None = None,
    draw: str = "3037",
    status: str = "Concurso não apurado",
    hour: int = 23,
) -> PortalBetResult:
    return PortalBetResult(
        purchase_datetime=datetime(2026, 7, 27, hour, 14, 44, tzinfo=ZoneInfo("America/Sao_Paulo")),
        lottery_modality=modality,
        selected_numbers=numbers or ["02", "20", "28", "48", "57", "59"],
        draw_number=draw,
        status=status,
    )


class FakeListUseCase:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.calls: list[object] = []

    def run(self, filters):
        self.calls.append(filters)
        return self.results


class FakeNotifier:
    def __init__(
        self,
        channel: NotificationChannel = NotificationChannel.WHATSAPP,
        error: Exception | None = None,
    ) -> None:
        self.channel = channel
        self.error = error
        self.calls: list[tuple[AutomationSession, list[PortalBetResult]]] = []

    def notify_draw_results(self, session, bets):
        self.calls.append((session, bets))
        if self.error is not None:
            raise self.error
        return self.channel


def command() -> CheckBetDrawsCommand:
    return CheckBetDrawsCommand(BetSearchFilters(), PortalBetSearchFilters(has_explicit_filters=True))


def test_parse_check_bet_draws_returns_both_typed_filters() -> None:
    result = BetRequestParser.parse_check_bet_draws(
        CheckBetDrawsRequest(
            lottery_modality="MEGA_SENA",
            start_date="2026-07-01",
            end_date="2026-07-31",
            bet_type="INDIVIDUAL",
            draw_type="ALL",
            month_year="LAST_7_DAYS",
            status="PAID",
        ),
        today=date(2026, 7, 28),
    )

    assert result.history_filters == BetSearchFilters(
        lottery_modality=LotteryModality.MEGA_SENA,
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31, 23, 59, 59),
    )
    assert result.portal_filters == PortalBetSearchFilters(
        bet_type=PortalBetType.INDIVIDUAL,
        lottery_modality=LotteryModality.MEGA_SENA,
        draw_type=PortalDrawType.ALL,
        month_year=PortalBetRelativePeriod.LAST_7_DAYS,
        status=PortalBetStatus.PAID,
        sort_by=None,
        has_explicit_filters=True,
    )


def test_parse_check_bet_draws_maps_all_to_none_in_both_filters() -> None:
    result = BetRequestParser.parse_check_bet_draws(
        CheckBetDrawsRequest(lottery_modality="ALL", start_date="2026-07-01", end_date="2026-07-31"),
        today=date(2026, 7, 28),
    )

    assert result.history_filters.lottery_modality is None
    assert result.portal_filters.lottery_modality is None
    assert result.portal_filters.has_explicit_filters is True


@pytest.mark.parametrize(
    ("lottery_modality", "expected_history_modality"),
    [
        ("QUINA", LotteryModality.QUINA_ESPECIAL),
        ("LOTECA", LotteryModality.LOTECA_ESPECIAL),
        ("LOTOFACIL", LotteryModality.LOTOFACIL_ESPECIAL),
    ],
)
def test_parse_check_bet_draws_maps_special_draw_to_special_history_modality(
    lottery_modality: str,
    expected_history_modality: LotteryModality,
) -> None:
    result = BetRequestParser.parse_check_bet_draws(
        CheckBetDrawsRequest(
            lottery_modality=lottery_modality,
            start_date="2026-07-01",
            end_date="2026-07-31",
            draw_type="SPECIAL",
        ),
        today=date(2026, 7, 28),
    )

    assert result.history_filters.lottery_modality is expected_history_modality
    assert result.portal_filters.lottery_modality is LotteryModality[lottery_modality]
    assert result.portal_filters.draw_type is PortalDrawType.SPECIAL


def test_parse_check_bet_draws_keeps_valid_history_modality_when_special_variant_does_not_exist() -> None:
    result = BetRequestParser.parse_check_bet_draws(
        CheckBetDrawsRequest(
            lottery_modality="MEGA_SENA",
            start_date="2026-07-01",
            end_date="2026-07-31",
            draw_type="SPECIAL",
        ),
        today=date(2026, 7, 28),
    )

    assert result.history_filters.lottery_modality is LotteryModality.MEGA_SENA
    assert isinstance(result.history_filters.lottery_modality, LotteryModality)


@pytest.mark.parametrize("lottery_modality", ["QUINA_ESPECIAL", "LOTECA_ESPECIAL", "LOTOFACIL_ESPECIAL"])
def test_parse_check_bet_draws_rejects_special_lottery_modalities(lottery_modality: str) -> None:
    request = CheckBetDrawsRequest(
        lottery_modality=lottery_modality,
        start_date="2026-07-01",
        end_date="2026-07-31",
    )

    with pytest.raises(PortalBetFiltersValidationError) as captured:
        BetRequestParser.parse_check_bet_draws(request, today=date(2026, 7, 28))

    detail = captured.value.details[0]
    assert detail.field == "lottery_modality"
    assert detail.rejected_value == lottery_modality
    assert all(not value.endswith("_ESPECIAL") for value in detail.allowed_values or [])


def test_parse_check_bet_draws_accumulates_raw_validation_details_in_contract_order() -> None:
    request = CheckBetDrawsRequest(
        lottery_modality="invalid",
        start_date="2026-02-30",
        end_date="invalid",
        bet_type="invalid",
        draw_type="invalid",
        month_year="invalid",
        status="invalid",
    )

    with pytest.raises(PortalBetFiltersValidationError) as captured:
        BetRequestParser.parse_check_bet_draws(request, today=date(2026, 7, 28))

    details = captured.value.details
    assert [detail.field for detail in details] == [
        "lottery_modality",
        "start_date",
        "end_date",
        "bet_type",
        "draw_type",
        "month_year",
        "status",
    ]
    assert [detail.rejected_value for detail in details] == [
        "invalid",
        "2026-02-30",
        "invalid",
        "invalid",
        "invalid",
        "invalid",
        "invalid",
    ]


@pytest.mark.parametrize("payload_model", [None, CheckBetDrawsRequest(), CheckBetDrawsRequest(lottery_modality="   ")])
def test_parse_check_bet_draws_reports_all_required_fields(payload_model: CheckBetDrawsRequest | None) -> None:
    with pytest.raises(PortalBetFiltersValidationError) as captured:
        BetRequestParser.parse_check_bet_draws(payload_model, today=date(2026, 7, 28))

    assert [detail.field for detail in captured.value.details] == ["lottery_modality", "start_date", "end_date"]
    assert all(detail.message == "Campo obrigatório." for detail in captured.value.details)


def test_parse_check_bet_draws_rejects_reversed_date_range_before_optional_fields() -> None:
    request = CheckBetDrawsRequest(
        lottery_modality="MEGA_SENA",
        start_date="2026-07-31",
        end_date="2026-07-01",
        bet_type="invalid",
    )

    with pytest.raises(PortalBetFiltersValidationError) as captured:
        BetRequestParser.parse_check_bet_draws(request, today=date(2026, 7, 28))

    assert [detail.field for detail in captured.value.details] == ["start_date", "bet_type"]


def test_check_bet_draws_short_circuits_when_history_is_empty() -> None:
    session = AutomationSession()
    history = FakeListUseCase([])
    portal = FakeListUseCase([portal_bet()])
    notifier = FakeNotifier()

    result = CheckBetDrawsUseCase(session, history, portal, notifier).run(command())

    assert result.notification_channel is NotificationChannel.NONE
    assert result.notification_sent is False
    assert portal.calls == []
    assert notifier.calls == []
    assert session.status is AutomationStatus.CLOSED


def test_check_bet_draws_correlates_once_preserves_portal_order_and_notifies_once() -> None:
    session = AutomationSession()
    session.mark_open()
    first = portal_bet(hour=20)
    second = portal_bet(hour=19, numbers=["01", "02", "03", "04", "05", "06"], draw="3036")
    history = FakeListUseCase(
        [
            placed_bet(),
            placed_bet(),
            placed_bet(numbers=second.selected_numbers, draw=second.draw_number, status="Outro status"),
        ]
    )
    portal = FakeListUseCase([first, second])
    notifier = FakeNotifier(NotificationChannel.EMAIL)

    result = CheckBetDrawsUseCase(session, history, portal, notifier).run(command())

    assert result.matched_bets == 2
    assert result.notification_channel is NotificationChannel.EMAIL
    assert result.message.endswith("enviada por e-mail.")
    assert portal.calls == [command().portal_filters]
    assert notifier.calls[0][1] == [first, second]
    assert len(notifier.calls) == 1
    assert session.status is AutomationStatus.OPEN
    assert session.executed_operation is Operation.CHECK_BET_DRAWS


@pytest.mark.parametrize(
    "candidate",
    [
        portal_bet(modality="QUINA"),
        portal_bet(modality="Mega-Sena"),
        portal_bet(numbers=["20", "02", "28", "48", "57", "59"]),
        portal_bet(numbers=["02", "20", "28", "48", "57", "00"]),
        portal_bet(draw="03037"),
    ],
)
def test_correlation_rejects_any_different_key_component(candidate: PortalBetResult) -> None:
    assert CheckBetDrawsUseCase.correlate([placed_bet()], [candidate]) == []


def test_correlation_accepts_enum_modality_and_trims_without_losing_leading_zeroes() -> None:
    candidate = portal_bet(
        modality=LotteryModality.MEGA_SENA,
        numbers=[" 02", "20 ", "28", "48", "57", "59"],
        draw=" 3037 ",
    )

    assert CheckBetDrawsUseCase.correlate([placed_bet()], [candidate]) == [candidate]


def test_check_bet_draws_returns_no_match_without_notification() -> None:
    session = AutomationSession()
    session.mark_open()
    notifier = FakeNotifier()

    result = CheckBetDrawsUseCase(
        session,
        FakeListUseCase([placed_bet()]),
        FakeListUseCase([portal_bet(draw="9999")]),
        notifier,
    ).run(command())

    assert result.matched_bets == 0
    assert notifier.calls == []
    assert session.status is AutomationStatus.OPEN


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (ExternalServiceError("falha", operation=Operation.CHECK_BET_DRAWS), ExternalServiceError),
        (RuntimeError("falha"), ExternalServiceError),
    ],
)
def test_check_bet_draws_marks_session_failed_and_propagates_typed_error(error, expected_type) -> None:
    session = AutomationSession()
    session.mark_open()
    use_case = CheckBetDrawsUseCase(
        session,
        FakeListUseCase([placed_bet()]),
        FakeListUseCase([portal_bet()]),
        FakeNotifier(error=error),
    )

    with pytest.raises(expected_type):
        use_case.run(command())

    assert session.status is AutomationStatus.FAILED
    assert session.executed_operation is Operation.CHECK_BET_DRAWS


def test_check_bet_draws_rejects_none_channel_for_matches() -> None:
    session = AutomationSession()
    session.mark_open()
    use_case = CheckBetDrawsUseCase(
        session,
        FakeListUseCase([placed_bet()]),
        FakeListUseCase([portal_bet()]),
        FakeNotifier(NotificationChannel.NONE),
    )

    with pytest.raises(ExternalServiceError, match="Nenhum canal"):
        use_case.run(command())


def test_draw_result_messages_include_all_fields_convert_timezone_and_escape_html() -> None:
    bet = PortalBetResult(
        purchase_datetime=datetime(2026, 7, 28, 2, 14, 44, 999, tzinfo=ZoneInfo("UTC")),
        lottery_modality=LotteryModality.MEGA_SENA,
        selected_numbers=["02", "<20>"],
        draw_number="3037&",
        status="<Concurso não apurado>",
    )

    whatsapp = build_draw_results_whatsapp_message([bet, portal_bet()])
    email = build_draw_results_email_message([bet])

    assert "27/07/2026 23:14:44" in whatsapp
    assert "Modalidade: MEGA_SENA" in whatsapp
    assert "Números selecionados: 02, <20>" in whatsapp
    assert "Concurso: 3037&" in whatsapp
    assert "Situação: <Concurso não apurado>" in whatsapp
    assert "\n\n---\n\n" in whatsapp
    assert "&lt;20&gt;" in email
    assert "3037&amp;" in email
    assert "&lt;Concurso não apurado&gt;" in email
