from __future__ import annotations

import logging

from application.dto import PortalBetResult, PortalBetSearchFilters
from domain import AutomationError, AutomationSession
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

        if self._click(page, self._short_timeout_ms, Selectors.PORTAL_APPLY_FILTER_BUTTON):
            try:
                page.locator(Selectors.PORTAL_BETS_TABLE).wait_for(state="visible", timeout=self._timeout_ms)
            except Exception:
                logger.debug("Falha ao aguardar a tabela de apostas do portal após aplicar filtros.")
                return []

        return self._parse_portal_bet_rows(page)

    def _filters_are_selected(self, page, labels: dict[str, str]) -> bool:
        pairs = (
            (Selectors.PORTAL_BET_TYPE_FILTER, labels["bet_type"]),
            (Selectors.PORTAL_LOTTERY_MODALITY_FILTER, labels["lottery_modality"]),
            (Selectors.PORTAL_PERIOD_FILTER, labels["month_year"]),
            (Selectors.PORTAL_STATUS_FILTER, labels["status"]),
            (Selectors.PORTAL_SORT_FILTER, labels["sort_by"]),
        )
        return all(self._selected_label(page, selector) == label for selector, label in pairs)

    @staticmethod
    def _selected_label(page, selector: str) -> str:
        selected = page.locator(f"{selector}/option[@selected]").first
        if selected.count() > 0:
            return selected.inner_text().strip()
        return ""

    def _select_filters(self, page, labels: dict[str, str], filters: PortalBetSearchFilters) -> None:
        page.locator(Selectors.PORTAL_BET_TYPE_FILTER).select_option(label=labels["bet_type"])
        page.locator(Selectors.PORTAL_LOTTERY_MODALITY_FILTER).select_option(label=labels["lottery_modality"])
        if filters.draw_type is not None:
            draw_type = page.locator(Selectors.PORTAL_DRAW_TYPE_FILTER)
            if draw_type.count() == 0:
                raise ValueError("Parâmetro draw_type não está disponível para a modalidade selecionada.")
            draw_type.select_option(label=labels["draw_type"])
        elif page.locator(Selectors.PORTAL_DRAW_TYPE_FILTER).count() > 0:
            page.locator(Selectors.PORTAL_DRAW_TYPE_FILTER).select_option(label=labels["draw_type"])
        period = page.locator(Selectors.PORTAL_PERIOD_FILTER)
        try:
            period.select_option(label=labels["month_year"])
        except Exception as exc:
            raise ValueError("Parâmetro month_year não está disponível no filtro atual do portal.") from exc
        page.locator(Selectors.PORTAL_STATUS_FILTER).select_option(label=labels["status"])
        page.locator(Selectors.PORTAL_SORT_FILTER).select_option(label=labels["sort_by"])

    @staticmethod
    def _parse_portal_bet_rows(page) -> list[PortalBetResult]:
        rows = page.locator(Selectors.PORTAL_BETS_TABLE_ROWS)
        results: list[PortalBetResult] = []
        for index in range(rows.count()):
            row = rows.nth(index)
            cells = row.locator(":scope > td")
            if cells.count() < 6:
                raise AutomationError("Linha de aposta malformada na tabela do portal.")
            date_parts = [text.strip() for text in cells.nth(1).locator("h6").all_inner_texts() if text.strip()]
            if len(date_parts) < 2:
                raise AutomationError("Data e hora da compra não foram encontradas na linha de aposta.")
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
