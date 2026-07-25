from __future__ import annotations

import logging

from application.dto import PortalBetResult, PortalBetSearchFilters
from domain import AutomationError, AutomationSession
from domain.enums import PortalBetSortOrder, PortalYearMonth
from infrastructure.browser.playwright_common import PlaywrightBrowserBase
from infrastructure.selectors import PortalBetFilterBuilder, Selectors
from shared import parse_sao_paulo_datetime

logger = logging.getLogger(__name__)


class PortalBetsBrowserMixin(PlaywrightBrowserBase):
    def find_all(self, session: AutomationSession, filters: PortalBetSearchFilters) -> list[PortalBetResult]:
        return self._run_on_browser_thread(self._find_all_portal_bets, session, filters)

    def _find_all_portal_bets(
        self, session: AutomationSession, filters: PortalBetSearchFilters
    ) -> list[PortalBetResult]:
        page = self._require_page()
        self._goto(page, self._timeout_ms, self._settings.portal_bets_url)
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.portal_bets_path)
        page.locator(Selectors.PORTAL_BET_TYPE_FILTER).wait_for(state="visible", timeout=self._timeout_ms)

        labels = PortalBetFilterBuilder.labels(filters)
        should_apply = filters.has_filters or not self._filters_are_selected(page, labels)
        if should_apply:
            self._select_filters(page, labels, filters)

        if not self._click(page, self._short_timeout_ms, Selectors.PORTAL_APPLY_FILTER_BUTTON):
            raise AutomationError("Nao foi possivel aplicar os filtros de apostas no portal.")
        if not self._wait_for_portal_bets_table(page):
            return []

        return self._parse_portal_bet_rows_when_stable(page, filters)

    def _wait_for_portal_bets_table(self, page) -> bool:
        try:
            page.locator(Selectors.PORTAL_BETS_TABLE).wait_for(state="visible", timeout=self._timeout_ms)
            page.locator(Selectors.PORTAL_BETS_TABLE_ROWS).first.wait_for(
                state="visible",
                timeout=self._timeout_ms,
            )
            return True
        except Exception:
            logger.debug("Nenhuma linha da tabela de apostas ficou visivel dentro do tempo limite.")
            return False

    def _parse_portal_bet_rows_when_stable(
        self,
        page,
        filters: PortalBetSearchFilters | None = None,
    ) -> list[PortalBetResult]:
        elapsed_ms = 0
        last_error: Exception | None = None
        previous_signature: tuple[tuple[object, ...], ...] | None = None
        previous_results: list[PortalBetResult] | None = None
        while elapsed_ms <= self._timeout_ms:
            try:
                results = self._parse_portal_bet_rows(page)
                if self._results_match_filters(results, filters):
                    signature = self._results_signature(results)
                    if filters is None or signature == previous_signature:
                        return results
                    previous_signature = signature
                    previous_results = results
                last_error = AutomationError("Tabela de apostas ainda exibe resultados de outro filtro.")
            except Exception as exc:
                last_error = exc
            page.wait_for_timeout(250)
            elapsed_ms += 250

        if previous_results is not None:
            return previous_results
        if last_error is not None:
            if isinstance(last_error, AutomationError):
                raise last_error
            raise AutomationError("Tabela de apostas instavel durante a leitura dos resultados.") from last_error
        return []

    @staticmethod
    def _results_match_filters(
        results: list[PortalBetResult],
        filters: PortalBetSearchFilters | None,
    ) -> bool:
        if filters is None or not results:
            return True
        if isinstance(filters.month_year, PortalYearMonth) and not all(
            result.purchase_datetime.year == filters.month_year.year
            and result.purchase_datetime.month == filters.month_year.month
            for result in results
        ):
            return False
        if filters.sort_by is PortalBetSortOrder.DATE_ASC:
            return all(
                previous.purchase_datetime <= current.purchase_datetime
                for previous, current in zip(results, results[1:], strict=False)
            )
        if filters.sort_by is PortalBetSortOrder.DATE_DESC:
            return all(
                previous.purchase_datetime >= current.purchase_datetime
                for previous, current in zip(results, results[1:], strict=False)
            )
        return True

    @staticmethod
    def _results_signature(results: list[PortalBetResult]) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (
                result.purchase_datetime,
                result.lottery_modality,
                tuple(result.selected_numbers),
                result.draw_number,
                result.status,
            )
            for result in results
        )

    def _filters_are_selected(self, page, labels: dict[str, str]) -> bool:
        pairs = [
            (Selectors.PORTAL_BET_TYPE_FILTER, labels["bet_type"]),
            (Selectors.PORTAL_LOTTERY_MODALITY_FILTER, labels["lottery_modality"]),
            (Selectors.PORTAL_PERIOD_FILTER, labels["month_year"]),
            (Selectors.PORTAL_STATUS_FILTER, labels["status"]),
            (Selectors.PORTAL_SORT_FILTER, labels["sort_by"]),
        ]
        if page.locator(Selectors.PORTAL_DRAW_TYPE_FILTER).count() > 0:
            pairs.append((Selectors.PORTAL_DRAW_TYPE_FILTER, labels["draw_type"]))
        return all(self._selected_label(page, selector) == label for selector, label in pairs)

    @staticmethod
    def _selected_label(page, selector: str) -> str:
        select = page.locator(selector).first
        if select.count() > 0:
            selected_label = select.evaluate("element => element.selectedOptions[0]?.textContent?.trim() || ''")
            if selected_label:
                return selected_label
        selected = page.locator(f"{selector}/option[@selected]").first
        if selected.count() > 0:
            return selected.inner_text().strip()
        return ""

    def _select_filters(self, page, labels: dict[str, str], filters: PortalBetSearchFilters) -> None:
        self._select_option_when_available(page, Selectors.PORTAL_BET_TYPE_FILTER, labels["bet_type"])
        self._select_option_when_available(page, Selectors.PORTAL_LOTTERY_MODALITY_FILTER, labels["lottery_modality"])
        if filters.draw_type is not None:
            self._select_option_when_available(
                page,
                Selectors.PORTAL_DRAW_TYPE_FILTER,
                labels["draw_type"],
                "Parametro draw_type nao esta disponivel para a modalidade selecionada.",
            )
        elif page.locator(Selectors.PORTAL_DRAW_TYPE_FILTER).count() > 0:
            self._select_option_when_available(page, Selectors.PORTAL_DRAW_TYPE_FILTER, labels["draw_type"])
        try:
            self._select_option_when_available(page, Selectors.PORTAL_PERIOD_FILTER, labels["month_year"])
        except Exception as exc:
            raise ValueError("Parametro month_year nao esta disponivel no filtro atual do portal.") from exc
        self._select_option_when_available(page, Selectors.PORTAL_STATUS_FILTER, labels["status"])
        self._select_option_when_available(page, Selectors.PORTAL_SORT_FILTER, labels["sort_by"])

    def _select_option_when_available(
        self,
        page,
        selector: Selectors,
        label: str,
        error_message: str | None = None,
    ) -> None:
        elapsed_ms = 0
        last_error: Exception | None = None
        while elapsed_ms <= self._timeout_ms:
            try:
                element = page.locator(selector)
                element.wait_for(state="visible", timeout=self._short_timeout_ms)
                element.select_option(label=label)
                return
            except Exception as exc:
                last_error = exc
                page.wait_for_timeout(250)
                elapsed_ms += 250

        if error_message is not None:
            raise ValueError(error_message) from last_error
        raise AutomationError(f"Filtro do portal indisponivel para selecao: {selector}") from last_error

    @staticmethod
    def _parse_portal_bet_rows(page) -> list[PortalBetResult]:
        rows = page.locator(Selectors.PORTAL_BETS_TABLE_ROWS)
        results: list[PortalBetResult] = []
        for index in range(rows.count()):
            row = rows.nth(index)
            cells = row.locator(":scope > td")
            cell_count = cells.count()
            if cell_count == 1 and cells.first.get_attribute("colspan"):
                logger.debug("Linha auxiliar da tabela de apostas ignorada durante a leitura.")
                continue
            if cell_count < 6:
                raise AutomationError("Linha de aposta malformada na tabela do portal.")
            date_parts = [text.strip() for text in cells.nth(1).locator("h6").all_inner_texts() if text.strip()]
            if len(date_parts) < 2:
                raise AutomationError("Data e hora da compra nao foram encontradas na linha de aposta.")
            selected_numbers = [
                text.strip() for text in cells.nth(3).locator("span.margemVolante").all_inner_texts() if text.strip()
            ]
            lottery_modality = cells.nth(2).inner_text().strip()
            draw_number = cells.nth(4).inner_text().strip()
            status = " ".join(cells.nth(5).inner_text().split())
            if not lottery_modality or not selected_numbers or not draw_number or not status:
                raise AutomationError("Linha de aposta incompleta na tabela do portal.")
            results.append(
                PortalBetResult(
                    purchase_datetime=parse_sao_paulo_datetime(date_parts[0], date_parts[1]),
                    lottery_modality=lottery_modality,
                    selected_numbers=selected_numbers,
                    draw_number=draw_number,
                    status=status,
                )
            )
        return results
