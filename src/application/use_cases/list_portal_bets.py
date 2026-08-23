from application.dto import PortalBetResult, PortalBetSearchFilters
from application.ports import BrowserAutomationPort
from domain import (
    AutomationError,
    AutomationSession,
    BrowserSessionClosedError,
    Operation,
)


class ListPortalBetsUseCase:
    def __init__(self, session: AutomationSession, browser: BrowserAutomationPort) -> None:
        self._session = session
        self._browser = browser

    def run(
        self,
        filters: PortalBetSearchFilters,
    ) -> list[PortalBetResult]:

        if not self._session.is_open:
            raise BrowserSessionClosedError(self._session.executed_operation)

        self._session.mark_running(Operation.LIST_PORTAL_BETS)
        try:
            results = [
                PortalBetResult(
                    purchase_datetime=result.purchase_datetime,
                    lottery_modality=result.lottery_modality,
                    selected_numbers=result.selected_numbers,
                    draw_number=result.draw_number,
                    status=result.status,
                )
                for result in self._browser.find_all(self._session, filters)
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
