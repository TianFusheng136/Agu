from app.providers.demo import DemoMarketDataProvider
from app.services.market_radar import MarketRadarService


def test_demo_provider_builds_ranked_market_overview() -> None:
    overview = MarketRadarService(DemoMarketDataProvider()).get_overview()

    assert overview.data_quality == "demo"
    assert overview.sentiment.level in {"强", "中", "弱"}
    assert len(overview.hot_sectors) == 3
    assert overview.hot_sectors[0].heat.score >= overview.hot_sectors[1].heat.score
    assert overview.hot_sectors[0].etfs[0].score >= overview.hot_sectors[0].etfs[1].score
    assert overview.hot_sectors[0].stocks
    assert overview.sources
    assert "投资建议" in overview.disclaimer


def test_market_overview_contains_no_trading_instruction_fields() -> None:
    overview = MarketRadarService(DemoMarketDataProvider()).get_overview()
    payload = overview.model_dump(mode="json")

    forbidden_fields = {"buy", "sell", "target_price", "position_size"}

    def collect_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            keys = set(value)
            for child in value.values():
                keys.update(collect_keys(child))
            return keys
        if isinstance(value, list):
            keys: set[str] = set()
            for child in value:
                keys.update(collect_keys(child))
            return keys
        return set()

    assert collect_keys(payload).isdisjoint(forbidden_fields)
