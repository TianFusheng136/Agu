from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_market_radar_service
from app.services.market_radar import EtfResearch, MarketRadarService

router = APIRouter(prefix="/etfs", tags=["etfs"])


@router.get("/{code}", response_model=EtfResearch)
def get_etf_research(
    code: str,
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> EtfResearch:
    research = service.get_etf_research(code, days=120)
    if research is None:
        raise HTTPException(status_code=404, detail="ETF research is unavailable for this code")
    return research
