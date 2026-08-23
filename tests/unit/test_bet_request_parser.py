from datetime import datetime

import pytest

from api.exceptions import ApiError
from api.parsers import BetRequestParser
from api.schemas import BetRunRequest
from application import BetSearchFilters, PortalBetFiltersValidationError
from domain import LotteryModality


def test_parse_selected_lottery_modality_handles_missing_and_valid_values() -> None:
    assert BetRequestParser.parse_selected_lottery_modality(None) is None
    assert BetRequestParser.parse_selected_lottery_modality(BetRunRequest(selected_lottery_modality=None)) is None
    assert (
        BetRequestParser.parse_selected_lottery_modality(BetRunRequest(selected_lottery_modality="MEGA_SENA"))
        is LotteryModality.MEGA_SENA
    )


def test_parse_selected_lottery_modality_maps_invalid_value_to_api_error() -> None:
    with pytest.raises(ApiError) as exc_info:
        BetRequestParser.parse_selected_lottery_modality(BetRunRequest(selected_lottery_modality="invalid"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.details is not None
    assert exc_info.value.details[0]["field"] == "selected_lottery_modality"
    assert exc_info.value.details[0]["rejected_value"] == "invalid"


def test_parse_placed_bet_filters_returns_domain_values_and_date_boundaries() -> None:
    result = BetRequestParser.parse_placed_bet_filters(
        lottery_modality="MEGA_SENA",
        draw_number="1234",
        start_date="2026-07-01",
        end_date="2026-07-31",
    )

    assert result == BetSearchFilters(
        lottery_modality=LotteryModality.MEGA_SENA,
        draw_number=1234,
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31, 23, 59, 59),
    )


def test_parse_placed_bet_filters_aggregates_invalid_values() -> None:
    with pytest.raises(PortalBetFiltersValidationError) as exc_info:
        BetRequestParser.parse_placed_bet_filters(
            lottery_modality="invalid",
            draw_number="invalid",
            start_date="invalid",
            end_date="invalid",
        )

    assert [detail.field for detail in exc_info.value.details] == [
        "lottery_modality",
        "draw_number",
        "start_date",
        "end_date",
    ]


def test_parse_placed_bet_filters_rejects_reversed_date_range() -> None:
    with pytest.raises(PortalBetFiltersValidationError) as exc_info:
        BetRequestParser.parse_placed_bet_filters(
            lottery_modality=None,
            draw_number=None,
            start_date="2026-07-31",
            end_date="2026-07-01",
        )

    assert len(exc_info.value.details) == 1
    assert exc_info.value.details[0].field == "start_date"
    assert exc_info.value.details[0].rejected_value == "2026-07-31"
