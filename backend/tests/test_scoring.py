from app.domain.contracts import MarketFactors, SectorFactors, SectorStage
from app.domain.scoring import calculate_market_sentiment, calculate_sector_heat


def test_market_sentiment_is_weighted_and_classified() -> None:
    result = calculate_market_sentiment(
        MarketFactors(
            breadth=80,
            limit_balance=70,
            promotion_rate=60,
            seal_rate=50,
            turnover_change=90,
            leader_strength=80,
            concentration=70,
            median_return=60,
        )
    )

    assert result.score == 70.5
    assert result.level == "强"


def test_sector_heat_uses_deterministic_stage() -> None:
    result = calculate_sector_heat(
        SectorFactors(
            breadth=85,
            turnover_acceleration=90,
            relative_strength=88,
            limit_density=70,
            leader_strength=82,
            capital_flow=65,
            catalyst_strength=75,
            previous_heat=58,
        )
    )

    assert result.score == 80.9
    assert result.stage is SectorStage.RISING


def test_market_factor_values_must_be_bounded() -> None:
    try:
        MarketFactors(
            breadth=101,
            limit_balance=70,
            promotion_rate=60,
            seal_rate=50,
            turnover_change=90,
            leader_strength=80,
            concentration=70,
            median_return=60,
        )
    except ValueError as error:
        assert "less than or equal to 100" in str(error)
    else:
        raise AssertionError("Expected bounded factor validation")

