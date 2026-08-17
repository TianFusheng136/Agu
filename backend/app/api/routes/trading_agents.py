from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_market_radar_service, get_trading_agents_service
from app.services.market_radar import MarketRadarService
from app.services.trading_agents import TradingAgentsService, build_price_context

router = APIRouter(prefix="/trading-agents", tags=["trading-agents"])


class TradingAgentsRunInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    analysis_date: date | None = None
    depth: Literal["quick", "standard"] = "quick"


@router.get("/status")
def get_status(
    service: Annotated[TradingAgentsService, Depends(get_trading_agents_service)],
) -> dict[str, Any]:
    return service.status()


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def start_run(
    payload: TradingAgentsRunInput,
    service: Annotated[TradingAgentsService, Depends(get_trading_agents_service)],
    market_service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> dict[str, Any]:
    try:
        try:
            price_context = build_price_context(
                market_service.get_stock_research(payload.code).history
            )
        except Exception:
            price_context = {
                "state": "unavailable",
                "message": "站内日 K 暂不可用，未计算观察区间。",
            }
        return service.start_run(
            code=payload.code,
            analysis_date=payload.analysis_date,
            depth=payload.depth,
            price_context=price_context,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/runs/{job_id}")
def get_run(
    job_id: str,
    service: Annotated[TradingAgentsService, Depends(get_trading_agents_service)],
) -> dict[str, Any]:
    run = service.get_run(job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="未找到该研判任务")
    return run
