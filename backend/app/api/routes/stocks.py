from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import get_market_radar_service
from app.domain.technical import TechnicalSignalStats
from app.providers.base import StockHistory
from app.services.market_radar import MarketRadarService, StockResearchSnapshot

router = APIRouter(tags=["stocks"])


@router.get("/stocks/{code}/technical-signals", response_model=TechnicalSignalStats)
def get_stock_technical_signals(
    code: Annotated[str, Path(pattern=r"^\d{6}$")],
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> TechnicalSignalStats:
    return service.get_stock_technical_signals(code)


@router.get("/stocks/{code}/research", response_model=StockResearchSnapshot)
def get_stock_research(
    code: Annotated[str, Path(pattern=r"^\d{6}$")],
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> StockResearchSnapshot:
    return service.get_stock_research(code)


@router.get("/stocks/{code}/candles", response_model=StockHistory)
def get_stock_candles(
    code: Annotated[str, Path(pattern=r"^\d{6}$")],
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
    period: Annotated[
        Literal["daily", "weekly", "monthly"],
        Query(description="K线周期"),
    ] = "daily",
    adjust: Annotated[
        Literal["", "qfq", "hfq"],
        Query(description="复权方式：空值、不复权；qfq，前复权；hfq，后复权"),
    ] = "qfq",
    limit: Annotated[int, Query(ge=20, le=250)] = 120,
) -> StockHistory:
    return service.get_stock_history(code, period, adjust, limit)
