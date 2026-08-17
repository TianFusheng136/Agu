import os
from functools import lru_cache
from pathlib import Path

from app.providers.akshare_live import AkshareLiveMarketDataProvider
from app.providers.demo import DemoMarketDataProvider
from app.services.market_radar import MarketRadarService
from app.services.research_cache import FileResearchCacheStore
from app.services.sector_history import FileSectorSnapshotStore
from app.services.trading_agents import TradingAgentsService


@lru_cache(maxsize=1)
def get_market_radar_service() -> MarketRadarService:
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "live").strip().casefold()
    if provider_name == "demo":
        return MarketRadarService(DemoMarketDataProvider())
    project_root = Path(__file__).resolve().parents[3]
    cache_root = Path(
        os.getenv("MARKET_DATA_CACHE_DIR", project_root / ".runtime" / "cache")
    )
    return MarketRadarService(
        AkshareLiveMarketDataProvider(
            stock_catalog_cache_path=cache_root / "a-share-stock-catalog.json",
            warm_stock_catalog=True,
        ),
        history_store=FileSectorSnapshotStore(
            cache_root.parent / "history" / "sector-snapshots.json"
        ),
        research_cache=FileResearchCacheStore(
            cache_root / "research-last-success.json"
        ),
    )


@lru_cache(maxsize=1)
def get_trading_agents_service() -> TradingAgentsService:
    project_root = Path(__file__).resolve().parents[3]
    return TradingAgentsService(project_root / ".runtime" / "trading-agents")
