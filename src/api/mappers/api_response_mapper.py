from __future__ import annotations

from api.mappers import ApiExceptionMapper
from api.schemas import (
    BetRunResponse,
    PlacedBetResponse,
    PortalBetResponse,
    SessionControlResponse,
    SessionStatusResponse,
)
from application import (
    AutomationRunResult,
    PlacedBetResult,
    PortalBetResult,
    SessionStatusResult,
)
from domain import LotteryModality


class ApiResponseMapper:
    @classmethod
    def session_control_response(cls, result: SessionStatusResult, message: str) -> SessionControlResponse:
        return SessionControlResponse(
            session_id=str(result.session_id),
            status=result.status.value,
            executed_operation=result.executed_operation.value,
            is_open=result.is_open,
            message=message,
        )

    @classmethod
    def session_status_response(cls, result: SessionStatusResult, message: str) -> SessionStatusResponse:
        return SessionStatusResponse(
            session_id=str(result.session_id),
            status=result.status.value,
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
            status=result.status.value,
            message=result.message,
            executed_operation=result.executed_operation.value,
            purchase_number=result.purchase_number,
        )

    @classmethod
    def portal_bets_response(cls, results: list[PortalBetResult]) -> list[PortalBetResponse]:
        return [
            PortalBetResponse(
                purchase_datetime=result.purchase_datetime,
                lottery_modality=result.lottery_modality.name
                if isinstance(result.lottery_modality, LotteryModality)
                else result.lottery_modality,
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
    def placed_bet_response(cls, result: PlacedBetResult | None) -> PlacedBetResponse:
        if result is None:
            ApiExceptionMapper.raise_internal_server_error(
                "Erro interno. Resultado da execução do fluxo de consulta de aposta não retornado."
            )

        return PlacedBetResponse(
            bet_id=result.bet_id,
            lottery_modality=result.lottery_modality.name,
            selected_numbers=result.selected_numbers,
            draw_number=result.draw_number,
            status=result.status,
            bet_amount=result.bet_amount,
            purchase_number=result.purchase_number,
            bet_date=result.bet_date,
        )
