from __future__ import annotations

from application.dto import PortalBetResult, PortalBetSearchFilters
from application.ports import ClockPort, PortalBetQueryPort
from application.services.portal_bet_filter_catalog import (
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
        if not self._session.is_open:
            raise BrowserSessionClosedError(self._session.executed_operation)

        filters = PortalBetSearchFilters(
            bet_type=parse_catalog_value("bet_type", bet_type, PortalBetType),
            lottery_modality=parse_portal_lottery_modality(lottery_modality),
            draw_type=parse_catalog_value("draw_type", draw_type, PortalDrawType),
            month_year=parse_portal_month_year(month_year, self._clock.today()),
            status=parse_catalog_value("status", status, PortalBetStatus),
            sort_by=parse_catalog_value("sort_by", sort_by, PortalBetSortOrder),
            has_explicit_filters=any(
                value is not None for value in (bet_type, lottery_modality, draw_type, month_year, status, sort_by)
            ),
        )

        self._session.mark_running(Operation.LIST_PORTAL_BETS)
        try:
            results = self._portal_bets.find_all(self._session, filters)
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
