from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import AppContainer, get_container
from api.schemas import BetRunResponse, ErrorResponse

router = APIRouter(prefix="/api/v1/bets", tags=["bets"])


@router.get(
    "/run",
    response_model=BetRunResponse,
    responses={500: {"model": ErrorResponse, "description": "Erro interno ou de automação"}},
)
async def run_bet(container: AppContainer = Depends(get_container)) -> BetRunResponse:
    result = container.run_bet_flow.run()
    return BetRunResponse(
        sessionId=str(result.session_id),
        status=result.status,
        message=result.message,
        executedOperation=result.executed_operation,
        codigoAcompanhamento=result.tracking_code,
    )
