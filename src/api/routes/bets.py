from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query

from api.dependencies import AppContainer, get_container
from api.mappers import ApiExceptionMapper, ApiResponseMapper
from api.parsers import BetRequestParser
from api.responses import error_response, success_response
from api.schemas import BetRunRequest, BetRunResponse, PlacedBetResponse, PortalBetResponse
from application import (
    ALL,
    PortalBetFiltersValidationError,
    current_and_previous_months,
)
from domain import (
    AutomationError,
    AutomationStatus,
    ErrorCode,
    LotteryModality,
    Operation,
    PortalBetRelativePeriod,
    PortalBetSortOrder,
    PortalBetStatus,
    PortalBetType,
    PortalDrawType,
)
from shared import sao_paulo_timezone

router = APIRouter(prefix="/api/v1", tags=["bets"])
placed_bets_router = APIRouter(prefix="/api/v1/history", tags=["placed-bets"])
CONTAINER_DEPENDENCY = Depends(get_container)
RUN_BET_REQUEST_BODY = Body(default=None)

BET_RUN_BAD_REQUEST_EXAMPLES = {
    ErrorCode.BAD_REQUEST.value: {
        "summary": ErrorCode.BAD_REQUEST.value,
        "value": {
            "error": {
                "timestamp": "2026-06-16T10:00:00-03:00",
                "status_code": 400,
                "code": ErrorCode.BAD_REQUEST.value,
                "message": "Parâmetros inválidos",
                "details": [
                    {
                        "field": "selected_lottery_modality",
                        "rejected_value": "abc",
                        "allowed_values": [*LotteryModality.__members__],
                        "message": "Valor inválido.",
                    }
                ],
            }
        },
    }
}

BETS_RUN_ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST, examples=BET_RUN_BAD_REQUEST_EXAMPLES),
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

BETS_RUN_RESPONSES = {
    200: success_response(
        "Fluxo de aposta executado com sucesso",
        {
            "session_id": "00000000-0000-0000-0000-000000000001",
            "status": f"{AutomationStatus.FINISHED.value}",
            "executed_operation": f"{Operation.COMPLETE_BET.value}",
            "message": "Aposta finalizada com sucesso.",
            "purchase_number": "123456",
        },
    ),
    **BETS_RUN_ERROR_RESPONSES,
}

BETS_ERROR_RESPONSES = {status_code: BETS_RUN_ERROR_RESPONSES[status_code] for status_code in (400, 409, 500, 503)}

PLACED_BET_DETAIL_ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST),
    404: error_response("Rota não encontrada", ErrorCode.ROUTE_NOT_FOUND),
    500: error_response("Erro interno", ErrorCode.INTERNAL_SERVER_ERROR),
}

PLACED_BETS_ERROR_RESPONSES = {
    status_code: PLACED_BET_DETAIL_ERROR_RESPONSES[status_code] for status_code in (400, 500)
}


@router.post(
    "/bets/run",
    response_model=BetRunResponse,
    responses=BETS_RUN_RESPONSES,
)
def run_bet(
    request: BetRunRequest | None = RUN_BET_REQUEST_BODY,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> BetRunResponse | None:
    try:
        selected_lottery_modality = BetRequestParser.parse_selected_lottery_modality(request)
        result = container.run_bet_flow.run(
            selected_lottery_modality=selected_lottery_modality,
        )
        return ApiResponseMapper.run_bet_response(result)
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get(
    "/bets",
    response_model=list[PortalBetResponse],
    responses=BETS_ERROR_RESPONSES,
)
def list_portal_bets(
    bet_type: str | None = Query(
        default=None,
        description=f"Tipo de aposta: {', '.join(bet_type.name for bet_type in PortalBetType)}.",
        examples=[PortalBetType.INDIVIDUAL.name],
    ),
    lottery_modality: str | None = Query(
        default=None,
        description=f"Modalidade: {ALL}, {', '.join(modality.name for modality in LotteryModality)}.",
        examples=[LotteryModality.MEGA_SENA.name],
    ),
    draw_type: str | None = Query(
        default=None,
        description=f"Tipo de concurso: {', '.join(draw_type.name for draw_type in PortalDrawType)}.",
        examples=[PortalDrawType.NORMAL.name],
    ),
    month_year: str | None = Query(
        default=None,
        description=(
            f"Período: {', '.join(period.name for period in PortalBetRelativePeriod)}, "
            f"{
                ', '.join(
                    month.canonical_value
                    for month in current_and_previous_months(datetime.now(sao_paulo_timezone()).date())
                )
            }."
        ),
        examples=[PortalBetRelativePeriod.LAST_7_DAYS.name],
    ),
    status: str | None = Query(
        default=None,
        description=f"Situação: {', '.join(status.name for status in PortalBetStatus)}.",
        examples=[PortalBetStatus.PAID.name],
    ),
    sort_by: str | None = Query(
        default=None,
        description=f"Ordenação: {', '.join(order.name for order in PortalBetSortOrder)}.",
        examples=[PortalBetSortOrder.DATE_DESC.name],
    ),
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> list[PortalBetResponse]:
    results = []
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
        ApiExceptionMapper.raise_invalid_parameters(exc)
    except ValueError as exc:
        ApiExceptionMapper.raise_bad_request(exc)
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)

    return ApiResponseMapper.portal_bets_response(results)


@placed_bets_router.get(
    "/bets",
    response_model=list[PlacedBetResponse],
    responses=PLACED_BETS_ERROR_RESPONSES,
)
def list_placed_bets(
    lottery_modality: str | None = Query(
        default=None,
        description=f"Modalidade: {ALL}, {', '.join(modality.name for modality in LotteryModality)}.",
        examples=[LotteryModality.MEGA_SENA.name],
    ),
    draw_number: str | None = Query(
        default=None,
        description="Número do sorteio.",
    ),
    start_date: str | None = Query(
        default=None,
        description="Data de início no formato AAAA-MM-DD.",
    ),
    end_date: str | None = Query(
        default=None,
        description="Data de término no formato AAAA-MM-DD.",
    ),
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> list[PlacedBetResponse]:
    results = []
    try:
        parsed_lottery_modality, parsed_draw_number, parsed_start_date, parsed_end_date = (
            BetRequestParser.parse_placed_bet_filters(
                lottery_modality=lottery_modality,
                draw_number=draw_number,
                start_date=start_date,
                end_date=end_date,
            )
        )
        results = container.list_placed_bets.run(
            lottery_modality=parsed_lottery_modality,
            draw_number=parsed_draw_number,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )
    except PortalBetFiltersValidationError as exc:
        ApiExceptionMapper.raise_invalid_parameters(exc)
    except ValueError as exc:
        ApiExceptionMapper.raise_bad_request(exc)

    return ApiResponseMapper.placed_bets_response(results)


@placed_bets_router.get(
    "/bets/{bet_id}",
    response_model=PlacedBetResponse,
    responses=PLACED_BET_DETAIL_ERROR_RESPONSES,
)
def get_placed_bet(
    bet_id: str,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> PlacedBetResponse | None:
    try:
        result = container.get_placed_bet.run(bet_id=bet_id)
        return ApiResponseMapper.placed_bet_response(result)
    except ValueError as exc:
        ApiExceptionMapper.raise_bad_request(exc)
