from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query

from api.dependencies import AppContainer, get_container
from api.mappers import ApiExceptionMapper, ApiResponseMapper
from api.parsers import BetRequestParser
from api.responses import error_response, success_response
from api.schemas import (
    BetRunRequest,
    BetRunResponse,
    CheckBetDrawsRequest,
    CheckBetDrawsResponse,
    PlacedBetResponse,
    PortalBetResponse,
)
from application import (
    ALL,
    PORTAL_LOTTERY_MODALITY_ALLOWED_VALUES,
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
from shared import SaoPauloClock, sao_paulo_timezone

router = APIRouter(prefix="/api/v1", tags=["bets"])
placed_bets_router = APIRouter(prefix="/api/v1/history", tags=["placed-bets"])
CONTAINER_DEPENDENCY = Depends(get_container)
RUN_BET_REQUEST_BODY = Body(default=None)
CHECK_BET_DRAWS_REQUEST_BODY = Body(default=None)

BET_RUN_BAD_REQUEST_EXAMPLE = {
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
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST, examples=BET_RUN_BAD_REQUEST_EXAMPLE),
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

PORTAL_BETS_BAD_REQUEST_EXAMPLE = {
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
                        "field": "lottery_modality",
                        "rejected_value": "abc",
                        "allowed_values": PORTAL_LOTTERY_MODALITY_ALLOWED_VALUES[1:],
                        "message": "Valor inválido.",
                    }
                ],
            }
        },
    }
}

BETS_ERROR_RESPONSES = {
    400: error_response(
        "Requisição inválida",
        ErrorCode.BAD_REQUEST,
        examples=PORTAL_BETS_BAD_REQUEST_EXAMPLE,
    ),
    **{status_code: BETS_RUN_ERROR_RESPONSES[status_code] for status_code in (409, 500, 503)},
}

BETS_RESPONSES = {
    200: success_response(
        "Lista de apostas obtida com sucesso",
        [
            {
                "purchase_datetime": "2026-07-19T12:33:09-03:00",
                "lottery_modality": LotteryModality.MEGA_SENA.name,
                "selected_numbers": ["09", "18", "33", "40", "47", "53"],
                "draw_number": "3034",
                "status": "Aposta não premiada",
            }
        ],
    ),
    **BETS_ERROR_RESPONSES,
}

CHECK_BET_DRAWS_BAD_REQUEST_EXAMPLE = {
    ErrorCode.BAD_REQUEST.value: {
        "summary": ErrorCode.BAD_REQUEST.value,
        "value": {
            "error": {
                "timestamp": "2026-07-28T22:00:00-03:00",
                "status_code": 400,
                "code": ErrorCode.BAD_REQUEST.value,
                "message": "Campos inválidos",
                "details": [
                    {
                        "field": "lottery_modality",
                        "rejected_value": "abc",
                        "allowed_values": PORTAL_LOTTERY_MODALITY_ALLOWED_VALUES,
                        "message": "Valor inválido.",
                    }
                ],
            }
        },
    }
}

CHECK_BET_DRAWS_RESPONSES = {
    200: success_response(
        "Conferência de apostas concluída",
        examples={
            "WHATSAPP": {
                "summary": "Notificação enviada pelo WhatsApp",
                "value": {
                    "matched_bets": 1,
                    "notification_sent": True,
                    "notification_channel": "WHATSAPP",
                    "message": "Conferência concluída e notificação enviada pelo WhatsApp.",
                },
            },
            "EMAIL": {
                "summary": "Notificação enviada por e-mail",
                "value": {
                    "matched_bets": 1,
                    "notification_sent": True,
                    "notification_channel": "EMAIL",
                    "message": "Conferência concluída e notificação enviada por e-mail.",
                },
            },
            "NONE": {
                "summary": "Nenhuma correspondência encontrada",
                "value": {
                    "matched_bets": 0,
                    "notification_sent": False,
                    "notification_channel": "NONE",
                    "message": "Conferência concluída. Nenhuma aposta correspondente foi encontrada.",
                },
            },
        },
    ),
    400: error_response(
        "Campos inválidos",
        ErrorCode.BAD_REQUEST,
        examples=CHECK_BET_DRAWS_BAD_REQUEST_EXAMPLE,
    ),
    409: BETS_RUN_ERROR_RESPONSES[409],
    500: BETS_RUN_ERROR_RESPONSES[500],
    502: BETS_RUN_ERROR_RESPONSES[502],
    503: BETS_RUN_ERROR_RESPONSES[503],
}

PLACED_BET_RESPONSE_EXAMPLE = {
    "bet_id": "64ef8f7a6f9a8f0f8f0f8f0f",
    "lottery_modality": LotteryModality.MEGA_SENA.name,
    "selected_numbers": ["01", "02", "03", "04", "05", "06"],
    "draw_number": "1234",
    "status": "Efetivada",
    "bet_amount": "123.45",
    "purchase_number": "123456",
    "bet_date": "2026-07-12T18:08:14-03:00",
}

