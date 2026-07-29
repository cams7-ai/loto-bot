from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from application.dto import PortalBetResult, PortalBetSearchFilters
from application.exceptions import PortalBetFiltersValidationError, ValidationErrorDetail
from application.ports import ClockPort, PortalBetQueryPort
from application.services.portal_bet_filter_catalog import (
    invalid_catalog_detail,
    invalid_lottery_modality_detail,
    invalid_month_year_detail,
    parse_catalog_value,
    parse_portal_lottery_modality,
    parse_portal_month_year,
)
from domain import AutomationError, AutomationSession, BrowserSessionClosedError, Operation
from domain.enums import (
    PortalBetSortOrder,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
)
from shared import sao_paulo_timezone


class ListPortalBetsUseCase:
    def __init__(self, session: AutomationSession, portal_bets: PortalBetQueryPort, clock: ClockPort) -> None:
        self._session = session
        self._portal_bets = portal_bets
        self._clock = clock

    def run(
        self,
        bet_type: str | None = None,
        lottery_modality: str | None = None,
        draw_type: str | None = None,
        month_year: str | None = None,
        status: str | None = None,
        sort_by: str | None = None,
    ) -> list[PortalBetResult]:
        validation_details: list[ValidationErrorDetail] = []
        parsed_bet_type = _parse_filter(
            validation_details,
            lambda: parse_catalog_value("bet_type", bet_type, PortalBetType),
            lambda: invalid_catalog_detail("bet_type", bet_type or "", PortalBetType),
        )
        parsed_lottery_modality = _parse_filter(
            validation_details,
            lambda: parse_portal_lottery_modality(lottery_modality),
            lambda: invalid_lottery_modality_detail("lottery_modality", lottery_modality or ""),
        )
        parsed_draw_type = _parse_filter(
            validation_details,
            lambda: parse_catalog_value("draw_type", draw_type, PortalDrawType),
            lambda: invalid_catalog_detail("draw_type", draw_type or "", PortalDrawType),
        )
        parsed_month_year = _parse_filter(
            validation_details,
            lambda: parse_portal_month_year(month_year, self._clock.today()),
            lambda: invalid_month_year_detail(month_year or "", self._clock.today()),
        )
        parsed_status = _parse_filter(
            validation_details,
            lambda: parse_catalog_value("status", status, PortalBetStatus),
            lambda: invalid_catalog_detail("status", status or "", PortalBetStatus),
        )
        parsed_sort_by = _parse_filter(
            validation_details,
            lambda: parse_catalog_value("sort_by", sort_by, PortalBetSortOrder),
            lambda: invalid_catalog_detail("sort_by", sort_by or "", PortalBetSortOrder),
        )
        if validation_details:
            raise PortalBetFiltersValidationError(validation_details)

        if not self._session.is_open:
            raise BrowserSessionClosedError(self._session.executed_operation)

        filters = PortalBetSearchFilters(
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

        self._session.mark_running(Operation.LIST_PORTAL_BETS)
        try:
            results = [
                PortalBetResult(
                    purchase_datetime=_portal_purchase_datetime_with_timezone(result.purchase_datetime),
                    lottery_modality=result.lottery_modality,
                    selected_numbers=result.selected_numbers,
                    draw_number=result.draw_number,
                    status=result.status,
                )
                for result in self._portal_bets.find_all(self._session, filters)
            ]
        except ValueError:
            self._session.mark_ready()
            raise
        except AutomationError:
            self._session.mark_failed(Operation.LIST_PORTAL_BETS)
            raise
        except Exception as exc:
            self._session.mark_failed(Operation.LIST_PORTAL_BETS)
            raise AutomationError(str(exc), operation=Operation.LIST_PORTAL_BETS) from exc
        self._session.mark_ready()
        return results


def _parse_filter[T](
    details: list[ValidationErrorDetail],
    parser: Callable[[], T],
    detail_factory: Callable[[], ValidationErrorDetail],
) -> T | None:
    try:
        return parser()
    except ValueError:
        details.append(detail_factory())
        return None


def _portal_purchase_datetime_with_timezone(purchase_datetime: datetime | None) -> datetime | None:
    if purchase_datetime is None or purchase_datetime.tzinfo is None:
        return None
    return purchase_datetime.astimezone(UTC).replace(tzinfo=sao_paulo_timezone(), microsecond=0)
