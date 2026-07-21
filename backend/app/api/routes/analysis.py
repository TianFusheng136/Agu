from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_market_radar_service
from app.services.llm_analysis import check_llm_connection
from app.services.llm_config import save_local_llm_configuration
from app.services.market_radar import LlmAnalysisStatus, LlmMarketBrief, MarketRadarService

router = APIRouter(prefix="/analysis", tags=["analysis"])


class LlmConfigurationInput(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=8, max_length=300)


class LlmConnectionTestResult(BaseModel):
    state: Literal["connected", "failed", "not-configured"]
    code: str
    message: str
    model: str | None
    latency_ms: int | None


@router.get("/status", response_model=LlmAnalysisStatus)
def get_llm_analysis_status(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> LlmAnalysisStatus:
    del service
    return MarketRadarService.get_llm_analysis_status()


@router.put("/configuration", response_model=LlmAnalysisStatus)
def save_llm_configuration(configuration: LlmConfigurationInput) -> LlmAnalysisStatus:
    save_local_llm_configuration(
        api_key=configuration.api_key,
        model=configuration.model,
        base_url=configuration.base_url,
    )
    return MarketRadarService.get_llm_analysis_status()


@router.post("/connection-test", response_model=LlmConnectionTestResult)
def test_llm_connection() -> LlmConnectionTestResult:
    return LlmConnectionTestResult.model_validate(check_llm_connection())


@router.post("/market-brief", response_model=LlmMarketBrief)
def generate_market_brief(
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> LlmMarketBrief:
    return service.generate_llm_market_brief()
