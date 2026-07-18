from api.routes.bets import placed_bets_router
from api.routes.bets import router as bets_router
from api.routes.health import router as health_router
from api.routes.sessions import router as sessions_router

__all__ = ["bets_router", "health_router", "placed_bets_router", "sessions_router"]
