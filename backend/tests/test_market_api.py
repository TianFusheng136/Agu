from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_radar_service
from app.main import app
from app.providers.base import MarketDataUnavailable, StockNewsRecord
from app.providers.demo import DemoMarketDataProvider
from app.services import research_cache
from app.services.llm_config import get_llm_runtime_configuration, save_local_llm_configuration
from app.services.market_radar import MarketRadarService


def demo_service() -> MarketRadarService:
    return MarketRadarService(DemoMarketDataProvider())


app.dependency_overrides[get_market_radar_service] = demo_service
client = TestClient(app, raise_server_exceptions=False)


def _without_llm_configuration(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_CONFIG_PATH", str(tmp_path / "no-llm-config.json"))


def test_market_overview_endpoint() -> None:
    response = client.get("/api/v1/market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_quality"] == "demo"
    assert len(payload["hot_sectors"]) == 3
    assert payload["hot_sectors"][0]["etfs"]


def test_market_refresh_endpoint_returns_an_explicit_provider_status() -> None:
    response = client.post("/api/v1/market/refresh")

    assert response.status_code == 200
    assert response.json()["state"] == "not-supported"


def test_market_data_status_exposes_sources_and_unavailable_fields() -> None:
    response = client.get("/api/v1/market/data-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_quality"] == "demo"
    assert payload["sources"]
    assert any(item["state"] == "unavailable" for item in payload["fields"])


def test_market_signal_scan_summarizes_current_hot_sector_representatives() -> None:
    response = client.get("/api/v1/market/signals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["scope"] == "current-hot-sector-representatives"
    assert payload["scanned_count"] == len(payload["items"])
    assert payload["scanned_count"] > 0
    assert {bucket["id"] for bucket in payload["buckets"]} == {
        "macd_golden_cross",
        "macd_death_cross",
        "kdj_golden_cross",
        "kdj_death_cross",
        "weekly_volume_anomaly",
    }
    assert {"code", "macd_state", "kdj_state", "weekly_state"}.issubset(
        payload["items"][0]
    )


def test_market_signal_scan_retries_one_transient_history_failure() -> None:
    class RetryOnceProvider(DemoMarketDataProvider):
        def __init__(self) -> None:
            super().__init__()
            self.history_attempts = 0

        def get_market_payload(self):
            payload = super().get_market_payload()
            sector = payload.sectors[0].model_copy(
                update={"stocks": payload.sectors[0].stocks[:1]}
            )
            return payload.model_copy(update={"sectors": [sector]})

        def get_stock_history(self, *args, **kwargs):
            self.history_attempts += 1
            if self.history_attempts == 1:
                raise ConnectionError("transient public history failure")
            return super().get_stock_history(*args, **kwargs)

    provider = RetryOnceProvider()
    scan = MarketRadarService(provider).get_market_signals()

    assert provider.history_attempts == 2
    assert scan.state == "available"
    assert scan.scanned_count == 1
    assert scan.cached_count == 0
    assert scan.query_failures == []
    assert scan.items[0].data_state == "live"
    assert scan.items[0].cached_at is None


def test_market_signal_scan_keeps_last_success_when_refresh_fails() -> None:
    class SwitchableHistoryProvider(DemoMarketDataProvider):
        def __init__(self) -> None:
            super().__init__()
            self.fail_history = False
            self.history_attempts = 0

        def get_market_payload(self):
            payload = super().get_market_payload()
            sector = payload.sectors[0].model_copy(
                update={"stocks": payload.sectors[0].stocks[:1]}
            )
            return payload.model_copy(update={"sectors": [sector]})

        def get_stock_history(self, *args, **kwargs):
            self.history_attempts += 1
            if self.fail_history:
                raise ConnectionError("public history unavailable")
            return super().get_stock_history(*args, **kwargs)

    provider = SwitchableHistoryProvider()
    service = MarketRadarService(provider)

    first_scan = service.get_market_signals()
    provider.fail_history = True
    second_scan = service.get_market_signals()

    assert first_scan.scanned_count == 1
    assert first_scan.cached_count == 0
    assert provider.history_attempts == 3
    assert second_scan.state == "available"
    assert second_scan.scanned_count == 1
    assert second_scan.cached_count == 1
    assert second_scan.query_failures == ["000021:ConnectionError"]
    assert second_scan.items[0].code == first_scan.items[0].code
    assert second_scan.items[0].data_state == "cached"
    assert second_scan.items[0].cached_at
    assert second_scan.items[0].as_of == first_scan.items[0].as_of


def test_signal_and_news_last_success_survive_service_restart(tmp_path) -> None:
    class PersistentResearchProvider(DemoMarketDataProvider):
        def __init__(self, *, failing: bool) -> None:
            super().__init__()
            self.failing = failing

        def get_market_payload(self):
            payload = super().get_market_payload()
            sector = payload.sectors[0].model_copy(
                update={"stocks": payload.sectors[0].stocks[:1]}
            )
            return payload.model_copy(update={"sectors": [sector]})

        def get_stock_history(self, *args, **kwargs):
            if self.failing:
                raise ConnectionError("public history unavailable after restart")
            return super().get_stock_history(*args, **kwargs)

        def get_stock_news(self, code: str, limit: int = 5):
            if self.failing:
                raise ConnectionError("public news unavailable after restart")
            return [
                StockNewsRecord(
                    title=f"{code}公开新闻",
                    summary="公开新闻摘要。",
                    published_at="2026-07-21 09:30:00",
                    source="公开新闻源",
                    url=f"https://example.test/news/{code}",
                )
            ][:limit]

    path = tmp_path / "research-last-success.json"
    first_service = MarketRadarService(
        PersistentResearchProvider(failing=False),
        research_cache=research_cache.FileResearchCacheStore(path),
    )
    assert first_service.get_market_signals().cached_count == 0
    first_evidence = first_service.get_sector_evidence("ai-server")
    assert first_evidence is not None and first_evidence.cached_count == 0

    restarted_service = MarketRadarService(
        PersistentResearchProvider(failing=True),
        research_cache=research_cache.FileResearchCacheStore(path),
    )
    restarted_signals = restarted_service.get_market_signals()
    restarted_evidence = restarted_service.get_sector_evidence("ai-server")

    assert restarted_signals.scanned_count == 1
    assert restarted_signals.cached_count == 1
    assert restarted_signals.items[0].data_state == "cached"
    assert restarted_evidence is not None
    assert restarted_evidence.cached_count == 1
    assert restarted_evidence.news[0].data_state == "cached"


def test_rotation_snapshot_collection_records_only_the_current_provider_facts() -> None:
    response = client.post("/api/v1/market/rotation-snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "recorded"
    assert payload["sectors_recorded"] == 3
    assert payload["as_of"]


def test_market_overview_returns_503_when_live_source_is_unavailable() -> None:
    class FailingProvider:
        def get_market_payload(self):
            raise MarketDataUnavailable("上游公开行情暂时不可用")

    app.dependency_overrides[get_market_radar_service] = lambda: MarketRadarService(
        FailingProvider()
    )
    try:
        response = client.get("/api/v1/market/overview")
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 503
    assert response.json()["detail"] == "上游公开行情暂时不可用"


def test_hot_sectors_and_sector_detail_endpoints() -> None:
    hot_response = client.get("/api/v1/sectors/hot")
    detail_response = client.get("/api/v1/sectors/ai-server")
    missing_response = client.get("/api/v1/sectors/not-found")

    assert hot_response.status_code == 200
    assert len(hot_response.json()) == 3
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "AI服务器"
    assert missing_response.status_code == 404


def test_sector_evidence_and_llm_status_are_explicit_when_not_available(
    monkeypatch, tmp_path
) -> None:
    _without_llm_configuration(monkeypatch, tmp_path)
    evidence_response = client.get("/api/v1/sectors/ai-server/evidence")
    llm_response = client.get("/api/v1/analysis/status")

    assert evidence_response.status_code == 200
    assert evidence_response.json()["state"] == "unavailable"
    assert llm_response.status_code == 200
    assert llm_response.json()["state"] == "not-configured"


def test_llm_configuration_endpoint_stores_the_key_only_on_the_local_backend(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_BASE_URL", raising=False)
    config_path = tmp_path / "llm-config.json"
    monkeypatch.setenv("LLM_CONFIG_PATH", str(config_path))

    response = client.put(
        "/api/v1/analysis/configuration",
        json={
            "api_key": "test-local-key",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "state": "configured",
        "provider": "OpenAI-compatible API",
        "model": "deepseek-v4-flash",
        "message": "模型已配置；只接收冻结后的结构化事实，不能改写行情数字。",
    }
    assert "api_key" not in response.json()
    assert config_path.exists()


def test_local_web_configuration_overrides_a_stale_environment_value(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_CONFIG_PATH", str(tmp_path / "llm-config.json"))
    monkeypatch.setenv("LLM_API_KEY", "stale-environment-key")
    monkeypatch.setenv("LLM_MODEL", "stale-model")
    monkeypatch.setenv("LLM_API_BASE_URL", "https://stale.example.com")
    save_local_llm_configuration(
        api_key="web-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )

    configuration = get_llm_runtime_configuration()

    assert configuration.api_key == "web-key"
    assert configuration.model == "deepseek-v4-flash"
    assert configuration.base_url == "https://api.deepseek.com"


def test_sector_evidence_aggregates_multiple_representative_stocks() -> None:
    class MultiStockNewsProvider(DemoMarketDataProvider):
        def get_stock_news(self, code: str, limit: int = 5):
            return [
                StockNewsRecord(
                    title=f"{code} public news",
                    summary="Evidence attached to a representative stock.",
                    published_at="2026-07-20 14:00:00",
                    source="public source",
                    url=f"https://example.test/{code}",
                )
            ][:limit]

    app.dependency_overrides[get_market_radar_service] = lambda: MarketRadarService(
        MultiStockNewsProvider()
    )
    try:
        response = client.get("/api/v1/sectors/ai-server/evidence")
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "available"
    assert {item["code"] for item in payload["news"]} == {"000021", "300308"}
    assert {item["code"] for item in payload["representative_stocks"]} == {
        "000021",
        "300308",
    }


def test_sector_evidence_retries_one_transient_news_failure() -> None:
    class RetryOnceNewsProvider(DemoMarketDataProvider):
        def __init__(self) -> None:
            super().__init__()
            self.news_attempts = 0

        def get_market_payload(self):
            payload = super().get_market_payload()
            sector = payload.sectors[0].model_copy(
                update={"stocks": payload.sectors[0].stocks[:1]}
            )
            return payload.model_copy(update={"sectors": [sector]})

        def get_stock_news(self, code: str, limit: int = 5):
            self.news_attempts += 1
            if self.news_attempts == 1:
                raise ConnectionError("transient public news failure")
            return [
                StockNewsRecord(
                    title=f"{code}公开新闻",
                    summary="公开新闻摘要。",
                    published_at="2026-07-21 09:30:00",
                    source="公开新闻源",
                    url=f"https://example.test/news/{code}",
                )
            ][:limit]

    provider = RetryOnceNewsProvider()
    evidence = MarketRadarService(provider).get_sector_evidence("ai-server")

    assert provider.news_attempts == 2
    assert evidence is not None
    assert evidence.state == "available"
    assert evidence.cached_count == 0
    assert evidence.query_failures == []
    assert evidence.news[0].data_state == "live"
    assert evidence.news[0].cached_at is None


def test_sector_evidence_keeps_last_success_when_news_refresh_fails() -> None:
    class SwitchableNewsProvider(DemoMarketDataProvider):
        def __init__(self) -> None:
            super().__init__()
            self.fail_news = False
            self.news_attempts = 0

        def get_market_payload(self):
            payload = super().get_market_payload()
            sector = payload.sectors[0].model_copy(
                update={"stocks": payload.sectors[0].stocks[:1]}
            )
            return payload.model_copy(update={"sectors": [sector]})

        def get_stock_news(self, code: str, limit: int = 5):
            self.news_attempts += 1
            if self.fail_news:
                raise ConnectionError("public news unavailable")
            return [
                StockNewsRecord(
                    title=f"{code}公开新闻",
                    summary="公开新闻摘要。",
                    published_at="2026-07-21 09:30:00",
                    source="公开新闻源",
                    url=f"https://example.test/news/{code}",
                )
            ][:limit]

    provider = SwitchableNewsProvider()
    service = MarketRadarService(provider)

    first = service.get_sector_evidence("ai-server")
    provider.fail_news = True
    second = service.get_sector_evidence("ai-server")

    assert first is not None and first.cached_count == 0
    assert provider.news_attempts == 3
    assert second is not None
    assert second.state == "available"
    assert second.cached_count == 1
    assert second.query_failures == ["000021:ConnectionError"]
    assert second.news[0].data_state == "cached"
    assert second.news[0].cached_at
    assert second.news[0].title == first.news[0].title


def test_llm_market_brief_never_falls_back_to_a_fake_generated_answer(
    monkeypatch, tmp_path
) -> None:
    _without_llm_configuration(monkeypatch, tmp_path)
    response = client.post("/api/v1/analysis/market-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "not-configured"
    assert payload["analysis"] is None


def test_generated_llm_brief_returns_the_frozen_facts_used_for_audit(monkeypatch) -> None:
    class StructuredEvidenceProvider(DemoMarketDataProvider):
        def get_sector_price_history(self, sector_name: str, days: int):
            assert days == 20
            return {
                "state": "available",
                "requested_name": sector_name,
                "source_name": sector_name,
                "source": "AKShare/THS industry board history",
                "message": "20 real trading days.",
                "summary": {
                    "period_days": 20,
                    "period_change_pct": 3.2,
                    "latest_turnover_billion": 120.0,
                    "turnover_change_pct": 9.5,
                    "volume_change_pct": 8.4,
                    "trend_5d_pct": 6.5,
                    "trend_20d_pct": 3.2,
                    "relative_strength_pct": 4.1,
                    "benchmark_name": "上证指数",
                },
                "points": [],
            }

        def get_stock_news(self, code: str, limit: int = 5):
            return [
                StockNewsRecord(
                    title=f"{code}公开新闻证据",
                    summary="代表股公开新闻摘要。",
                    published_at="2026-07-20 14:00:00",
                    source="公开新闻源",
                    url=f"https://example.test/{code}",
                )
            ][:limit]

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    captured: dict[str, object] = {}

    def capture_facts(facts):
        captured.update(facts)
        return {
            "market_conclusion": "市场分化，热点仍有结构性强度。",
            "evidence": ["[轮动] 近5日趋势已纳入。", "[新闻] 仅关联代表股。"],
            "risks": ["[技术] 代表股信号存在分化。"],
            "data_gaps": ["[缺失] 北向资金暂缺。"],
        }

    monkeypatch.setattr(
        "app.services.market_radar.generate_evidence_explanation",
        capture_facts,
    )
    app.dependency_overrides[get_market_radar_service] = lambda: MarketRadarService(
        StructuredEvidenceProvider()
    )
    try:
        response = client.post("/api/v1/analysis/market-brief")
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "generated"
    assert payload["sections"] == {
        "market_conclusion": "市场分化，热点仍有结构性强度。",
        "evidence": ["[轮动] 近5日趋势已纳入。", "[新闻] 仅关联代表股。"],
        "risks": ["[技术] 代表股信号存在分化。"],
        "data_gaps": ["[缺失] 北向资金暂缺。"],
    }
    assert payload["facts"]["as_of"]
    assert payload["facts"]["directions"][0]["name"]
    assert "representative_stock_available" in payload["facts"]["directions"][0]
    assert payload["facts"]["market_metrics"]["advancers"] == 3216
    assert payload["facts"]["directions"][0]["capital_flow_label"] == (
        "行业资金净额（非主力净流入）"
    )
    assert payload["facts"]["directions"][0]["rotation"]["trend_5d_pct"] == 6.5
    assert payload["facts"]["directions"][0]["news"][0]["source"] == "公开新闻源"
    assert payload["facts"]["technical_signals"]["scanned_count"] > 0
    assert payload["facts"]["technical_signals"]["cached_count"] == 0
    assert payload["facts"]["technical_signals"]["buckets"]
    assert any("北向资金" in item for item in payload["facts"]["data_gaps"])
    assert captured["directions"] == payload["facts"]["directions"]


def test_llm_connection_endpoint_returns_a_safe_diagnostic(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.analysis.check_llm_connection",
        lambda: {
            "state": "failed",
            "code": "invalid-model",
            "message": "模型名称不可用，请填写服务商支持的模型ID。",
            "model": "missing-model",
            "latency_ms": 82,
        },
        raising=False,
    )

    response = client.post("/api/v1/analysis/connection-test")

    assert response.status_code == 200
    assert response.json() == {
        "state": "failed",
        "code": "invalid-model",
        "message": "模型名称不可用，请填写服务商支持的模型ID。",
        "model": "missing-model",
        "latency_ms": 82,
    }


def test_sector_rotation_endpoint_marks_new_history_as_collecting() -> None:
    response = client.get("/api/v1/sectors/ai-server/rotation", params={"days": 20})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["capital_flow_label"] == "行业资金净额（非主力净流入）"
    assert payload["classification"]["canonical_name"] == "AI服务器"


def test_sector_rotation_uses_20_real_price_days_without_fabricating_heat() -> None:
    class HistoricalRotationProvider(DemoMarketDataProvider):
        def get_sector_price_history(self, sector_name: str, days: int):
            assert sector_name == "AI服务器"
            assert days == 20
            return {
                "state": "available",
                "requested_name": sector_name,
                "source_name": sector_name,
                "source": "AKShare/THS industry board history",
                "message": "20 real trading days.",
                "summary": {
                    "period_days": 20,
                    "period_change_pct": 19.0,
                    "latest_turnover_billion": 120.0,
                    "turnover_change_pct": 2.0,
                    "volume_change_pct": 3.0,
                    "trend_5d_pct": 5.0,
                    "trend_20d_pct": 19.0,
                    "relative_strength_pct": 8.0,
                    "benchmark_name": "上证指数",
                },
                "points": [
                    {
                        "date": f"2026-07-{index + 1:02d}",
                        "close": 100.0 + index,
                        "change_pct": 1.0 if index else None,
                        "turnover_billion": 100.0 + index,
                        "turnover_change_pct": 1.0 if index else None,
                        "volume_change_pct": 2.0 if index else None,
                        "relative_strength_pct": index * 0.4,
                    }
                    for index in range(20)
                ],
            }

    rotation = MarketRadarService(
        HistoricalRotationProvider()
    ).get_sector_rotation("ai-server", 20)

    assert rotation is not None
    assert rotation.status == "ready"
    assert rotation.basis == "source-price-history"
    assert rotation.source == "AKShare/THS industry board history"
    assert rotation.data_points == 20
    assert rotation.snapshot_data_points == 1
    assert rotation.points[0].strength_score == 0
    assert rotation.points[-1].strength_score == 100
    assert all(point.rank is None for point in rotation.points)
    assert all(point.heat_score is None for point in rotation.points)
    assert all(point.capital_flow_billion is None for point in rotation.points)


def test_sector_price_history_returns_source_labeled_real_history() -> None:
    class HistoricalDemoProvider(DemoMarketDataProvider):
        def get_sector_price_history(self, sector_name: str, days: int):
            assert sector_name == "AI服务器"
            assert days == 20
            return {
                "state": "available",
                "requested_name": sector_name,
                "source_name": "AI服务器",
                "source": "AKShare·东方财富行业板块历史行情",
                "message": "Historical price series from the matched source board.",
                "points": [
                    {"date": "2026-07-17", "close": 100.0, "change_pct": 1.2},
                    {"date": "2026-07-20", "close": 102.0, "change_pct": 2.0},
                ],
            }

    app.dependency_overrides[get_market_radar_service] = lambda: MarketRadarService(
        HistoricalDemoProvider()
    )
    try:
        response = client.get("/api/v1/sectors/ai-server/price-history", params={"days": 20})
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["source"] == "AKShare·东方财富行业板块历史行情"
    assert [point["close"] for point in payload["points"]] == [100.0, 102.0]


def test_etf_research_endpoint_returns_public_price_history_and_mapping_audit() -> None:
    class EtfResearchDemoProvider(DemoMarketDataProvider):
        def get_etf_research(self, code: str, days: int):
            assert (code, days) == ("515980", 120)
            return {
                "code": code,
                "name": "人工智能ETF",
                "as_of": "2026-07-20",
                "change_pct": 1.2,
                "source": "AKShare/Eastmoney ETF history",
                "points": [
                    {"date": "2026-07-17", "close": 1.0, "change_pct": 0.5},
                    {"date": "2026-07-20", "close": 1.02, "change_pct": 2.0},
                ],
                "fund_profile": {
                    "state": "available",
                    "full_name": "华富中证人工智能产业ETF",
                    "benchmark": "中证人工智能产业指数收益率",
                    "manager": "华富基金管理有限公司",
                    "share_scale": "12.50亿份（2026-06-30）",
                    "source": "AKShare/THS fund profile",
                    "retrieved_at": "2026-07-20T10:30:00+08:00",
                    "message": "公开基金资料已返回。",
                },
            }

    app.dependency_overrides[get_market_radar_service] = lambda: MarketRadarService(
        EtfResearchDemoProvider()
    )
    try:
        response = client.get("/api/v1/etfs/515980")
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "515980"
    assert payload["price_history"]["source"] == "AKShare/Eastmoney ETF history"
    assert payload["price_history"]["points"][-1]["close"] == 1.02
    assert payload["fund_profile"]["benchmark"] == "中证人工智能产业指数收益率"
    assert payload["fund_profile"]["source"] == "AKShare/THS fund profile"


def test_search_finds_stock_sector_and_etf() -> None:
    stock_results = client.get("/api/v1/search", params={"q": "深科技"}).json()
    sector_results = client.get("/api/v1/search", params={"q": "机器人"}).json()
    etf_results = client.get("/api/v1/search", params={"q": "515980"}).json()

    assert stock_results[0]["kind"] == "stock"
    assert sector_results[0]["kind"] == "sector"
    assert etf_results[0]["kind"] == "etf"


def test_search_rejects_blank_query() -> None:
    response = client.get("/api/v1/search", params={"q": " "})

    assert response.status_code == 422


def test_cors_allows_the_default_127_frontend_origin() -> None:
    response = client.options(
        "/api/v1/search?q=000021",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_search_finds_a_stock_outside_the_hot_sector_snapshot() -> None:
    class CatalogSearchService:
        def get_overview(self):
            return demo_service().get_overview()

        def search_stocks(self, query: str, limit: int = 12):
            assert query == "000001"
            assert limit == 12
            return [
                SimpleNamespace(code="000001", name="平安银行"),
            ]

    app.dependency_overrides[get_market_radar_service] = CatalogSearchService
    try:
        response = client.get("/api/v1/search", params={"q": "000001"})
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    assert response.json()[0] == {
        "kind": "stock",
        "id": "000001",
        "name": "平安银行",
        "subtitle": "000001 · A股",
    }


def test_search_returns_snapshot_matches_without_waiting_for_full_catalog() -> None:
    class SlowCatalogSearchService:
        def get_overview(self):
            return demo_service().get_overview()

        def search_stocks(self, query: str, limit: int = 12):
            raise AssertionError("snapshot match must not load the full stock catalog")

    app.dependency_overrides[get_market_radar_service] = SlowCatalogSearchService
    try:
        response = client.get("/api/v1/search", params={"q": "机器人"})
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    assert response.json()[0]["kind"] == "sector"


def test_exact_stock_code_search_does_not_wait_for_market_overview() -> None:
    class ExactCodeSearchService:
        def get_overview(self):
            raise AssertionError("exact stock code search must not load market overview")

        def search_stocks(self, query: str, limit: int = 12):
            assert query == "000021"
            assert limit == 12
            return [SimpleNamespace(code="000021", name="深科技")]

    app.dependency_overrides[get_market_radar_service] = ExactCodeSearchService
    try:
        response = client.get("/api/v1/search", params={"q": "000021"})
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    assert response.json() == [
        {
            "kind": "stock",
            "id": "000021",
            "name": "深科技",
            "subtitle": "000021 · A股",
        }
    ]


def test_stock_kline_endpoint_returns_normalized_candles() -> None:
    class StockHistoryService:
        def get_stock_history(
            self,
            code: str,
            period: str,
            adjust: str,
            limit: int,
        ):
            assert (code, period, adjust, limit) == ("000021", "daily", "qfq", 120)
            return {
                "code": "000021",
                "name": "深科技",
                "period": "daily",
                "adjust": "qfq",
                "as_of": "2026-07-17",
                "data_quality": "live-public",
                "source": "AKShare·东方财富A股历史行情",
                "candles": [
                    {
                        "date": "2026-07-17",
                        "open": 22.1,
                        "high": 23.4,
                        "low": 21.8,
                        "close": 23.0,
                        "volume": 123456.0,
                        "amount": 281234567.0,
                        "change_pct": 4.55,
                    }
                ],
            }

    app.dependency_overrides[get_market_radar_service] = StockHistoryService
    try:
        response = client.get("/api/v1/stocks/000021/candles")
    finally:
        app.dependency_overrides[get_market_radar_service] = demo_service

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "深科技"
    assert payload["candles"][0]["close"] == 23.0


def test_stock_technical_signals_endpoint_returns_statistics_not_trade_instruction() -> None:
    response = client.get("/api/v1/stocks/000021/technical-signals")

    assert response.status_code == 200
    payload = response.json()
    assert {"macd", "kdj", "weekly"}.issubset(payload)
    assert "买入" not in payload["disclaimer"]
    assert "卖出" not in payload["disclaimer"]


def test_stock_research_endpoint_returns_kline_and_signals_in_one_request() -> None:
    response = client.get("/api/v1/stocks/000021/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["history"]["code"] == "000021"
    assert payload["history"]["candles"]
    assert payload["technical"]["sample_size"] >= 20
