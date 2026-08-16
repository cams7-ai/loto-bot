from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from api.mappers import ApiExceptionMapper
from api.schemas import BetRunResponse, PlacedBetResponse, PortalBetResponse, SessionControlResponse
from application import AutomationRunResult, PlacedBetResult, PortalBetResult, SessionStatusResult
from application.services.portal_bet_filter_catalog import normalize_public_value
from domain import LotteryModality
from shared.datetime_utils import with_sao_paulo_timezone


class ApiResponseMapper:
    @classmethod
    def session_response(cls, result: SessionStatusResult, message: str) -> SessionControlResponse:
        return SessionControlResponse(
            session_id=str(result.session_id),
            status=result.status,
            executed_operation=result.executed_operation.value,
            is_open=result.is_open,
            message=message,
        )

    @classmethod
    def run_bet_response(cls, result: AutomationRunResult | None) -> BetRunResponse | None:
        if result is None:
            ApiExceptionMapper.raise_internal_server_error(
                "Erro interno. Resultado da execução do fluxo de apostas não retornado."
            )

        return BetRunResponse(
            session_id=str(result.session_id),
            status=result.status,
            message=result.message,
            executed_operation=result.executed_operation.value,
            purchase_number=result.purchase_number,
        )

    @classmethod
    def portal_bets_response(cls, results: list[PortalBetResult]) -> list[PortalBetResponse]:
        return [
            PortalBetResponse(
                purchase_datetime=result.purchase_datetime,
                lottery_modality=cls._resolve_response_lottery_modality(result.lottery_modality),
                selected_numbers=result.selected_numbers,
                draw_number=result.draw_number,
                status=result.status,
            )
            for result in results
        ]

    @classmethod
    def placed_bets_response(cls, results: list[PlacedBetResult]) -> list[PlacedBetResponse]:
        return [cls.placed_bet_response(result) for result in results]

    @classmethod
    def placed_bet_response(cls, result) -> PlacedBetResponse:
        return PlacedBetResponse(
            bet_id=result.bet_id,
            lottery_modality=result.lottery_modality.name if result.lottery_modality else None,
            selected_numbers=result.selected_numbers,
            draw_number=result.draw_number,
            status=result.status,
            bet_amount=result.bet_amount.quantize(Decimal("0.01")),
            purchase_number=result.purchase_number,
            bet_date=cls._bet_date_with_timezone(result.bet_date),
        )

    @classmethod
    def _resolve_response_lottery_modality(cls, value: str | None) -> str | None:
        if value is None:
            return None

        stripped = value.strip()
        normalized_value = cls._normalize_lottery_modality_value(stripped)
        for modality in LotteryModality:
            if normalized_value in {
                cls._normalize_lottery_modality_value(modality.name),
                cls._normalize_lottery_modality_value(modality.value),
            }:
                return modality.name

        return stripped

    @classmethod
    def _normalize_lottery_modality_value(cls, value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", normalize_public_value(value))

    @classmethod
    def _bet_date_with_timezone(cls, bet_date: datetime) -> datetime:
        return with_sao_paulo_timezone(bet_date, remove_microseconds=True)
