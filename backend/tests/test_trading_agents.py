from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_market_radar_service, get_trading_agents_service
from app.main import app
from app.providers.demo import DemoMarketDataProvider
from app.services.market_radar import MarketRadarService
from app.services.trading_agents import (
    TradingAgentsService,
    build_direction_summary,
    normalize_a_share_ticker,
)


def test_normalize_a_share_ticker() -> None:
    assert normalize_a_share_ticker("600519") == "600519.SS"
    assert normalize_a_share_ticker("688981") == "688981.SS"
    assert normalize_a_share_ticker("000021") == "000021.SZ"
    assert normalize_a_share_ticker("300750") == "300750.SZ"


@pytest.mark.parametrize("code", ["123", "ABCDEF", "920088"])
def test_normalize_a_share_ticker_rejects_unsupported_codes(code: str) -> None:
    with pytest.raises(ValueError):
        normalize_a_share_ticker(code)


def test_status_is_explicit_when_package_is_missing(monkeypatch, tmp_path) -> None:
    service = TradingAgentsService(tmp_path)
    monkeypatch.setattr(service, "package_installed", lambda: False)

    status = service.status()

    assert status["state"] == "package-missing"
    assert status["execution_enabled"] is False
    assert status["analysts"] == ["技术", "情绪", "新闻", "基本面"]


def test_direction_summary_exposes_tilt_without_calling_it_probability() -> None:
    summary = build_direction_summary(
        "**Rating**: Overweight\n\n**Price Target**: 12.5",
        {"state": "inside-zone", "current_price": 10.2},
    )

    assert summary["direction"] == "偏多"
    assert summary["bullish_weight"] == 65
    assert summary["bearish_weight"] == 35
    assert "不是" in summary["weight_note"]
    assert summary["framework_price_target"] == 12.5


class FakeTradingAgentsService:
    def status(self):
        return {
            "state": "ready",
            "installed": True,
            "configured": True,
            "version": "0.3.1",
            "model": "test-model",
            "message": "ready",
            "analysts": ["技术", "情绪", "新闻", "基本面"],
            "data_source": "test",
            "execution_enabled": False,
        }

    def start_run(self, *, code, analysis_date, depth, price_context=None):
        assert code == "600519"
        assert analysis_date == date(2026, 8, 8)
        assert depth == "quick"
        assert price_context is not None
        return {"id": "job-1", "state": "queued", "code": code}

    def get_run(self, job_id):
        if job_id != "job-1":
            return None
        return {"id": job_id, "state": "completed", "result": {"final_assessment": "研究完成"}}


def test_trading_agents_api_starts_and_reads_a_background_run() -> None:
    app.dependency_overrides[get_trading_agents_service] = FakeTradingAgentsService
    app.dependency_overrides[get_market_radar_service] = lambda: MarketRadarService(
        DemoMarketDataProvider()
    )
    client = TestClient(app)
    try:
        created = client.post(
            "/api/v1/trading-agents/runs",
            json={"code": "600519", "analysis_date": "2026-08-08", "depth": "quick"},
        )
        fetched = client.get("/api/v1/trading-agents/runs/job-1")
    finally:
        app.dependency_overrides.pop(get_trading_agents_service, None)
        app.dependency_overrides.pop(get_market_radar_service, None)

    assert created.status_code == 202
    assert created.json()["state"] == "queued"
    assert fetched.status_code == 200
    assert fetched.json()["result"]["final_assessment"] == "研究完成"
