import re
from datetime import date, datetime, time

from api.mappers import ApiExceptionMapper
from api.schemas import BetRunRequest, CheckBetDrawsRequest
from application import (
    INVALID_DATE_MESSAGE,
    INVALID_DRAW_NUMBER_MESSAGE,
    BetSearchFilters,
    CheckBetDrawsCommand,
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
    REQUIRED_FIELD_MESSAGE = "Campo obrigatório."

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

    @classmethod
    def parse_placed_bet_filters(
        cls,
        *,
        lottery_modality: str | None,
        draw_number: str | None,
        start_date: str | None,
        end_date: str | None,
    ) -> BetSearchFilters:
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

        return BetSearchFilters(
            lottery_modality=parsed_lottery_modality,
            draw_number=parsed_draw_number,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )

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
            lambda: invalid_catalog_detail("bet_type", bet_type or "", PortalBetType),
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

    @classmethod
    def parse_check_bet_draws(
        cls,
        request: CheckBetDrawsRequest | None,
        *,
        today: date,
    ) -> CheckBetDrawsCommand:
        values = request.model_dump() if request is not None else {}
        details: list[ValidationErrorDetail] = []

        raw_lottery_modality = values.get("lottery_modality")
        lottery_modality = cls._parse_required_text(
            details,
            "lottery_modality",
            raw_lottery_modality,
            lambda value: parse_portal_lottery_modality(value),
            lambda value: invalid_lottery_modality_detail("lottery_modality", value),
        )
        raw_start_date = values.get("start_date")
        start_date = cls._parse_required_text(
            details,
            "start_date",
            raw_start_date,
            lambda value: cls._parse_history_date(value, end_of_day=False),
            lambda value: ValidationErrorDetail("start_date", value, INVALID_DATE_MESSAGE),
        )
        raw_end_date = values.get("end_date")
        end_date = cls._parse_required_text(
            details,
            "end_date",
            raw_end_date,
            lambda value: cls._parse_history_date(value, end_of_day=True),
            lambda value: ValidationErrorDetail("end_date", value, INVALID_DATE_MESSAGE),
        )
        if start_date is not None and end_date is not None and start_date > end_date:
            details.append(
                ValidationErrorDetail(
                    field="start_date",
                    rejected_value=raw_start_date,
                    message="Valor inválido. A data inicial não pode ser maior que a data final.",
                )
            )

        bet_type = cls._parse_optional_text(
            details,
            "bet_type",
            values.get("bet_type"),
            lambda value: parse_catalog_value("bet_type", value, PortalBetType),
            lambda value: invalid_catalog_detail("bet_type", value, PortalBetType),
        )
        draw_type = cls._parse_optional_text(
            details,
            "draw_type",
            values.get("draw_type"),
            lambda value: parse_catalog_value("draw_type", value, PortalDrawType),
            lambda value: invalid_catalog_detail("draw_type", value, PortalDrawType),
        )
        raw_month_year = values.get("month_year")
        month_year = cls._parse_optional_text(
            details,
            "month_year",
            raw_month_year,
            lambda value: parse_portal_month_year(value, today),
            lambda value: invalid_month_year_detail(value, today),
        )
        status = cls._parse_optional_text(
            details,
            "status",
            values.get("status"),
            lambda value: parse_catalog_value("status", value, PortalBetStatus),
            lambda value: invalid_catalog_detail("status", value, PortalBetStatus),
        )

        if details:
            raise PortalBetFiltersValidationError(details)

        return CheckBetDrawsCommand(
            history_filters=BetSearchFilters(
                lottery_modality=lottery_modality,
                draw_number=None,
                start_date=start_date,
                end_date=end_date,
            ),
            portal_filters=PortalBetSearchFilters(
                bet_type=bet_type,
                lottery_modality=lottery_modality,
                draw_type=draw_type,
                month_year=month_year,
                status=status,
                sort_by=None,
                has_explicit_filters=True,
            ),
        )

    @classmethod
    def _parse_required_text[T](
        cls,
        details: list[ValidationErrorDetail],
        field: str,
        raw_value: object | None,
        parser,
        detail_factory,
    ) -> T | None:
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            details.append(ValidationErrorDetail(field, raw_value, cls.REQUIRED_FIELD_MESSAGE))
            return None
        return cls._parse_text(details, raw_value, parser, detail_factory)

    @classmethod
    def _parse_optional_text[T](
        cls,
        details: list[ValidationErrorDetail],
        field: str,
        raw_value: object | None,
        parser,
        detail_factory,
    ) -> T | None:
        if raw_value is None:
            return None
        return cls._parse_text(details, raw_value, parser, detail_factory, field)

    @staticmethod
    def _parse_text[T](
        details: list[ValidationErrorDetail],
        raw_value: object,
        parser,
        detail_factory,
        field: str | None = None,
    ) -> T | None:
        if not isinstance(raw_value, str):
            if field == "month_year":
                template = detail_factory("")
                details.append(ValidationErrorDetail(field, raw_value, template.message, template.allowed_values))
            else:
                details.append(detail_factory(raw_value))
            return None
        try:
            return parser(raw_value)
        except ValueError:
            details.append(detail_factory(raw_value))
            return None

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
