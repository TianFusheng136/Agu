from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_market_radar_service
from app.providers.base import MarketRefreshResult
from app.services.market_radar import (
    MarketDataStatus,
    MarketOverview,
    MarketRadarService,
    MarketSignalScan,
    RotationSnapshotCollection,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview", response_model=MarketOverview)
def get_market_overview(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> MarketOverview:
    return service.get_overview()


@router.get("/data-status", response_model=MarketDataStatus)
def get_market_data_status(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> MarketDataStatus:
    return service.get_data_status()


@router.get("/signals", response_model=MarketSignalScan)
def get_market_signals(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> MarketSignalScan:
    return service.get_market_signals()


@router.post("/refresh", response_model=MarketRefreshResult)
def refresh_market_overview(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> MarketRefreshResult:
    return service.request_market_refresh()


@router.post("/rotation-snapshot", response_model=RotationSnapshotCollection)
def collect_rotation_snapshot(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> RotationSnapshotCollection:
    return service.collect_rotation_snapshot()
