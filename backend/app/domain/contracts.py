from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Score = float
MarketLevel = Literal["强", "中", "弱"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class SectorStage(StrEnum):
    COOLING = "冷却"
    STARTING = "启动"
    RISING = "上涨"
    CLIMAX = "高潮"
    DIVERGING = "分歧"
    RETREATING = "退潮"


class MarketFactors(FrozenModel):
    breadth: Score = Field(ge=0, le=100)
    limit_balance: Score = Field(ge=0, le=100)
    promotion_rate: Score = Field(ge=0, le=100)
    seal_rate: Score = Field(ge=0, le=100)
    turnover_change: Score = Field(ge=0, le=100)
    leader_strength: Score = Field(ge=0, le=100)
    concentration: Score = Field(ge=0, le=100)
    median_return: Score = Field(ge=0, le=100)


class MarketSentiment(FrozenModel):
    score: Score = Field(ge=0, le=100)
    level: MarketLevel


class SectorFactors(FrozenModel):
    breadth: Score = Field(ge=0, le=100)
    turnover_acceleration: Score = Field(ge=0, le=100)
    relative_strength: Score = Field(ge=0, le=100)
    limit_density: Score = Field(ge=0, le=100)
    leader_strength: Score = Field(ge=0, le=100)
    capital_flow: Score = Field(ge=0, le=100)
    catalyst_strength: Score = Field(ge=0, le=100)
    previous_heat: Score = Field(ge=0, le=100)


class SectorHeat(FrozenModel):
    score: Score = Field(ge=0, le=100)
    stage: SectorStage

