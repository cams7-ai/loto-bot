from __future__ import annotations

import re
from datetime import datetime, time
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query

from api.dependencies import AppContainer, get_container
from api.exceptions import ApiError
from api.mappers import ApiExceptionMapper
from api.responses import error_response
from api.schemas import BetRunRequest, BetRunResponse, PlacedBetResponse, PortalBetResponse
from application import PortalBetFiltersValidationError, ValidationErrorDetail
from application.services.portal_bet_filter_catalog import (
    ALL,
    INVALID_DATE_MESSAGE,
    INVALID_DRAW_NUMBER_MESSAGE,
    current_and_previous_months,
    invalid_lottery_modality_detail,
    normalize_public_value,
    parse_portal_lottery_modality,
    parse_positive_int,
)
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
                        "allowed_values": [
                            LotteryModality.MEGA_SENA.name,
                            LotteryModality.QUINA.name,
                            LotteryModality.QUINA_ESPECIAL.name,
                            LotteryModality.LOTECA.name,
                            LotteryModality.LOTECA_ESPECIAL.name,
                            LotteryModality.LOTOFACIL.name,
                            LotteryModality.LOTOFACIL_ESPECIAL.name,
                            LotteryModality.MAIS_MILIONARIA.name,
                            LotteryModality.LOTOMANIA.name,
                            LotteryModality.TIMEMANIA.name,
                            LotteryModality.DUPLA_SENA.name,
                            LotteryModality.DIA_DE_SORTE.name,
                            LotteryModality.SUPER_SETE.name,
                        ],
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

BETS_ERROR_RESPONSES = {status_code: BETS_RUN_ERROR_RESPONSES[status_code] for status_code in (400, 409, 500, 503)}

PLACED_BET_DETAIL_ERROR_RESPONSES = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST),
    404: error_response("Aposta não encontrada", ErrorCode.NOT_FOUND),
    500: error_response("Erro interno", ErrorCode.INTERNAL_SERVER_ERROR),
}

PLACED_BETS_ERROR_RESPONSES = {
    status_code: PLACED_BET_DETAIL_ERROR_RESPONSES[status_code] for status_code in (400, 500)
}


@router.post(
    "/bets/run",
    response_model=BetRunResponse,
    responses=BETS_RUN_ERROR_RESPONSES,
)
def run_bet(
    request: BetRunRequest | None = RUN_BET_REQUEST_BODY,
    container: AppContainer = CONTAINER_DEPENDENCY,
) -> BetRunResponse | None:
    try:
        selected_lottery_modality = _parse_selected_lottery_modality(request)
        result = container.run_bet_flow.run(
            selected_lottery_modality=selected_lottery_modality,
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
        _raise_invalid_parameters(exc.details)
    except ValueError as exc:
        _raise_bad_request(exc)
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)

    return [
        PortalBetResponse(
            purchase_datetime=with_sao_paulo_timezone(result.purchase_datetime, remove_microseconds=True),
            lottery_modality=_resolve_response_lottery_modality(result.lottery_modality),
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
    try:
        parsed_lottery_modality, parsed_draw_number, parsed_start_date, parsed_end_date = _parse_placed_bet_filters(
            lottery_modality=lottery_modality,
            draw_number=draw_number,
            start_date=start_date,
            end_date=end_date,
        )
        results = container.list_placed_bets.run(
            lottery_modality=parsed_lottery_modality,
            draw_number=parsed_draw_number,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )
    except PortalBetFiltersValidationError as exc:
        _raise_invalid_parameters(exc.details)
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
        lottery_modality=result.lottery_modality,
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


def _raise_invalid_parameters(details: list[ValidationErrorDetail]) -> None:
    raise ApiError(
        status_code=400,
        code=ErrorCode.BAD_REQUEST,
        message="Parâmetros inválidos",
        details=[detail.to_dict() for detail in details],
    )


def _raise_invalid_fields(details: list[ValidationErrorDetail]) -> None:
    raise ApiError(
        status_code=400,
        code=ErrorCode.BAD_REQUEST,
        message="Campos inválidos",
        details=[detail.to_dict() for detail in details],
    )


def _parse_selected_lottery_modality(request: BetRunRequest | None) -> LotteryModality | None:
    if request is None or request.selected_lottery_modality is None:
        return None
    try:
        return parse_portal_lottery_modality(request.selected_lottery_modality, False)
    except ValueError:
        _raise_invalid_fields(
            [invalid_lottery_modality_detail("selected_lottery_modality", request.selected_lottery_modality)]
        )
        return None


def _parse_placed_bet_filters(
    *,
    lottery_modality: str | None,
    draw_number: str | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[LotteryModality | None, int | None, datetime | None, datetime | None]:
    details: list[ValidationErrorDetail] = []
    parsed_lottery_modality = _parse_filter(
        details,
        lottery_modality,
        lambda: parse_portal_lottery_modality(lottery_modality),
        lambda value: invalid_lottery_modality_detail("lottery_modality", value),
    )
    parsed_draw_number = _parse_filter(
        details,
        draw_number,
        lambda: parse_positive_int(draw_number),
        lambda value: ValidationErrorDetail(
            field="draw_number", rejected_value=value, message=INVALID_DRAW_NUMBER_MESSAGE
        ),
    )
    parsed_start_date = _parse_filter(
        details,
        start_date,
        lambda: _parse_history_date(start_date, end_of_day=False),
        lambda value: ValidationErrorDetail(field="start_date", rejected_value=value, message=INVALID_DATE_MESSAGE),
    )
    parsed_end_date = _parse_filter(
        details,
        end_date,
        lambda: _parse_history_date(end_date, end_of_day=True),
        lambda value: ValidationErrorDetail(field="end_date", rejected_value=value, message=INVALID_DATE_MESSAGE),
    )
    if (
        not details
        and parsed_start_date is not None
        and parsed_end_date is not None
        and parsed_start_date > parsed_end_date
    ):
        details.append(
            ValidationErrorDetail(
                field="start_date",
                rejected_value=start_date or "",
                message="Valor inválido. A data inicial não pode ser maior que a data final.",
            )
        )
    if details:
        raise PortalBetFiltersValidationError(details)
    return parsed_lottery_modality, parsed_draw_number, parsed_start_date, parsed_end_date


def _parse_filter[T](
    details: list[ValidationErrorDetail],
    raw_value: str | None,
    parser,
    detail_factory,
) -> T | None:
    if raw_value is None:
        return None
    try:
        return parser()
    except ValueError:
        details.append(detail_factory(raw_value))
        return None


def _parse_history_date(value: str | None, *, end_of_day: bool) -> datetime | None:
    if value is None:
        return None
    stripped = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped) is None:
        raise ValueError(INVALID_DATE_MESSAGE)
    parsed_date = datetime.strptime(stripped, "%Y-%m-%d").date()
    if end_of_day:
        return datetime.combine(parsed_date, time(23, 59, 59))
    return datetime.combine(parsed_date, time.min)


def _resolve_response_lottery_modality(value: str | None) -> str:
    if value is None:
        return ""

    stripped = value.strip()
    normalized_value = _normalize_lottery_modality_value(stripped)
    for modality in LotteryModality:
        if normalized_value in {
            _normalize_lottery_modality_value(modality.name),
            _normalize_lottery_modality_value(modality.value),
        }:
            return modality.value

    return stripped


def _normalize_lottery_modality_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_public_value(value))
