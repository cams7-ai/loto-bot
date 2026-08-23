import re
from datetime import date, datetime, time

from api.mappers import ApiExceptionMapper
from api.schemas import BetRunRequest
from application import (
    INVALID_DATE_MESSAGE,
    INVALID_DRAW_NUMBER_MESSAGE,
    PortalBetFiltersValidationError,
    PortalBetSearchFilters,
    ValidationErrorDetail,
    invalid_catalog_detail,
    invalid_lottery_modality_detail,
    invalid_month_year_detail,
    parse_catalog_value,
    parse_portal_lottery_modality,
    parse_portal_month_year,
    parse_positive_int,
)
from domain import (
    LotteryModality,
    PortalBetSortOrder,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
)


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
        parsed_lottery_modality = cls._parse_placed_bet_filter(
            details,
            lottery_modality,
            lambda: parse_portal_lottery_modality(lottery_modality),
            lambda value: invalid_lottery_modality_detail("lottery_modality", value),
        )
        parsed_draw_number = cls._parse_placed_bet_filter(
            details,
            draw_number,
            lambda: parse_positive_int(draw_number),
            lambda value: ValidationErrorDetail(
                field="draw_number", rejected_value=value, message=INVALID_DRAW_NUMBER_MESSAGE
            ),
        )
        parsed_start_date = cls._parse_placed_bet_filter(
            details,
            start_date,
            lambda: cls._parse_history_date(start_date, end_of_day=False),
            lambda value: ValidationErrorDetail(field="start_date", rejected_value=value, message=INVALID_DATE_MESSAGE),
        )
        parsed_end_date = cls._parse_placed_bet_filter(
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

    @staticmethod
    def _parse_placed_bet_filter[T](
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

    @staticmethod
    def _parse_history_date(value: str | None, *, end_of_day: bool) -> datetime | None:
        if value is None:
            return None
        stripped = value.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped) is None:
            raise ValueError(INVALID_DATE_MESSAGE)
        parsed_date = datetime.strptime(stripped, "%Y-%m-%d").date()
        if end_of_day:
            return datetime.combine(parsed_date, time(23, 59, 59))
        return datetime.combine(parsed_date, time.min)

    @classmethod
    def parse_portal_bet_filters(
        cls,
        *,
        today: date,
        bet_type: str | None = None,
        lottery_modality: str | None = None,
        draw_type: str | None = None,
        month_year: str | None = None,
        status: str | None = None,
        sort_by: str | None = None,
    ) -> PortalBetSearchFilters:
        details: list[ValidationErrorDetail] = []

        parsed_bet_type = cls._parse_portal_bet_filter(
            details,
            lambda: parse_catalog_value("bet_type", bet_type, PortalBetType),
            lambda: invalid_catalog_detail("bet_type", bet_type or "", PortalBetType),  # noqa: F821
        )
        parsed_lottery_modality = cls._parse_portal_bet_filter(
            details,
            lambda: parse_portal_lottery_modality(lottery_modality),
            lambda: invalid_lottery_modality_detail("lottery_modality", lottery_modality or ""),
        )
        parsed_draw_type = cls._parse_portal_bet_filter(
            details,
            lambda: parse_catalog_value("draw_type", draw_type, PortalDrawType),
            lambda: invalid_catalog_detail("draw_type", draw_type or "", PortalDrawType),
        )
        parsed_month_year = cls._parse_portal_bet_filter(
            details,
            lambda: parse_portal_month_year(month_year, today),
            lambda: invalid_month_year_detail(month_year or "", today),
        )
        parsed_status = cls._parse_portal_bet_filter(
            details,
            lambda: parse_catalog_value("status", status, PortalBetStatus),
            lambda: invalid_catalog_detail("status", status or "", PortalBetStatus),
        )
        parsed_sort_by = cls._parse_portal_bet_filter(
            details,
            lambda: parse_catalog_value("sort_by", sort_by, PortalBetSortOrder),
            lambda: invalid_catalog_detail("sort_by", sort_by or "", PortalBetSortOrder),
        )

        if details:
            raise PortalBetFiltersValidationError(details)

        return PortalBetSearchFilters(
            bet_type=parsed_bet_type,
            lottery_modality=parsed_lottery_modality,
            draw_type=parsed_draw_type,
            month_year=parsed_month_year,
            status=parsed_status,
            sort_by=parsed_sort_by,
            has_explicit_filters=any(
                value is not None for value in (bet_type, lottery_modality, draw_type, month_year, status, sort_by)
            ),
        )

    @staticmethod
    def _parse_portal_bet_filter[T](
        details: list[ValidationErrorDetail],
        parser,
        detail_factory,
    ) -> T | None:
        try:
            return parser()
        except ValueError:
            details.append(detail_factory())
            return None
