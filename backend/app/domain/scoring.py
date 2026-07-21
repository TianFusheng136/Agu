from app.domain.contracts import (
    MarketFactors,
    MarketLevel,
    MarketSentiment,
    SectorFactors,
    SectorHeat,
    SectorStage,
)

MARKET_WEIGHTS = {
    "breadth": 0.15,
    "limit_balance": 0.15,
    "promotion_rate": 0.15,
    "seal_rate": 0.15,
    "turnover_change": 0.15,
    "leader_strength": 0.10,
    "concentration": 0.10,
    "median_return": 0.05,
}

SECTOR_WEIGHTS = {
    "breadth": 0.20,
    "turnover_acceleration": 0.20,
    "relative_strength": 0.15,
    "limit_density": 0.15,
    "leader_strength": 0.10,
    "capital_flow": 0.10,
    "catalyst_strength": 0.10,
}


def _weighted_score(model: MarketFactors | SectorFactors, weights: dict[str, float]) -> float:
    return round(sum(getattr(model, name) * weight for name, weight in weights.items()), 1)


def _market_level(score: float) -> MarketLevel:
    if score >= 70:
        return "强"
    if score >= 45:
        return "中"
    return "弱"


def calculate_market_sentiment(factors: MarketFactors) -> MarketSentiment:
    score = _weighted_score(factors, MARKET_WEIGHTS)
    return MarketSentiment(score=score, level=_market_level(score))


def _sector_stage(score: float, previous_heat: float) -> SectorStage:
    if score >= 80 and score - previous_heat >= 15:
        return SectorStage.RISING
    if score >= 80:
        return SectorStage.CLIMAX
    if score >= 65:
        return SectorStage.STARTING
    if score >= 45:
        return SectorStage.DIVERGING
    return SectorStage.RETREATING


def calculate_sector_heat(factors: SectorFactors) -> SectorHeat:
    score = _weighted_score(factors, SECTOR_WEIGHTS)
    return SectorHeat(score=score, stage=_sector_stage(score, factors.previous_heat))

