from __future__ import annotations

from fastapi import APIRouter

from api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Verificar disponibilidade da API")
async def health() -> HealthResponse:
    return HealthResponse()
