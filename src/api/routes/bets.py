from __future__ import annotations

from fastapi import APIRouter, Depends, status

from domain import AutomationError
from api.dependencies import AppContainer, get_container
from api.schemas import BetRunResponse, ErrorResponse
from api.mappers import ApiExceptionMapper

router = APIRouter(prefix="/api/v1/bets", tags=["bets"])

@router.get(
    "/run",
    response_model=BetRunResponse,
    responses={500: {"model": ErrorResponse, "description": "Erro interno ou de automação"}},
)
async def run_bet(container: AppContainer = Depends(get_container)) -> BetRunResponse | None:
    try:
        result = container.run_bet_flow.run()
        return BetRunResponse(
            sessionId=str(result.session_id),
            status=result.status,
            message=result.message,
            executedOperation=result.executed_operation.value,
            codigoAcompanhamento=result.tracking_code,
        )
    #    if result.status == "failed":
    #        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT if result.executed_operation == Operation.CONFIRM_PAYMENT else status.HTTP_500_INTERNAL_SERVER_ERROR
    #        return Utf8JSONResponse(status_code=status_code, content=response.model_dump(by_alias=True))
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)