PLACED_BET_DETAIL_BAD_REQUEST_EXAMPLE = {
    ErrorCode.BAD_REQUEST.value: {
        "summary": ErrorCode.BAD_REQUEST.value,
        "value": {
            "error": {
                "status_code": 400,
                "code": ErrorCode.BAD_REQUEST.value,
                "message": "Identificador da aposta inválido.",
            }
        },
    }
}

PLACED_BET_DETAIL_INTERNAL_ERROR_EXAMPLE = {
    ErrorCode.INTERNAL_SERVER_ERROR.value: {
        "summary": ErrorCode.INTERNAL_SERVER_ERROR.value,
        "value": {
            "error": {
                "status_code": 500,
                "code": ErrorCode.INTERNAL_SERVER_ERROR.value,
                "message": "Erro interno. Resultado da execução do fluxo de consulta de aposta não retornado.",
            }
        },
    }
}

PLACED_BET_DETAIL_ERROR_RESPONSES = {
    400: error_response(
        "Requisição inválida",
        ErrorCode.BAD_REQUEST,
        examples=PLACED_BET_DETAIL_BAD_REQUEST_EXAMPLE,
    ),
    500: error_response(
        "Erro interno",
        ErrorCode.INTERNAL_SERVER_ERROR,
        examples=PLACED_BET_DETAIL_INTERNAL_ERROR_EXAMPLE,
    ),
}

PLACED_BET_DETAIL_RESPONSES = {
    200: success_response(
        "Detalhes da aposta obtidos com sucesso",
        PLACED_BET_RESPONSE_EXAMPLE,
    ),
    **PLACED_BET_DETAIL_ERROR_RESPONSES,
}

PLACED_BETS_ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST),
    500: error_response("Erro interno", ErrorCode.INTERNAL_SERVER_ERROR),
}

PLACED_BETS_RESPONSES = {
    200: success_response("Lista de apostas obtida com sucesso", [PLACED_BET_RESPONSE_EXAMPLE]),
    **PLACED_BETS_ERROR_RESPONSES,
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
        result = container.run_bet_flow.run(selected_lottery_modality)
        return ApiResponseMapper.run_bet_response(result)
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.post(
    "/bets/check_draws",
    response_model=CheckBetDrawsResponse,
    responses=CHECK_BET_DRAWS_RESPONSES,
)
def check_bet_draws(
    request: CheckBetDrawsRequest | None = CHECK_BET_DRAWS_REQUEST_BODY,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> CheckBetDrawsResponse | None:
    try:
        command = BetRequestParser.parse_check_bet_draws(request, today=SaoPauloClock.today())
        result = container.check_bet_draws.run(command)
        return ApiResponseMapper.check_bet_draws_response(result)
    except PortalBetFiltersValidationError as exc:
        ApiExceptionMapper.raise_invalid_fields(exc.details, exc)
    except ValueError as exc:
        ApiExceptionMapper.raise_bad_request(exc)
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get(
    "/bets",
    response_model=list[PortalBetResponse],
    responses=BETS_RESPONSES,
)
def list_portal_bets(
    bet_type: str | None = Query(
        default=None,
        description=f"Tipo de aposta: {', '.join(bet_type.name for bet_type in PortalBetType)}.",
        examples=[PortalBetType.INDIVIDUAL.name],
    ),
    lottery_modality: str | None = Query(
        default=None,
        description=f"Modalidade: {', '.join(PORTAL_LOTTERY_MODALITY_ALLOWED_VALUES)}.",
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
        filters = BetRequestParser.parse_portal_bet_filters(
            bet_type=bet_type,
            lottery_modality=lottery_modality,
            draw_type=draw_type,
            month_year=month_year,
            status=status,
            sort_by=sort_by,
            today=SaoPauloClock.today(),
        )
        results = container.list_portal_bets.run(filters)
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
    responses=PLACED_BETS_RESPONSES,
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
        filters = BetRequestParser.parse_placed_bet_filters(
            lottery_modality=lottery_modality,
            draw_number=draw_number,
            start_date=start_date,
            end_date=end_date,
        )

        results = container.list_placed_bets.run(filters)
    except PortalBetFiltersValidationError as exc:
        ApiExceptionMapper.raise_invalid_parameters(exc)
    except ValueError as exc:
        ApiExceptionMapper.raise_bad_request(exc)

    return ApiResponseMapper.placed_bets_response(results)


@placed_bets_router.get(
    "/bets/{bet_id}",
    response_model=PlacedBetResponse,
    responses=PLACED_BET_DETAIL_RESPONSES,
)
def get_placed_bet(
    bet_id: str,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> PlacedBetResponse | None:
    try:
        result = container.get_placed_bet.run(bet_id)
        return ApiResponseMapper.placed_bet_response(result)
    except ValueError as exc:
        ApiExceptionMapper.raise_bad_request(exc)
