from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query

from api.dependencies import AppContainer, get_container
from api.exceptions import ApiError
from api.mappers import ApiExceptionMapper
from api.responses import error_response
from api.schemas import BetRunRequest, BetRunResponse, PlacedBetResponse, PortalBetResponse
from application import PortalBetFiltersValidationError
from application.services.portal_bet_filter_catalog import current_and_previous_months
from domain import AutomationError, ErrorCode, LotteryModality
from domain.enums import (
    PortalBetRelativePeriod,
    PortalBetSortOrder,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
)
from shared import sao_paulo_timezone, with_sao_paulo_timezone

router = APIRouter(prefix="/api/v1", tags=["bets"])
placed_bets_router = APIRouter(prefix="/api/v1/history", tags=["placed-bets"])
CONTAINER_DEPENDENCY = Depends(get_container)
RUN_BET_REQUEST_BODY = Body(default=None)


ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST),
    403: error_response(
        "Confirmação de pagamento real desabilitada", ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE
    ),
    409: error_response(
        "Sessão fechada ou aposta indisponível no momento",
        ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE,
        ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE,
        ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE,
    ),
    429: error_response("Limite diário de compras atingido", ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE),
    500: error_response(
        "Erro interno ou de automação", ErrorCode.AUTOMATION_ERROR_CODE, ErrorCode.INTERNAL_SERVER_ERROR
    ),
    502: error_response(
        "Falha de comunicação ou redirecionamento no portal externo", ErrorCode.PAGE_REDIRECTION_ERROR_CODE
    ),
    503: error_response("Serviço externo indisponível", ErrorCode.EXTERNAL_SERVICE_ERROR_CODE),
}

PLACED_BETS_ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST),
    500: error_response("Erro interno", ErrorCode.INTERNAL_SERVER_ERROR),
}

PLACED_BET_DETAIL_ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST),
    404: error_response("Aposta não encontrada", ErrorCode.NOT_FOUND),
    500: error_response("Erro interno", ErrorCode.INTERNAL_SERVER_ERROR),
}


@router.post(
    "/bets/run",
    response_model=BetRunResponse,
    responses=ERROR_RESPONSES,
)
def run_bet(
    request: BetRunRequest | None = RUN_BET_REQUEST_BODY,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> BetRunResponse | None:
    try:
        result = container.run_bet_flow.run(
            selected_lottery_modality=request.selected_lottery_modality if request is not None else None
        )
        return BetRunResponse(
            session_id=str(result.session_id),
            status=result.status,
            message=result.message,
            executed_operation=result.executed_operation.value,
            purchase_number=result.purchase_number,
        )
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get(
    "/bets",
    response_model=list[PortalBetResponse],
    responses=ERROR_RESPONSES,
)
def list_portal_bets(
    bet_type: str | None = Query(
        default=None,
        description=f"Tipo de aposta: {', '.join(bet_type.value for bet_type in PortalBetType)}.",
        examples=[PortalBetType.INDIVIDUAL.value],
    ),
    lottery_modality: str | None = Query(
        default=None,
        description=f"Modalidade: all, {', '.join(modality.name for modality in LotteryModality)}.",
        examples=[LotteryModality.MEGA_SENA.name],
    ),
    draw_type: str | None = Query(
        default=None,
        description=f"Tipo de concurso: {', '.join(draw_type.value for draw_type in PortalDrawType)}.",
        examples=[PortalDrawType.NORMAL.value],
    ),
    month_year: str | None = Query(
        default=None,
        description=(
            f"Período: {', '.join(period.value for period in PortalBetRelativePeriod)}, "
            f"{
                ', '.join(
                    month.canonical_value
                    for month in current_and_previous_months(datetime.now(sao_paulo_timezone()).date())
                )
            }."
        ),
        examples=[PortalBetRelativePeriod.LAST_7_DAYS.value],
    ),
    status: str | None = Query(
        default=None,
        description=f"Situação: {', '.join(status.value for status in PortalBetStatus)}.",
        examples=[PortalBetStatus.PAID.value],
    ),
    sort_by: str | None = Query(
        default=None,
        description=f"Ordenação: {', '.join(order.value for order in PortalBetSortOrder)}.",
        examples=[PortalBetSortOrder.DATE_DESC.value],
    ),
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> list[PortalBetResponse]:
    try:
        results = container.list_portal_bets.run(
            bet_type=bet_type,
            lottery_modality=lottery_modality,
            draw_type=draw_type,
            month_year=month_year,
            status=status,
            sort_by=sort_by,
        )
    except PortalBetFiltersValidationError as exc:
        _raise_bad_request_messages(exc.messages)
    except ValueError as exc:
        _raise_bad_request(exc)
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)

    return [
        PortalBetResponse(
            purchase_datetime=with_sao_paulo_timezone(result.purchase_datetime, remove_microseconds=True),
            lottery_modality=result.lottery_modality,
            selected_numbers=result.selected_numbers,
            draw_number=result.draw_number,
            status=result.status,
        )
        for result in results
    ]


@placed_bets_router.get(
    "/bets",
    response_model=list[PlacedBetResponse],
    responses=PLACED_BETS_ERROR_RESPONSES,
)
def list_placed_bets(
    lottery_modality: str | None = None,
    draw_number: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> list[PlacedBetResponse]:
    try:
        results = container.list_placed_bets.run(
            lottery_modality=lottery_modality,
            draw_number=draw_number,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        _raise_bad_request(exc)

    return [_placed_bet_response(result) for result in results]


@placed_bets_router.get(
    "/bets/{bet_id}",
    response_model=PlacedBetResponse,
    responses=PLACED_BET_DETAIL_ERROR_RESPONSES,
)
def get_placed_bet(
    bet_id: str,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> PlacedBetResponse:
    try:
        result = container.get_placed_bet.run(bet_id=bet_id)
    except ValueError as exc:
        _raise_bad_request(exc)

    if result is None:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="Aposta não encontrada.",
        )

    return _placed_bet_response(result)


def _placed_bet_response(result) -> PlacedBetResponse:
    return PlacedBetResponse(
        bet_id=result.bet_id,
        lottery_modality=result.lottery_modality.value,
        selected_numbers=result.selected_numbers,
        draw_number=result.draw_number,
        status=result.status,
        bet_amount=result.bet_amount.quantize(Decimal("0.01")),
        purchase_number=result.purchase_number,
        bet_date=_bet_date_with_timezone(result.bet_date),
    )


def _bet_date_with_timezone(bet_date: datetime) -> datetime:
    return with_sao_paulo_timezone(bet_date, remove_microseconds=True)


def _raise_bad_request(exc: ValueError) -> None:
    raise ApiError(
        status_code=400,
        code=ErrorCode.BAD_REQUEST,
        message=str(exc),
    ) from exc


def _raise_bad_request_messages(messages: list[str]) -> None:
    raise ApiError(
        status_code=400,
        code=ErrorCode.BAD_REQUEST,
        messages=messages,
    )
