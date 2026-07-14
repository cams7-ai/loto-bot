from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import AppContainer, get_container
from api.mappers import ApiExceptionMapper
from api.schemas import BetRunResponse, ErrorResponse, error_response_examples
from domain import AutomationError, ErrorCode

router = APIRouter(prefix="/api/v1/bets", tags=["bets"])
CONTAINER_DEPENDENCY = Depends(get_container)


def error_response(description: str, *codes: ErrorCode) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json; charset=utf-8": {
                "examples": error_response_examples(*codes),
            }
        },
    }


ERROR_RESPONSES = {
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


@router.get(
    "/run",
    response_model=BetRunResponse,
    responses=ERROR_RESPONSES,
)
async def run_bet(container: AppContainer = CONTAINER_DEPENDENCY) -> BetRunResponse | None:
    try:
        result = container.run_bet_flow.run()
        return BetRunResponse(
            session_id=str(result.session_id),
            status=result.status,
            message=result.message,
            executed_operation=result.executed_operation.value,
            purchase_number=result.purchase_number,
        )
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)
