from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_market_radar_service
from app.services.market_radar import (
    MarketRadarService,
    SectorEvidence,
    SectorOverview,
    SectorPriceHistory,
    SectorRotation,
)

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("/hot", response_model=list[SectorOverview])
def get_hot_sectors(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> list[SectorOverview]:
    return service.get_overview().hot_sectors


@router.get("/{sector_id}", response_model=SectorOverview)
def get_sector_detail(
    sector_id: str,
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> SectorOverview:
    sector = service.get_sector_detail(sector_id)
    if sector is None:
        raise HTTPException(status_code=404, detail="未找到该板块")
    return sector


@router.get("/{sector_id}/rotation", response_model=SectorRotation)
def get_sector_rotation(
    sector_id: str,
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
    days: int = 20,
) -> SectorRotation:
    rotation = service.get_sector_rotation(sector_id, days=max(5, min(days, 180)))
    if rotation is None:
        raise HTTPException(status_code=404, detail="未找到该板块")
    return rotation


@router.get("/{sector_id}/price-history", response_model=SectorPriceHistory)
def get_sector_price_history(
    sector_id: str,
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
    days: int = 20,
) -> SectorPriceHistory:
    history = service.get_sector_price_history(sector_id, days=max(5, min(days, 60)))
    if history is None:
        raise HTTPException(status_code=404, detail="未找到该板块")
    return history


@router.get("/{sector_id}/evidence", response_model=SectorEvidence)
def get_sector_evidence(
    sector_id: str,
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> SectorEvidence:
    evidence = service.get_sector_evidence(sector_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="未找到该板块")
    return evidence
