import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from threading import Event
from time import monotonic, sleep
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.providers.akshare_live import AkshareClient, AkshareLiveMarketDataProvider
from app.providers.base import MarketDataUnavailable


class FakeAkshareClient:
    def __init__(self) -> None:
        self.industry_calls = 0

    def industry_summary(self) -> pd.DataFrame:
        self.industry_calls += 1
        return pd.DataFrame(
            [
                {
                    "板块": "电力",
                    "涨跌幅": 3.2,
                    "总成交额": 600.0,
                    "净流入": 45.0,
                    "上涨家数": 25,
                    "下跌家数": 5,
                    "领涨股": "珈伟新能",
                    "领涨股-涨跌幅": 16.01,
                },
                {
                    "板块": "银行",
                    "涨跌幅": 1.1,
                    "总成交额": 400.0,
                    "净流入": 30.0,
                    "上涨家数": 20,
                    "下跌家数": 10,
                    "领涨股": "建设银行",
                    "领涨股-涨跌幅": 3.67,
                },
                {
                    "板块": "房地产开发",
                    "涨跌幅": -0.5,
                    "总成交额": 100.0,
                    "净流入": -5.0,
                    "上涨家数": 5,
                    "下跌家数": 15,
                    "领涨股": "沙河股份",
                    "领涨股-涨跌幅": 2.0,
                },
            ]
        )

    def market_breadth(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"item": "上涨", "value": 405},
                {"item": "下跌", "value": 4758},
                {"item": "平盘", "value": 32},
                {"item": "统计日期", "value": "2026-07-17 15:00:00"},
            ]
        )

    def limit_up_pool(self, date: str) -> pd.DataFrame:
        assert date == "20260717"
        return pd.DataFrame(
            [
                {
                    "代码": "300317",
                    "名称": "珈伟新能",
                    "涨跌幅": 16.01,
                    "成交额": 800_000_000,
                    "连板数": 1,
                    "所属行业": "电力",
                },
                {
                    "代码": "600900",
                    "名称": "长江电力",
                    "涨跌幅": 10.0,
                    "成交额": 500_000_000,
                    "连板数": 3,
                    "所属行业": "电力",
                },
                {
                    "代码": "600036",
                    "名称": "招商银行",
                    "涨跌幅": 10.0,
                    "成交额": 300_000_000,
                    "连板数": 2,
                    "所属行业": "银行",
                },
            ]
        )

    def broken_board_pool(self, date: str) -> pd.DataFrame:
        assert date == "20260717"
        return pd.DataFrame([{"代码": "000001", "所属行业": "银行"}])

    def limit_down_pool(self, date: str) -> pd.DataFrame:
        assert date == "20260717"
        return pd.DataFrame([{"代码": "000002", "所属行业": "房地产开"}])

    def previous_limit_up_pool(self, date: str) -> pd.DataFrame:
        assert date == "20260717"
        return pd.DataFrame([{"代码": f"{index:06d}"} for index in range(4)])

    def etf_spot(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "代码": "159611",
                    "名称": "电力ETF广发",
                    "涨跌幅": 2.18,
                    "成交额": 1_061_168_000,
                    "数据日期": "2026-07-17",
                    "更新时间": "2026-07-17 15:34:57+08:00",
                },
                {
                    "代码": "512800",
                    "名称": "银行ETF",
                    "涨跌幅": 1.2,
                    "成交额": 900_000_000,
                    "数据日期": "2026-07-17",
                    "更新时间": "2026-07-17 15:35:01+08:00",
                },
                {
                    "代码": "515980",
                    "名称": "人工智能ETF",
                    "涨跌幅": -1.0,
                    "成交额": 500_000_000,
                    "数据日期": "2026-07-17",
                    "更新时间": "2026-07-17 15:35:02+08:00",
                },
            ]
        )

    def stock_codes(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"code": "300317", "name": "珈伟新能"},
                {"code": "601939", "name": "建设银行"},
                {"code": "000014", "name": "沙河股份"},
            ]
        )

    def stock_history(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        assert symbol == "300317"
        assert period == "daily"
        assert adjust == "qfq"
        assert start_date < end_date
        return pd.DataFrame(
            [
                {
                    "日期": "2026-07-16",
                    "股票代码": "300317",
                    "开盘": 7.11,
                    "收盘": 7.42,
                    "最高": 7.55,
                    "最低": 7.02,
                    "成交量": 123456,
                    "成交额": 90123456,
                    "涨跌幅": 4.21,
                },
                {
                    "日期": "2026-07-17",
                    "股票代码": "300317",
                    "开盘": 7.45,
                    "收盘": 8.61,
                    "最高": 8.61,
                    "最低": 7.33,
                    "成交量": 234567,
                    "成交额": 188123456,
                    "涨跌幅": 16.04,
                },
            ]
        )

    def stock_daily_sina(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        assert symbol == "sz300317"
        assert adjust == "qfq"
        frame = pd.DataFrame(
            [
                {
                    "date": "2026-07-16",
                    "open": 7.11,
                    "high": 7.55,
                    "low": 7.02,
                    "close": 7.42,
                    "volume": 123456,
                    "amount": 90123456,
                },
                {
                    "date": "2026-07-17",
                    "open": 7.45,
                    "high": 8.61,
                    "low": 7.33,
                    "close": 8.61,
                    "volume": 234567,
                    "amount": 188123456,
                },
            ]
        )
        return frame.set_index("date")


def test_live_provider_derives_market_snapshot_from_public_data() -> None:
    client = FakeAkshareClient()
    now = datetime(2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    payload = provider.get_market_payload()

    assert payload.data_quality == "live-public"
    assert payload.market_status == "已收盘"
    assert payload.metrics.advancers == 405
    assert payload.metrics.decliners == 4758
    assert payload.metrics.limit_up_count == 3
    assert payload.metrics.limit_down_count == 1
    assert payload.metrics.max_board_height == 3
    assert payload.metrics.broken_board_rate == 25.0
    assert payload.metrics.turnover_billion == 1100.0
    assert payload.metrics.turnover_change_pct is None
    assert [sector.name for sector in payload.sectors][:2] == ["电力", "银行"]
    assert "相对抗跌" in payload.sectors[2].core_direction
    assert payload.sectors[0].stocks[0].code == "300317"
    assert payload.sectors[0].etfs[0].code == "159611"
    breadth_source = next(
        source for source in payload.sources if "市场活跃度" in source.name
    )
    assert breadth_source.updated_at == "2026-07-17T15:00:00+08:00"


def test_live_provider_uses_same_source_two_market_turnover_comparison() -> None:
    class ExchangeTurnoverClient(FakeAkshareClient):
        def market_turnover_history(self, trade_date: str) -> pd.DataFrame:
            assert trade_date == "20260717"
            frame = pd.DataFrame(
                [
                    {"date": "2026-07-16", "turnover_billion": 1200.0},
                    {"date": "2026-07-17", "turnover_billion": 1500.0},
                ]
            )
            frame.attrs["source_name"] = "AKShare·沪深交易所成交概况"
            return frame

    provider = AkshareLiveMarketDataProvider(
        client=ExchangeTurnoverClient(),
        clock=lambda: datetime(
            2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai")
        ),
    )

    payload = provider.get_market_payload()

    assert payload.metrics.turnover_billion == 1500.0
    assert payload.metrics.turnover_change_pct == 25.0
    assert any("沪深交易所成交概况" in source.name for source in payload.sources)


def test_live_provider_keeps_snapshot_when_turnover_comparison_is_unavailable() -> None:
    class UnavailableExchangeTurnoverClient(FakeAkshareClient):
        def market_turnover_history(self, trade_date: str) -> pd.DataFrame:
            raise ConnectionError(trade_date)

    provider = AkshareLiveMarketDataProvider(
        client=UnavailableExchangeTurnoverClient(),
        clock=lambda: datetime(
            2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai")
        ),
    )

    payload = provider.get_market_payload()

    assert payload.metrics.turnover_billion == 1100.0
    assert payload.metrics.turnover_change_pct is None


def test_akshare_client_normalizes_exchange_turnover_with_previous_trading_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sse_values = {
        "20260720": 12957.39,
        "20260717": 12478.80,
    }
    szse_values = {
        "20260720": "1,408,238,578,127.89",
        "20260717": "1,409,853,985,720.61",
    }

    def fake_sse(date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [{"单日情况": "成交金额", "股票": sse_values[date]}]
        )

    def fake_szse(date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [{"证券类别": "股票", "成交金额": szse_values[date]}]
        )

    monkeypatch.setattr(
        "app.providers.akshare_live.ak.stock_sse_deal_daily", fake_sse
    )
    monkeypatch.setattr(
        "app.providers.akshare_live.ak.stock_szse_summary", fake_szse
    )

    history = AkshareClient().market_turnover_history("20260720")

    assert history["date"].tolist() == ["2026-07-17", "2026-07-20"]
    assert history["turnover_billion"].tolist() == pytest.approx(
        [26577.3398572061, 27039.7757812789]
    )


def test_live_provider_rejects_snapshot_when_market_breadth_is_incomplete() -> None:
    class IncompleteBreadthClient(FakeAkshareClient):
        def market_breadth(self) -> pd.DataFrame:
            return pd.DataFrame([{"item": "统计日期", "value": "2026-07-17"}])

    client = IncompleteBreadthClient()
    now = datetime(2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    with pytest.raises(MarketDataUnavailable, match="上涨/下跌家数"):
        provider.get_market_payload()


def test_live_provider_uses_ttl_cache() -> None:
    client = FakeAkshareClient()
    now = datetime(2026, 7, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(
        client=client,
        clock=lambda: now,
        cache_ttl_seconds=60,
    )

    first = provider.get_market_payload()
    second = provider.get_market_payload()

    assert first is second
    assert client.industry_calls == 1


def test_live_provider_searches_the_full_stock_catalog() -> None:
    client = FakeAkshareClient()
    now = datetime(2026, 7, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    results = provider.search_stocks("300317")

    assert [(stock.code, stock.name) for stock in results] == [("300317", "珈伟新能")]


def test_stock_catalog_warms_in_background_without_blocking_provider_startup() -> None:
    class ControlledCatalogClient(FakeAkshareClient):
        def __init__(self) -> None:
            super().__init__()
            self.catalog_started = Event()
            self.release_catalog = Event()

        def stock_codes(self) -> pd.DataFrame:
            self.catalog_started.set()
            self.release_catalog.wait(timeout=2)
            return super().stock_codes()

    client = ControlledCatalogClient()
    now = datetime(2026, 7, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    started_at = monotonic()
    provider = AkshareLiveMarketDataProvider(
        client=client,
        clock=lambda: now,
        warm_stock_catalog=True,
    )
    startup_elapsed = monotonic() - started_at

    assert startup_elapsed < 0.2
    assert client.catalog_started.wait(timeout=0.5)
    with pytest.raises(MarketDataUnavailable, match="后台加载"):
        provider.search_stocks("300317")

    client.release_catalog.set()
    deadline = monotonic() + 1
    results = []
    while monotonic() < deadline:
        try:
            results = provider.search_stocks("300317")
        except MarketDataUnavailable:
            sleep(0.01)
            continue
        break

    assert [(stock.code, stock.name) for stock in results] == [("300317", "珈伟新能")]


def test_stock_catalog_uses_persisted_cache_while_background_refresh_fails(
    tmp_path,
) -> None:
    class FailingCatalogClient(FakeAkshareClient):
        def stock_codes(self) -> pd.DataFrame:
            raise TimeoutError("catalog upstream timed out")

    cache_path = tmp_path / "a-share-stock-catalog.json"
    cache_path.write_text(
        json.dumps(
            {
                "updated_at": "2026-07-16T18:00:00+08:00",
                "stocks": [{"code": "000021", "name": "深科技"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    now = datetime(2026, 7, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(
        client=FailingCatalogClient(),
        clock=lambda: now,
        stock_catalog_cache_path=cache_path,
        warm_stock_catalog=True,
    )

    results = provider.search_stocks("000021")
    payload = provider.get_market_payload()

    assert [(stock.code, stock.name) for stock in results] == [("000021", "深科技")]
    assert payload.data_quality == "live-public"


def test_live_provider_normalizes_stock_history() -> None:
    client = FakeAkshareClient()
    now = datetime(2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    history = provider.get_stock_history("300317", limit=20)

    assert history.name == "珈伟新能"
    assert history.source == "AKShare·东方财富A股历史行情"
    assert history.candles[-1].date == "2026-07-17"
    assert history.candles[-1].close == 8.61


def test_live_provider_falls_back_when_primary_history_source_fails() -> None:
    class PrimaryHistoryFailingClient(FakeAkshareClient):
        def stock_history(
            self,
            symbol: str,
            period: str,
            start_date: str,
            end_date: str,
            adjust: str,
        ) -> pd.DataFrame:
            raise ConnectionError("primary source unavailable")

    client = PrimaryHistoryFailingClient()
    now = datetime(2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    history = provider.get_stock_history("300317", limit=20)

    assert history.source == "AKShare·新浪A股历史行情"
    assert history.candles[-1].close == 8.61
    assert history.candles[-1].change_pct == 16.04


def test_live_provider_falls_back_when_primary_history_source_is_empty() -> None:
    class EmptyPrimaryHistoryClient(FakeAkshareClient):
        def stock_history(
            self,
            symbol: str,
            period: str,
            start_date: str,
            end_date: str,
            adjust: str,
        ) -> pd.DataFrame:
            assert symbol == "920088"
            return pd.DataFrame()

        def stock_daily_sina(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            adjust: str,
        ) -> pd.DataFrame:
            assert symbol == "bj920088"
            return super().stock_daily_sina(
                "sz300317", start_date, end_date, adjust
            )

    provider = AkshareLiveMarketDataProvider(
        client=EmptyPrimaryHistoryClient(),
        clock=lambda: datetime(
            2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai")
        ),
    )

    history = provider.get_stock_history("920088", limit=20)

    assert history.code == "920088"
    assert history.source == "AKShare·新浪A股历史行情"
    assert history.candles[-1].close == 8.61


def test_sector_price_history_returns_cached_success_when_public_source_fails() -> None:
    class IntermittentSectorHistoryClient(FakeAkshareClient):
        def __init__(self) -> None:
            super().__init__()
            self.history_calls = 0

        def industry_board_names(self) -> pd.DataFrame:
            return pd.DataFrame([{"板块名称": "电力"}])

        def industry_board_history(
            self, symbol: str, start_date: str, end_date: str
        ) -> pd.DataFrame:
            self.history_calls += 1
            if self.history_calls > 1:
                raise ConnectionError("temporary public source failure")
            return pd.DataFrame(
                [
                    {"日期": "2026-07-17", "收盘": 100.0, "涨跌幅": 1.0},
                    {"日期": "2026-07-20", "收盘": 102.0, "涨跌幅": 2.0},
                ]
            )

    client = IntermittentSectorHistoryClient()
    provider = AkshareLiveMarketDataProvider(
        client=client,
        sector_price_history_cache_ttl_seconds=0,
    )

    first = provider.get_sector_price_history("电力", days=20)
    second = provider.get_sector_price_history("电力", days=20)

    assert first.state == "available"
    assert second.state == "available"
    assert [point.close for point in second.points] == [100.0, 102.0]
    assert "cached" in second.message.casefold()


def test_sector_price_history_returns_explicit_unavailable_instead_of_raising() -> None:
    class FailingSectorHistoryClient(FakeAkshareClient):
        def industry_board_names(self) -> pd.DataFrame:
            raise ConnectionError("public source unavailable")

    provider = AkshareLiveMarketDataProvider(client=FailingSectorHistoryClient())

    history = provider.get_sector_price_history("电力", days=20)

    assert history.state == "unavailable"
    assert history.points == []
    assert "unavailable" in history.message.casefold()


def test_sector_price_history_backfills_20_days_from_ths_with_strength_metrics() -> None:
    class ThsHistoryClient(FakeAkshareClient):
        def industry_board_names(self) -> pd.DataFrame:
            raise ConnectionError("eastmoney catalog unavailable")

        def industry_board_names_ths(self) -> pd.DataFrame:
            return pd.DataFrame([{"name": "电力", "code": "881145"}])

        def industry_board_history_ths(
            self, symbol: str, start_date: str, end_date: str
        ) -> pd.DataFrame:
            assert symbol == "电力"
            dates = pd.date_range("2026-06-01", periods=21, freq="B")
            return pd.DataFrame(
                [
                    {
                        "日期": date,
                        "收盘价": 100.0 + index,
                        "成交量": 1_000.0 * (index + 1),
                        "成交额": 100_000_000.0 * (index + 1),
                    }
                    for index, date in enumerate(dates)
                ]
            )

        def benchmark_history(self) -> pd.DataFrame:
            dates = pd.date_range("2026-06-01", periods=21, freq="B")
            return pd.DataFrame(
                [
                    {"date": date, "close": 100.0 + index * 0.5}
                    for index, date in enumerate(dates)
                ]
            )

    provider = AkshareLiveMarketDataProvider(client=ThsHistoryClient())

    history = provider.get_sector_price_history("电力", days=20)

    assert history.state == "available"
    assert history.source_name == "电力"
    assert "THS" in history.source
    assert len(history.points) == 20
    assert history.points[-1].change_pct == pytest.approx(0.8403, abs=0.0001)
    assert history.points[-1].turnover_billion == pytest.approx(21.0)
    assert history.points[-1].turnover_change_pct == pytest.approx(5.0)
    assert history.points[-1].volume_change_pct == pytest.approx(5.0)
    assert history.points[-1].relative_strength_pct == pytest.approx(9.3591, abs=0.0001)
    assert history.summary is not None
    assert history.summary.period_days == 20
    assert history.summary.period_change_pct == pytest.approx(18.8119, abs=0.0001)
    assert history.summary.trend_5d_pct == pytest.approx(4.3478, abs=0.0001)
    assert history.summary.trend_20d_pct == pytest.approx(18.8119, abs=0.0001)
    assert history.summary.relative_strength_pct == pytest.approx(9.3591, abs=0.0001)
    assert history.summary.benchmark_name == "上证指数"


def test_expired_snapshot_returns_immediately_while_refreshing_in_background() -> None:
    class ControlledRefreshProvider(AkshareLiveMarketDataProvider):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.fetch_count = 0
            self.refresh_started = Event()
            self.release_refresh = Event()
            self.fail_refresh = False

        def _fetch_payload(self):
            self.fetch_count += 1
            if self.fetch_count > 1:
                self.refresh_started.set()
                self.release_refresh.wait(timeout=5)
                if self.fail_refresh:
                    raise ConnectionError("refresh failed")
            return super()._fetch_payload()

    client = FakeAkshareClient()
    now = datetime(2026, 7, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = ControlledRefreshProvider(
        client=client,
        clock=lambda: now,
        cache_ttl_seconds=60,
    )
    first = provider.get_market_payload()
    provider._cache_deadline = monotonic() - 1

    with ThreadPoolExecutor(max_workers=1) as executor:
        request = executor.submit(provider.get_market_payload)
        assert provider.refresh_started.wait(timeout=1)
        try:
            refreshing = request.result(timeout=0.2)
        except TimeoutError:
            provider.release_refresh.set()
            raise

    assert refreshing.as_of == first.as_of
    assert refreshing.data_quality == "refreshing-live-public"

    provider.fail_refresh = True
    provider.release_refresh.set()
    deadline = monotonic() + 2
    while getattr(provider, "_refreshing", True) and monotonic() < deadline:
        sleep(0.01)

    stale = provider.get_market_payload()
    assert stale.as_of == first.as_of
    assert stale.data_quality == "stale-public"


def test_manual_refresh_starts_in_background_without_waiting_for_upstream() -> None:
    class ControlledRefreshProvider(AkshareLiveMarketDataProvider):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.fetch_count = 0
            self.refresh_started = Event()
            self.release_refresh = Event()

        def _fetch_payload(self):
            self.fetch_count += 1
            if self.fetch_count > 1:
                self.refresh_started.set()
                self.release_refresh.wait(timeout=5)
            return super()._fetch_payload()

    provider = ControlledRefreshProvider(
        client=FakeAkshareClient(),
        clock=lambda: datetime(2026, 7, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    first = provider.get_market_payload()

    result = provider.request_market_refresh()

    assert result.state == "started"
    assert result.as_of == first.as_of
    assert provider.refresh_started.wait(timeout=1)
    assert provider.request_market_refresh().state == "already-running"
    provider.release_refresh.set()


def test_sina_industry_summary_keeps_unavailable_fields_explicit() -> None:
    raw = pd.DataFrame(
        [
            {
                "label": "new_dlhy",
                "板块": "电力行业",
                "公司家数": 62,
                "涨跌幅": 1.475,
                "总成交额": 44_585_141_769,
                "股票代码": "sh600236",
                "个股-涨跌幅": 10.052,
                "股票名称": "桂冠电力",
            }
        ]
    )

    normalized = AkshareClient.normalize_industry_summary(raw)

    assert normalized.iloc[0]["板块"] == "电力"
    assert normalized.iloc[0]["总成交额"] == 445.85
    assert normalized.iloc[0]["领涨股"] == "桂冠电力"
    assert pd.isna(normalized.iloc[0]["净流入"])
    assert pd.isna(normalized.iloc[0]["上涨家数"])
    assert pd.isna(normalized.iloc[0]["下跌家数"])


def test_ths_industry_summary_preserves_fund_flow_and_breadth() -> None:
    raw = pd.DataFrame(
        [
            {
                "序号": 1,
                "板块": "电力",
                "涨跌幅": 1.25,
                "总成交量": 8886.73,
                "总成交额": 607.09,
                "净流入": 45.11,
                "上涨家数": 63,
                "下跌家数": 47,
                "均价": 6.83,
                "领涨股": "珈伟新能",
                "领涨股-最新价": 4.13,
                "领涨股-涨跌幅": 16.01,
            }
        ]
    )

    normalized = AkshareClient.normalize_ths_industry_summary(raw)

    assert normalized.iloc[0]["总成交额"] == 607.09
    assert normalized.iloc[0]["净流入"] == 45.11
    assert normalized.iloc[0]["上涨家数"] == 63
    assert normalized.iloc[0]["下跌家数"] == 47


def test_weekend_snapshot_uses_latest_market_statistics_trade_date() -> None:
    client = FakeAkshareClient()
    now = datetime(2026, 7, 19, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    payload = provider.get_market_payload()

    assert payload.market_status == "休市"
    assert payload.as_of == "2026-07-17T15:00:00+08:00"
    assert payload.metrics.limit_up_count == 3


def test_medical_device_etf_mapping_rejects_cross_border_and_generic_medical_names() -> None:
    etfs = pd.DataFrame(
        [
            {
                "代码": "159506",
                "名称": "富国恒生港股通创新药及医疗保健ETF",
                "成交额": 2_000_000_000,
            },
            {
                "代码": "159883",
                "名称": "医疗器械ETF",
                "成交额": 500_000_000,
            },
        ]
    )

    matches = AkshareLiveMarketDataProvider._etfs_for_sector("医疗器械", etfs)

    assert [item.code for item in matches] == ["159883"]


def test_stock_explanations_are_derived_from_board_structure_instead_of_templates() -> None:
    limit_up = pd.DataFrame(
        [
            {
                "代码": "600900",
                "名称": "长江电力",
                "涨跌幅": 10.0,
                "成交额": 500_000_000,
                "连板数": 3,
                "首次封板时间": "093001",
                "炸板次数": 0,
                "换手率": 4.2,
            },
            {
                "代码": "300317",
                "名称": "珈伟新能",
                "涨跌幅": 16.01,
                "成交额": 800_000_000,
                "连板数": 1,
                "首次封板时间": "142000",
                "炸板次数": 2,
                "换手率": 28.6,
            },
        ]
    )

    stocks = AkshareLiveMarketDataProvider._stocks_for_sector(
        name="电力",
        sector_change=3.2,
        leader_name="",
        leader_change=0,
        limit_up=limit_up,
        stock_codes={},
    )

    by_code = {stock.code: stock for stock in stocks}
    assert "3连板" in by_code["600900"].reason
    assert "首板" in by_code["300317"].reason
    assert by_code["600900"].reason != by_code["300317"].reason
    assert "炸板2次" in by_code["300317"].risk


def test_market_snapshot_does_not_block_on_the_full_stock_catalog() -> None:
    class SlowCatalogClient(FakeAkshareClient):
        def stock_codes(self) -> pd.DataFrame:
            raise TimeoutError("full stock catalog is still loading")

    client = SlowCatalogClient()
    now = datetime(2026, 7, 17, 16, 11, tzinfo=ZoneInfo("Asia/Shanghai"))
    provider = AkshareLiveMarketDataProvider(client=client, clock=lambda: now)

    payload = provider.get_market_payload()

    assert payload.data_quality == "live-public"
    assert payload.sectors[0].name == "电力"


def test_sina_industry_snapshot_can_be_enriched_with_fast_fund_flow_table() -> None:
    market = pd.DataFrame(
        [
            {
                "板块": "电力",
                "涨跌幅": 1.48,
                "总成交额": 607.09,
                "净流入": pd.NA,
                "上涨家数": pd.NA,
                "下跌家数": pd.NA,
                "领涨股": "珈伟新能",
                "领涨股-涨跌幅": 16.01,
            },
            {
                "板块": "公路桥梁",
                "涨跌幅": 0.24,
                "总成交额": 55.37,
                "净流入": pd.NA,
                "上涨家数": pd.NA,
                "下跌家数": pd.NA,
                "领涨股": "中原高速",
                "领涨股-涨跌幅": 2.66,
            }
        ]
    )
    funds = pd.DataFrame(
        [
            {
                "行业": "电力",
                "净额": 24.36,
                "领涨股": "珈伟新能",
                "领涨股-涨跌幅": 16.01,
            },
            {
                "行业": "银行",
                "行业-涨跌幅": 0.4,
                "净额": 43.92,
                "领涨股": "建设银行",
                "领涨股-涨跌幅": 3.67,
            },
            {
                "行业": "公路铁路运输",
                "行业-涨跌幅": -0.58,
                "净额": 3.23,
                "领涨股": "中原高速",
                "领涨股-涨跌幅": 2.66,
            }
        ]
    )

    enriched = AkshareClient.merge_industry_fund_flow(market, funds)

    assert enriched.iloc[0]["净流入"] == 24.36
    assert set(enriched["板块"]) == {"电力", "银行", "公路铁路运输"}
    assert enriched.loc[enriched["板块"] == "银行", "净流入"].iloc[0] == 43.92
    road = enriched.loc[enriched["板块"] == "公路铁路运输"].iloc[0]
    assert road["净流入"] == 3.23
    assert road["总成交额"] == 55.37
    assert enriched.attrs["source_name"] == "AKShare·新浪行业行情 + 同花顺行业资金流"


def test_ths_etf_snapshot_is_normalized_without_downloading_all_quote_pages() -> None:
    raw = pd.DataFrame(
        [
            {
                "基金代码": "159611",
                "基金名称": "广发中证全指电力公用事业ETF",
                "增长率": 1.39,
                "最新-交易日": "2026-07-17",
            }
        ]
    )

    normalized = AkshareClient.normalize_ths_etf_spot(raw)

    assert normalized.iloc[0]["代码"] == "159611"
    assert normalized.iloc[0]["名称"] == "广发中证全指电力公用事业ETF"
    assert normalized.iloc[0]["数据日期"] == "2026-07-17"
    assert normalized.iloc[0]["更新时间"] == "2026-07-17 15:00:00+08:00"


def test_reviewed_etf_code_is_ranked_before_unreviewed_name_matches() -> None:
    etfs = pd.DataFrame(
        [
            {"代码": "159046", "名称": "绿色电力ETF", "成交额": 0},
            {"代码": "159611", "名称": "电力ETF广发", "成交额": 0},
        ]
    )

    matches = AkshareLiveMarketDataProvider._etfs_for_sector("电力", etfs)

    assert [item.code for item in matches] == ["159611", "159046"]


def test_sector_summary_marks_missing_turnover_instead_of_reporting_zero() -> None:
    summary = AkshareLiveMarketDataProvider._summary(
        name="银行",
        change=0.4,
        turnover=0,
        flow=43.92,
    )

    assert "成交额数据暂缺" in summary
    assert "成交额0.0亿元" not in summary
