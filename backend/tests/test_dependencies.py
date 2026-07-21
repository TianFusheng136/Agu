from app.api.dependencies import get_market_radar_service
from app.providers.akshare_live import AkshareLiveMarketDataProvider


def test_default_market_provider_is_live(monkeypatch) -> None:
    warmups = []
    monkeypatch.setattr(
        AkshareLiveMarketDataProvider,
        "_start_stock_catalog_warmup",
        lambda provider: warmups.append(provider),
    )
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)
    get_market_radar_service.cache_clear()

    service = get_market_radar_service()

    assert isinstance(service._provider, AkshareLiveMarketDataProvider)
    assert warmups == [service._provider]
    assert service._provider._stock_catalog_cache_path.name == "a-share-stock-catalog.json"
    get_market_radar_service.cache_clear()
