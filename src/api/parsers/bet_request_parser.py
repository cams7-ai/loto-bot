import re
from datetime import datetime, time

from api.mappers import ApiExceptionMapper
from api.schemas import BetRunRequest
from application import (
    INVALID_DATE_MESSAGE,
    INVALID_DRAW_NUMBER_MESSAGE,
    PortalBetFiltersValidationError,
    ValidationErrorDetail,
    invalid_lottery_modality_detail,
    parse_portal_lottery_modality,
    parse_positive_int,
)
from domain import LotteryModality


class BetRequestParser:
    @classmethod
    def parse_selected_lottery_modality(cls, request: BetRunRequest | None) -> LotteryModality | None:
        if request is None or request.selected_lottery_modality is None:
            return None
        try:
            return parse_portal_lottery_modality(request.selected_lottery_modality, False)
        except ValueError:
            ApiExceptionMapper.raise_invalid_fields(
                [invalid_lottery_modality_detail("selected_lottery_modality", request.selected_lottery_modality)]
            )
            return None

    @classmethod
    def parse_placed_bet_filters(
        cls,
        *,
        lottery_modality: str | None,
        draw_number: str | None,
        start_date: str | None,
        end_date: str | None,
    ) -> tuple[LotteryModality | None, int | None, datetime | None, datetime | None]:
        details: list[ValidationErrorDetail] = []
        parsed_lottery_modality = cls._parse_filter(
            details,
            lottery_modality,
            lambda: parse_portal_lottery_modality(lottery_modality),
            lambda value: invalid_lottery_modality_detail("lottery_modality", value),
        )
        parsed_draw_number = cls._parse_filter(
            details,
            draw_number,
            lambda: parse_positive_int(draw_number),
            lambda value: ValidationErrorDetail(
                field="draw_number", rejected_value=value, message=INVALID_DRAW_NUMBER_MESSAGE
            ),
        )
        parsed_start_date = cls._parse_filter(
            details,
            start_date,
            lambda: cls._parse_history_date(start_date, end_of_day=False),
            lambda value: ValidationErrorDetail(field="start_date", rejected_value=value, message=INVALID_DATE_MESSAGE),
        )
        parsed_end_date = cls._parse_filter(
            details,
            end_date,
            lambda: cls._parse_history_date(end_date, end_of_day=True),
            lambda value: ValidationErrorDetail(field="end_date", rejected_value=value, message=INVALID_DATE_MESSAGE),
        )
        if (
            not details
            and parsed_start_date is not None
            and parsed_end_date is not None
            and parsed_start_date > parsed_end_date
        ):
            details.append(
                ValidationErrorDetail(
                    field="start_date",
                    rejected_value=start_date or "",
                    message="Valor inválido. A data inicial não pode ser maior que a data final.",
                )
            )
        if details:
            raise PortalBetFiltersValidationError(details)
        return parsed_lottery_modality, parsed_draw_number, parsed_start_date, parsed_end_date

    @classmethod
    def _parse_filter[T](
        cls,
        details: list[ValidationErrorDetail],
        raw_value: str | None,
        parser,
        detail_factory,
    ) -> T | None:
        if raw_value is None:
            return None
        try:
            return parser()
        except ValueError:
            details.append(detail_factory(raw_value))
            return None

    @classmethod
    def _parse_history_date(cls, value: str | None, *, end_of_day: bool) -> datetime | None:
        if value is None:
            return None
        stripped = value.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped) is None:
            raise ValueError(INVALID_DATE_MESSAGE)
        parsed_date = datetime.strptime(stripped, "%Y-%m-%d").date()
        if end_of_day:
            return datetime.combine(parsed_date, time(23, 59, 59))
        return datetime.combine(parsed_date, time.min)
