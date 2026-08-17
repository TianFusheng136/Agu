from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.etfs import router as etfs_router
from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.search import router as search_router
from app.api.routes.sectors import router as sectors_router
from app.api.routes.stocks import router as stocks_router
from app.api.routes.trading_agents import router as trading_agents_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(analysis_router)
api_router.include_router(etfs_router)
api_router.include_router(health_router)
api_router.include_router(market_router)
api_router.include_router(sectors_router)
api_router.include_router(search_router)
api_router.include_router(stocks_router)
api_router.include_router(trading_agents_router)
