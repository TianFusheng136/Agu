from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timedelta
from pathlib import Path
from threading import Lock, Thread
from time import monotonic
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from app.domain.contracts import MarketFactors, SectorFactors
from app.domain.etf_mapping import EtfCandidate
from app.domain.scoring import calculate_sector_heat
from app.domain.sector_taxonomy import (
    canonical_sector_name,
    classify_sector,
    industry_sector_id,
)
from app.providers.base import (
    MarketDataUnavailable,
    MarketMetrics,
    MarketRefreshResult,
    RawMarketPayload,
    SectorPriceHistory,
    SectorPricePoint,
    SectorPriceSummary,
    SectorRecord,
    SourceReference,
    StockCandle,
    StockHistory,
    StockIdentity,
    StockNewsRecord,
    StockRecord,
)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
TRACKING_INDEX_NOTICE = "以基金管理人最新公告披露为准"
CROSS_BORDER_ETF_MARKERS = ("港股", "港股通", "恒生", "中概", "海外")
ETF_REVIEWED_CODES: dict[str, tuple[str, ...]] = {
    "电力": ("159611",),
    "银行": ("512800",),
    "医疗器械": ("159883",),
}
ETF_ALIASES: dict[str, tuple[str, ...]] = {
    "电力": ("电力", "绿电"),
    "银行": ("银行",),
    "半导体": ("半导体", "芯片"),
    "通信": ("通信", "5G"),
    "计算机": ("计算机", "软件"),
    "港口航运": ("航运", "交通运输"),
    "公路铁路运输": ("交通运输", "物流"),
    "房地产开发": ("房地产", "地产"),
    "证券": ("证券", "券商"),
    "汽车": ("汽车", "智能车"),
    "医疗器械": ("医疗器械", "医疗设备"),
    "化学制药": ("医药", "创新药"),
    "有色金属": ("有色", "金属"),
    "煤炭开采加工": ("煤炭",),
    "油气开采及服务": ("油气", "能源"),
    "国防军工": ("军工",),
    "光伏设备": ("光伏", "新能源"),
}


class AkshareClientProtocol(Protocol):
    def industry_summary(self) -> pd.DataFrame: ...

    def market_breadth(self) -> pd.DataFrame: ...

    def market_turnover_history(self, trade_date: str) -> pd.DataFrame: ...

    def limit_up_pool(self, date: str) -> pd.DataFrame: ...

    def broken_board_pool(self, date: str) -> pd.DataFrame: ...

    def limit_down_pool(self, date: str) -> pd.DataFrame: ...

    def previous_limit_up_pool(self, date: str) -> pd.DataFrame: ...

    def etf_spot(self) -> pd.DataFrame: ...

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame: ...

    def fund_info(self, symbol: str) -> pd.DataFrame: ...

    def stock_codes(self) -> pd.DataFrame: ...

    def stock_news(self, symbol: str) -> pd.DataFrame: ...

    def industry_board_names(self) -> pd.DataFrame: ...

    def industry_board_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame: ...

    def industry_board_names_ths(self) -> pd.DataFrame: ...

    def industry_board_history_ths(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame: ...

    def benchmark_history(self) -> pd.DataFrame: ...

    def stock_history(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame: ...

    def stock_daily_sina(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame: ...


class AkshareClient:
    """Thin boundary around AKShare so parsing can be tested without network access."""

    def industry_summary(self) -> pd.DataFrame:
        frame = self.normalize_industry_summary(
            ak.stock_sector_spot(indicator="新浪行业")
        )
        try:
            return self.merge_industry_fund_flow(
                frame,
                ak.stock_fund_flow_industry(),
            )
        except Exception:
            frame.attrs["source_name"] = "AKShare·新浪行业行情（资金字段暂缺）"
            return frame

    def market_breadth(self) -> pd.DataFrame:
        return ak.stock_market_activity_legu()

    def market_turnover_history(self, trade_date: str) -> pd.DataFrame:
        """Return current and previous trading-day A-share turnover from exchanges."""
        current_date = datetime.strptime(trade_date, "%Y%m%d").date()
        current_turnover = self._exchange_stock_turnover_billion(trade_date)

        previous_date = current_date - timedelta(days=1)
        previous_turnover: float | None = None
        for _ in range(10):
            if previous_date.weekday() < 5:
                candidate = previous_date.strftime("%Y%m%d")
                try:
                    previous_turnover = self._exchange_stock_turnover_billion(candidate)
                except Exception:
                    previous_turnover = None
                if previous_turnover is not None:
                    break
            previous_date -= timedelta(days=1)

        if previous_turnover is None:
            raise ValueError("最近一个交易日的沪深成交额暂不可用")

        frame = pd.DataFrame(
            [
                {
                    "date": previous_date.isoformat(),
                    "turnover_billion": previous_turnover,
                },
                {
                    "date": current_date.isoformat(),
                    "turnover_billion": current_turnover,
                },
            ]
        )
        frame.attrs["source_name"] = "AKShare·沪深交易所成交概况"
        return frame

    @staticmethod
    def _exchange_stock_turnover_billion(date: str) -> float:
        sse = ak.stock_sse_deal_daily(date=date)
        szse = ak.stock_szse_summary(date=date)
        if not {"单日情况", "股票"}.issubset(sse.columns):
            raise ValueError("上交所成交概况字段不完整")
        if not {"证券类别", "成交金额"}.issubset(szse.columns):
            raise ValueError("深交所成交概况字段不完整")

        sse_rows = sse.loc[
            sse["单日情况"].astype(str).str.strip() == "成交金额", "股票"
        ]
        szse_rows = szse.loc[
            szse["证券类别"].astype(str).str.strip() == "股票", "成交金额"
        ]
        if sse_rows.empty or szse_rows.empty:
            raise ValueError("沪深交易所股票成交金额为空")

        sse_yi = _optional_number(str(sse_rows.iloc[0]).replace(",", ""))
        szse_yuan = _optional_number(str(szse_rows.iloc[0]).replace(",", ""))
        if sse_yi is None or sse_yi <= 0 or szse_yuan is None or szse_yuan <= 0:
            raise ValueError("沪深交易所股票成交金额无效")

        # SSE summary uses 亿元; SZSE summary returns raw yuan.
        # The legacy `turnover_billion` contract is displayed as 亿元, so keep 亿元 here.
        return sse_yi + szse_yuan / 100_000_000

    def stock_news(self, symbol: str) -> pd.DataFrame:
        return ak.stock_news_em(symbol=symbol)

    def industry_board_names(self) -> pd.DataFrame:
        return ak.stock_board_industry_name_em()

    def industry_board_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        return ak.stock_board_industry_hist_em(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period="日k",
            adjust="",
        )

    def industry_board_names_ths(self) -> pd.DataFrame:
        return ak.stock_board_industry_name_ths()

    def industry_board_history_ths(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        return ak.stock_board_industry_index_ths(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

    def benchmark_history(self) -> pd.DataFrame:
        return ak.stock_zh_index_daily(symbol="sh000001")

    @staticmethod
    def normalize_industry_summary(frame: pd.DataFrame) -> pd.DataFrame:
        required = {
            "板块",
            "涨跌幅",
            "总成交额",
            "股票名称",
            "个股-涨跌幅",
        }
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(
                "新浪行业行情字段不完整（缺少" + "、".join(sorted(missing)) + "）"
            )
        normalized = pd.DataFrame(
            {
                "板块": frame["板块"]
                .astype(str)
                .str.replace(r"行业$", "", regex=True),
                "涨跌幅": pd.to_numeric(frame["涨跌幅"], errors="coerce"),
                "总成交额": (
                    pd.to_numeric(frame["总成交额"], errors="coerce") / 100_000_000
                ).round(2),
                "净流入": pd.Series(pd.NA, index=frame.index, dtype="Float64"),
                "上涨家数": pd.Series(pd.NA, index=frame.index, dtype="Float64"),
                "下跌家数": pd.Series(pd.NA, index=frame.index, dtype="Float64"),
                "领涨股": frame["股票名称"].astype(str).str.strip(),
                "领涨股-涨跌幅": pd.to_numeric(
                    frame["个股-涨跌幅"], errors="coerce"
                ),
            }
        )
        return normalized.dropna(subset=["板块", "涨跌幅", "总成交额"])

    @staticmethod
    def normalize_ths_industry_summary(frame: pd.DataFrame) -> pd.DataFrame:
        required = {
            "板块",
            "涨跌幅",
            "总成交额",
            "净流入",
            "上涨家数",
            "下跌家数",
            "领涨股",
            "领涨股-涨跌幅",
        }
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(
                "同花顺行业资金行情字段不完整（缺少"
                + "、".join(sorted(missing))
                + "）"
            )
        normalized = pd.DataFrame(
            {
                "板块": frame["板块"].astype(str).str.strip(),
                "涨跌幅": pd.to_numeric(frame["涨跌幅"], errors="coerce"),
                "总成交额": pd.to_numeric(frame["总成交额"], errors="coerce"),
                "净流入": pd.to_numeric(frame["净流入"], errors="coerce"),
                "上涨家数": pd.to_numeric(frame["上涨家数"], errors="coerce"),
                "下跌家数": pd.to_numeric(frame["下跌家数"], errors="coerce"),
                "领涨股": frame["领涨股"].astype(str).str.strip(),
                "领涨股-涨跌幅": pd.to_numeric(
                    frame["领涨股-涨跌幅"], errors="coerce"
                ),
            }
        )
        return normalized.dropna(subset=["板块", "涨跌幅", "总成交额"])

    @staticmethod
    def merge_industry_fund_flow(
        market: pd.DataFrame,
        funds: pd.DataFrame,
    ) -> pd.DataFrame:
        required = {"行业", "净额"}
        missing = required.difference(funds.columns)
        if missing:
            raise ValueError(
                "同花顺行业资金流字段不完整（缺少"
                + "、".join(sorted(missing))
                + "）"
            )
        market_rows = list(market.iterrows())
        used_market_indexes: set[object] = set()
        rows: list[dict[str, object]] = []
        for _, fund in funds.iterrows():
            industry = str(fund["行业"]).strip()
            matched = next(
                (
                    (index, row)
                    for index, row in market_rows
                    if _same_industry(row["板块"], industry)
                ),
                None,
            )
            market_row = matched[1] if matched else None
            if matched:
                used_market_indexes.add(matched[0])
            fund_change = _optional_number(fund.get("行业-涨跌幅"))
            rows.append(
                {
                    "板块": industry,
                    "涨跌幅": (
                        fund_change
                        if fund_change is not None
                        else _number(
                            market_row.get("涨跌幅") if market_row is not None else 0
                        )
                    ),
                    "总成交额": _number(
                        market_row.get("总成交额") if market_row is not None else 0
                    ),
                    "净流入": _optional_number(fund.get("净额")),
                    "上涨家数": (
                        market_row.get("上涨家数")
                        if market_row is not None
                        else pd.NA
                    ),
                    "下跌家数": (
                        market_row.get("下跌家数")
                        if market_row is not None
                        else pd.NA
                    ),
                    "领涨股": str(
                        fund.get(
                            "领涨股",
                            market_row.get("领涨股", "")
                            if market_row is not None
                            else "",
                        )
                    ).strip(),
                    "领涨股-涨跌幅": (
                        _optional_number(fund.get("领涨股-涨跌幅"))
                        or _number(
                            market_row.get("领涨股-涨跌幅")
                            if market_row is not None
                            else 0
                        )
                    ),
                }
            )
        rows.extend(
            row.to_dict()
            for index, row in market_rows
            if index not in used_market_indexes
        )
        enriched = pd.DataFrame(rows, columns=market.columns)
        enriched.attrs["source_name"] = "AKShare·新浪行业行情 + 同花顺行业资金流"
        return enriched

    def limit_up_pool(self, date: str) -> pd.DataFrame:
        return ak.stock_zt_pool_em(date=date)

    def broken_board_pool(self, date: str) -> pd.DataFrame:
        return ak.stock_zt_pool_zbgc_em(date=date)

    def limit_down_pool(self, date: str) -> pd.DataFrame:
        return ak.stock_zt_pool_dtgc_em(date=date)

    def previous_limit_up_pool(self, date: str) -> pd.DataFrame:
        return ak.stock_zt_pool_previous_em(date=date)

    def etf_spot(self) -> pd.DataFrame:
        return self.normalize_ths_etf_spot(ak.fund_etf_spot_ths())

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )

    def fund_info(self, symbol: str) -> pd.DataFrame:
        return ak.fund_info_ths(symbol=symbol)

    @staticmethod
    def normalize_ths_etf_spot(frame: pd.DataFrame) -> pd.DataFrame:
        required = {"基金代码", "基金名称", "增长率", "最新-交易日"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(
                "同花顺ETF行情字段不完整（缺少"
                + "、".join(sorted(missing))
                + "）"
            )
        dates = frame["最新-交易日"].astype(str).str.slice(0, 10)
        normalized = pd.DataFrame(
            {
                "代码": frame["基金代码"].astype(str).str.replace(
                    r"\.0$", "", regex=True
                ).str.zfill(6),
                "名称": frame["基金名称"].astype(str).str.strip(),
                "涨跌幅": pd.to_numeric(frame["增长率"], errors="coerce"),
                "成交额": pd.Series(0.0, index=frame.index),
                "数据日期": dates,
                "更新时间": dates + " 15:00:00+08:00",
            }
        )
        return normalized.dropna(subset=["代码", "名称", "数据日期"])

    def stock_codes(self) -> pd.DataFrame:
        return ak.stock_info_a_code_name()

    def stock_history(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        return ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            timeout=15,
        )

    def stock_daily_sina(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        return ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )


def _number(value: object, default: float = 0.0) -> float:
    result = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(result) else float(result)


def _optional_number(value: object) -> float | None:
    result = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(result) else float(result)


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _ratio(part: float, total: float, default: float = 0.0) -> float:
    return _clamp(part / total * 100) if total > 0 else default


def _normalized(value: object) -> str:
    return re.sub(r"[\s*ＡA]+", "", str(value)).casefold()


def _same_industry(left: object, right: object) -> bool:
    a = _normalized(canonical_sector_name(str(left)))
    b = _normalized(canonical_sector_name(str(right)))
    return bool(a and b and (a.startswith(b) or b.startswith(a)))


def _market_status(now: datetime, latest_data_date: str | None) -> str:
    if latest_data_date and latest_data_date != now.date().isoformat():
        return "休市"
    if now.weekday() >= 5:
        return "休市"
    current = now.time()
    if current < time(9, 15):
        return "未开盘"
    if time(11, 30) < current < time(13, 0):
        return "午间休市"
    if current >= time(15, 0):
        return "已收盘"
    return "交易中"


class AkshareLiveMarketDataProvider:
    def __init__(
        self,
        client: AkshareClientProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
        cache_ttl_seconds: float = 60,
        stock_catalog_cache_path: Path | None = None,
        warm_stock_catalog: bool = False,
        sector_price_history_cache_ttl_seconds: float = 1800,
    ) -> None:
        self._client = client or AkshareClient()
        self._clock = clock or (lambda: datetime.now(SHANGHAI_TZ))
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: RawMarketPayload | None = None
        self._cache_deadline = 0.0
        self._refreshing = False
        self._last_refresh_error: str | None = None
        self._stock_catalog: list[StockIdentity] | None = None
        self._stock_catalog_deadline = 0.0
        self._stock_catalog_cache_path = stock_catalog_cache_path
        self._stock_catalog_refreshing = False
        self._stock_catalog_last_error: str | None = None
        self._sector_price_history_cache_ttl_seconds = (
            sector_price_history_cache_ttl_seconds
        )
        self._sector_price_history_cache: dict[
            tuple[str, int], tuple[float, SectorPriceHistory]
        ] = {}
        self._lock = Lock()
        self._stock_catalog_lock = Lock()
        self._sector_price_history_lock = Lock()
        self._load_persisted_stock_catalog()
        if warm_stock_catalog:
            self._start_stock_catalog_warmup()

    def get_market_payload(self) -> RawMarketPayload:
        now_tick = monotonic()
        if self._cache is not None:
            if now_tick < self._cache_deadline:
                return self._cache_view()
            with self._lock:
                if not self._refreshing:
                    self._refreshing = True
                    self._last_refresh_error = None
                    Thread(
                        target=self._refresh_in_background,
                        name="market-snapshot-refresh",
                        daemon=True,
                    ).start()
            return self._cache_view()

        with self._lock:
            now_tick = monotonic()
            if self._cache is not None:
                return self._cache_view()
            payload = self._fetch_payload()
            self._cache = payload
            self._cache_deadline = now_tick + self._cache_ttl_seconds
            self._last_refresh_error = None
            return payload

    def request_market_refresh(self) -> MarketRefreshResult:
        with self._lock:
            cached = self._cache_view() if self._cache is not None else None
            if self._refreshing:
                return MarketRefreshResult(
                    state="already-running",
                    message="公开行情正在后台刷新。",
                    as_of=cached.as_of if cached else None,
                    data_quality=cached.data_quality if cached else None,
                )
            self._refreshing = True
            self._last_refresh_error = None
            Thread(
                target=self._refresh_in_background,
                name="market-snapshot-manual-refresh",
                daemon=True,
            ).start()
            return MarketRefreshResult(
                state="started",
                message="已发起公开行情后台刷新。",
                as_of=cached.as_of if cached else None,
                data_quality=cached.data_quality if cached else None,
            )

    def _cache_view(self) -> RawMarketPayload:
        if self._cache is None:
            raise MarketDataUnavailable("市场快照尚未完成首次加载")
        if self._last_refresh_error:
            return self._cache.model_copy(update={"data_quality": "stale-public"})
        if self._refreshing:
            return self._cache.model_copy(
                update={"data_quality": "refreshing-live-public"}
            )
        return self._cache

    def _refresh_in_background(self) -> None:
        try:
            payload = self._fetch_payload()
        except Exception as error:
            with self._lock:
                self._last_refresh_error = (
                    f"{type(error).__name__}: {str(error)[:160]}"
                )
                self._cache_deadline = monotonic() + 15
        else:
            with self._lock:
                self._cache = payload
                self._cache_deadline = monotonic() + self._cache_ttl_seconds
                self._last_refresh_error = None
        finally:
            with self._lock:
                self._refreshing = False

    def search_stocks(self, query: str, limit: int = 12) -> list[StockIdentity]:
        normalized = query.strip().casefold()
        if not normalized:
            return []
        catalog = self._get_stock_catalog()
        matches = [
            stock
            for stock in catalog
            if normalized in f"{stock.code} {stock.name}".casefold()
        ]
        matches.sort(
            key=lambda stock: (
                normalized not in {stock.code.casefold(), stock.name.casefold()},
                stock.code,
            )
        )
        return matches[:limit]

    def get_stock_news(self, code: str, limit: int = 5) -> list[StockNewsRecord]:
        try:
            frame = self._client.stock_news(code)
        except Exception as error:
            raise MarketDataUnavailable(
                f"公开个股新闻暂时不可用（{type(error).__name__}）"
            ) from error
        required = {"新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"}
        if frame.empty or not required.issubset(frame.columns):
            return []
        records: list[StockNewsRecord] = []
        for _, row in frame.head(limit).iterrows():
            title = str(row["新闻标题"]).strip()
            url = str(row["新闻链接"]).strip()
            if not title or not url:
                continue
            records.append(
                StockNewsRecord(
                    title=title,
                    summary=" ".join(str(row["新闻内容"]).split())[:220],
                    published_at=str(row["发布时间"]).strip(),
                    source=str(row["文章来源"]).strip() or "公开新闻源",
                    url=url,
                )
            )
        return records

    def get_sector_price_history(
        self, sector_name: str, days: int = 20
    ) -> SectorPriceHistory:
        cache_key = (_normalized(sector_name), days)
        with self._sector_price_history_lock:
            cached = self._sector_price_history_cache.get(cache_key)
        if cached is not None and monotonic() < cached[0]:
            return cached[1]
        target = _normalized(sector_name)
        now = self._clock().astimezone(SHANGHAI_TZ)
        start = now.date() - timedelta(days=max(days * 3, 30))
        source_name: str | None = None
        source = "AKShare public industry board history"
        frame: pd.DataFrame | None = None
        source_errors: list[str] = []
        source_candidates = (
            (
                "industry_board_names",
                "板块名称",
                "industry_board_history",
                "AKShare/Eastmoney industry board history",
            ),
            (
                "industry_board_names_ths",
                "name",
                "industry_board_history_ths",
                "AKShare/THS industry board history",
            ),
        )
        for catalog_method, name_column, history_method, source_label in source_candidates:
            try:
                board_frame = getattr(self._client, catalog_method)()
            except Exception as error:
                source_errors.append(f"{source_label}: {type(error).__name__}")
                continue
            if board_frame.empty or name_column not in board_frame.columns:
                source_errors.append(f"{source_label}: unusable catalog")
                continue
            matched_name = next(
                (
                    str(item).strip()
                    for item in board_frame[name_column].dropna().tolist()
                    if _normalized(str(item)) == target
                ),
                None,
            )
            if matched_name is None:
                source_errors.append(f"{source_label}: no exact name match")
                continue
            try:
                candidate = getattr(self._client, history_method)(
                    matched_name,
                    start.strftime("%Y%m%d"),
                    now.strftime("%Y%m%d"),
                )
            except Exception as error:
                source_errors.append(f"{source_label}: {type(error).__name__}")
                continue
            if candidate.empty:
                source_errors.append(f"{source_label}: empty history")
                continue
            source_name = matched_name
            source = source_label
            frame = candidate
            break
        if frame is None or source_name is None:
            return self._sector_price_history_failure(
                cache_key,
                sector_name,
                source_name,
                "Public sector price history unavailable ("
                + "; ".join(source_errors)
                + ").",
            )

        def find_column(candidates: tuple[str, ...]) -> str | None:
            return next((column for column in candidates if column in frame.columns), None)

        date_column = find_column(("日期", "date"))
        close_column = find_column(("收盘", "收盘价", "close"))
        change_column = find_column(("涨跌幅", "change_pct"))
        volume_column = find_column(("成交量", "volume"))
        turnover_column = find_column(("成交额", "amount"))
        if date_column is None or close_column is None:
            return SectorPriceHistory(
                state="unavailable",
                requested_name=sector_name,
                source_name=source_name,
                source=source,
                message="The matched source board returned no usable historical candles.",
                points=[],
            )

        rows: list[dict[str, float | str | None]] = []
        for _, row in frame.iterrows():
            close = _optional_number(row.get(close_column))
            date = pd.to_datetime(row.get(date_column), errors="coerce")
            if close is None or close <= 0 or pd.isna(date):
                continue
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "close": close,
                    "change_pct": (
                        _optional_number(row.get(change_column))
                        if change_column is not None
                        else None
                    ),
                    "volume": (
                        _optional_number(row.get(volume_column))
                        if volume_column is not None
                        else None
                    ),
                    "turnover": (
                        _optional_number(row.get(turnover_column))
                        if turnover_column is not None
                        else None
                    ),
                }
            )
        rows = sorted(rows, key=lambda item: str(item["date"]))
        if not rows:
            return SectorPriceHistory(
                state="unavailable",
                requested_name=sector_name,
                source_name=source_name,
                source=source,
                message="The matched source board had no valid historical close values.",
                points=[],
            )

        points: list[SectorPricePoint] = []
        for index, row in enumerate(rows):
            previous = rows[index - 1] if index > 0 else None
            close = float(row["close"])
            previous_close = float(previous["close"]) if previous else None
            volume = row["volume"]
            previous_volume = previous["volume"] if previous else None
            turnover = row["turnover"]
            previous_turnover = previous["turnover"] if previous else None
            change_pct = row["change_pct"]
            if change_pct is None and previous_close:
                change_pct = (close / previous_close - 1) * 100
            turnover_change_pct = (
                (float(turnover) / float(previous_turnover) - 1) * 100
                if turnover is not None
                and previous_turnover is not None
                and float(previous_turnover) > 0
                else None
            )
            volume_change_pct = (
                (float(volume) / float(previous_volume) - 1) * 100
                if volume is not None
                and previous_volume is not None
                and float(previous_volume) > 0
                else None
            )
            points.append(
                SectorPricePoint(
                    date=str(row["date"]),
                    close=close,
                    change_pct=change_pct,
                    turnover_billion=(
                        float(turnover) / 100_000_000
                        if turnover is not None and float(turnover) >= 0
                        else None
                    ),
                    turnover_change_pct=turnover_change_pct,
                    volume_change_pct=volume_change_pct,
                )
            )

        points = points[-days:]
        benchmark_name = "上证指数"
        try:
            benchmark_frame = self._client.benchmark_history()
            benchmark_dates = pd.to_datetime(
                benchmark_frame.get("date"), errors="coerce"
            )
            benchmark_closes = pd.to_numeric(
                benchmark_frame.get("close"), errors="coerce"
            )
            benchmark_by_date = {
                date.date().isoformat(): float(close)
                for date, close in zip(benchmark_dates, benchmark_closes, strict=False)
                if not pd.isna(date) and not pd.isna(close) and float(close) > 0
            }
            first_benchmark = benchmark_by_date.get(points[0].date)
            first_sector = points[0].close
            if first_benchmark is not None:
                points = [
                    point.model_copy(
                        update={
                            "relative_strength_pct": (
                                (point.close / first_sector - 1) * 100
                                - (
                                    benchmark_by_date[point.date] / first_benchmark - 1
                                )
                                * 100
                                if point.date in benchmark_by_date
                                else None
                            )
                        }
                    )
                    for point in points
                ]
        except Exception:
            pass

        latest = points[-1]
        period_change = (
            (latest.close / points[0].close - 1) * 100 if len(points) >= 2 else None
        )
        trend_5d = (
            (latest.close / points[-6].close - 1) * 100
            if len(points) >= 6
            else None
        )
        trend_20d = period_change if len(points) >= 20 else None
        summary = SectorPriceSummary(
            period_days=len(points),
            period_change_pct=period_change,
            latest_turnover_billion=latest.turnover_billion,
            turnover_change_pct=latest.turnover_change_pct,
            volume_change_pct=latest.volume_change_pct,
            trend_5d_pct=trend_5d,
            trend_20d_pct=trend_20d,
            relative_strength_pct=latest.relative_strength_pct,
            benchmark_name=benchmark_name,
        )
        result = SectorPriceHistory(
            state="available",
            requested_name=sector_name,
            source_name=source_name,
            source=source,
            message=(
                f"Exact source-board match. Backfilled {len(points)} real trading days; "
                "this does not reconstruct historical heat or capital flow."
            ),
            summary=summary,
            points=points,
        )
        with self._sector_price_history_lock:
            self._sector_price_history_cache[cache_key] = (
                monotonic() + self._sector_price_history_cache_ttl_seconds,
                result,
            )
        return result

    def _sector_price_history_failure(
        self,
        cache_key: tuple[str, int],
        sector_name: str,
        source_name: str | None,
        message: str,
    ) -> SectorPriceHistory:
        with self._sector_price_history_lock:
            cached = self._sector_price_history_cache.get(cache_key)
        if cached is not None and cached[1].state == "available":
            return cached[1].model_copy(
                update={
                    "message": (
                        f"{message} Showing the last successful cached public history."
                    )
                }
            )
        return SectorPriceHistory(
            state="unavailable",
            requested_name=sector_name,
            source_name=source_name,
            source="AKShare/Eastmoney industry board history",
            message=message,
            points=[],
        )

    def get_etf_research(self, code: str, days: int = 120) -> dict[str, object]:
        if not re.fullmatch(r"\d{6}", code):
            raise MarketDataUnavailable("ETF code must be six digits.")
        try:
            spot = self._client.etf_spot()
        except Exception as error:
            raise MarketDataUnavailable(
                f"Public ETF quote unavailable ({type(error).__name__})."
            ) from error
        matches = spot[spot["代码"].astype(str).str.zfill(6) == code]
        if matches.empty:
            raise MarketDataUnavailable("Public ETF quote did not contain this code.")
        row = matches.iloc[0]
        now = self._clock().astimezone(SHANGHAI_TZ)
        start = now.date() - timedelta(days=max(days * 2, 180))
        try:
            frame = self._client.etf_history(
                code, start.strftime("%Y%m%d"), now.strftime("%Y%m%d")
            )
        except Exception as error:
            raise MarketDataUnavailable(
                f"Public ETF price history unavailable ({type(error).__name__})."
            ) from error
        date_column = "\u65e5\u671f"
        close_column = "\u6536\u76d8"
        change_column = "\u6da8\u8dcc\u5e45"
        points: list[dict[str, object]] = []
        if not frame.empty and {date_column, close_column}.issubset(frame.columns):
            for _, candle in frame.iterrows():
                close = _optional_number(candle.get(close_column))
                date = pd.to_datetime(candle.get(date_column), errors="coerce")
                if close is None or close <= 0 or pd.isna(date):
                    continue
                points.append(
                    {
                        "date": date.date().isoformat(),
                        "close": close,
                        "change_pct": _optional_number(candle.get(change_column)),
                    }
                )
        if not points:
            raise MarketDataUnavailable("Public ETF history returned no valid close values.")
        fund_profile = self._etf_fund_profile(code, now)
        return {
            "code": code,
            "name": str(row["名称"]).strip(),
            "as_of": str(row["更新时间"]).strip(),
            "change_pct": _optional_number(row.get("涨跌幅")),
            "source": "AKShare/Eastmoney ETF history",
            "points": points[-days:],
            "fund_profile": fund_profile,
        }

    def _etf_fund_profile(self, code: str, now: datetime) -> dict[str, object]:
        source = "AKShare/THS fund profile"
        retrieved_at = now.isoformat(timespec="seconds")
        try:
            frame = self._client.fund_info(code)
            required = {"字段", "值"}
            if not required.issubset(frame.columns):
                raise ValueError("fund profile columns are incomplete")
            facts = {
                str(row["字段"]).strip(): str(row["值"]).strip()
                for _, row in frame.iterrows()
                if str(row["字段"]).strip() and str(row["值"]).strip()
            }
            return {
                "state": "available",
                "full_name": facts.get("基金全称"),
                "benchmark": facts.get("业绩比较基准"),
                "manager": facts.get("基金管理人"),
                "share_scale": facts.get("份额规模"),
                "source": source,
                "retrieved_at": retrieved_at,
                "message": "Public fund facts returned; benchmark is not constituent verification.",
            }
        except Exception as error:
            return {
                "state": "unavailable",
                "full_name": None,
                "benchmark": None,
                "manager": None,
                "share_scale": None,
                "source": source,
                "retrieved_at": retrieved_at,
                "message": f"Public fund profile unavailable ({type(error).__name__}).",
            }

    def get_stock_history(
        self,
        code: str,
        period: Literal["daily", "weekly", "monthly"] = "daily",
        adjust: Literal["", "qfq", "hfq"] = "qfq",
        limit: int = 120,
    ) -> StockHistory:
        now = self._clock().astimezone(SHANGHAI_TZ)
        span_days = {
            "daily": max(limit * 2, 180),
            "weekly": max(limit * 10, 900),
            "monthly": max(limit * 40, 3600),
        }[period]
        start = now.date() - timedelta(days=span_days)
        source = "AKShare·东方财富A股历史行情"
        primary_error: Exception | None = None
        try:
            frame = self._client.stock_history(
                symbol=code,
                period=period,
                start_date=start.strftime("%Y%m%d"),
                end_date=now.strftime("%Y%m%d"),
                adjust=adjust,
            )
        except Exception as error:
            primary_error = error
            frame = pd.DataFrame()
        if frame.empty:
            primary_error = primary_error or ValueError("primary history returned empty")
            try:
                frame = self._client.stock_daily_sina(
                    symbol=self._market_symbol(code),
                    start_date=start.strftime("%Y%m%d"),
                    end_date=now.strftime("%Y%m%d"),
                    adjust=adjust,
                )
                frame = self._resample_history(frame, period)
                source = "AKShare·新浪A股历史行情"
            except Exception as fallback_error:
                raise MarketDataUnavailable(
                    f"股票 {code} K线公开行情暂时不可用"
                    f"（{type(primary_error).__name__}；"
                    f"{type(fallback_error).__name__}）"
                ) from fallback_error
        if frame.empty:
            raise MarketDataUnavailable(f"股票 {code} 暂无可用K线数据")

        columns = (
            {
                "date": "日期",
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
                "change_pct": "涨跌幅",
            }
            if "日期" in frame.columns
            else {
                "date": "date",
                "open": "open",
                "close": "close",
                "high": "high",
                "low": "low",
                "volume": "volume",
                "amount": "amount",
                "change_pct": "change_pct",
            }
        )
        required = {
            columns["date"],
            columns["open"],
            columns["close"],
            columns["high"],
            columns["low"],
            columns["volume"],
            columns["amount"],
        }
        missing = required.difference(frame.columns)
        if missing:
            raise MarketDataUnavailable(
                "K线公开行情字段不完整（缺少" + "、".join(sorted(missing)) + "）"
            )

        candles: list[StockCandle] = []
        previous_close: float | None = None
        for _, row in frame.tail(limit).iterrows():
            close = _number(row[columns["close"]])
            raw_change = (
                _number(row[columns["change_pct"]])
                if columns["change_pct"] in frame.columns
                else None
            )
            change_pct = (
                raw_change
                if raw_change is not None
                else (
                    round((close / previous_close - 1) * 100, 2)
                    if previous_close
                    else None
                )
            )
            candles.append(
                StockCandle(
                    date=str(row[columns["date"]])[:10],
                    open=_number(row[columns["open"]]),
                    high=_number(row[columns["high"]]),
                    low=_number(row[columns["low"]]),
                    close=close,
                    volume=max(0, _number(row[columns["volume"]])),
                    amount=max(0, _number(row[columns["amount"]])),
                    change_pct=change_pct,
                )
            )
            previous_close = close
        name = next(
            (stock.name for stock in self.search_stocks(code, 1) if stock.code == code),
            f"A股 {code}",
        )
        return StockHistory(
            code=code,
            name=name,
            period=period,
            adjust=adjust,
            as_of=candles[-1].date,
            data_quality="live-public",
            source=source,
            candles=candles,
        )

    @staticmethod
    def _market_symbol(code: str) -> str:
        if code.startswith("6"):
            return f"sh{code}"
        if code.startswith(("4", "8", "92")):
            return f"bj{code}"
        return f"sz{code}"

    @staticmethod
    def _resample_history(
        frame: pd.DataFrame,
        period: Literal["daily", "weekly", "monthly"],
    ) -> pd.DataFrame:
        normalized = frame.copy()
        if "date" not in normalized.columns:
            normalized = normalized.reset_index()
            if "date" not in normalized.columns:
                normalized = normalized.rename(
                    columns={normalized.columns[0]: "date"}
                )
        if period == "daily":
            return normalized
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"]).set_index("date")
        rule = "W-FRI" if period == "weekly" else "ME"
        aggregated = normalized.resample(rule).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
            }
        )
        return aggregated.dropna(subset=["open", "close"]).reset_index()

    def _get_stock_catalog(self) -> list[StockIdentity]:
        now_tick = monotonic()
        if (
            self._stock_catalog is not None
            and now_tick < self._stock_catalog_deadline
        ):
            return self._stock_catalog
        if self._stock_catalog is not None:
            self._start_stock_catalog_warmup()
            return self._stock_catalog
        with self._stock_catalog_lock:
            if self._stock_catalog is not None:
                return self._stock_catalog
            if self._stock_catalog_refreshing:
                raise MarketDataUnavailable(
                    "A股代码表正在后台加载，请稍后重试"
                )
            self._stock_catalog_refreshing = True
        try:
            catalog = self._fetch_stock_catalog()
        except Exception as error:
            with self._stock_catalog_lock:
                self._stock_catalog_last_error = (
                    f"{type(error).__name__}: {str(error)[:160]}"
                )
            if isinstance(error, MarketDataUnavailable):
                raise
            raise MarketDataUnavailable(
                f"A股代码表暂时不可用（{type(error).__name__}）"
            ) from error
        else:
            self._store_stock_catalog(catalog)
        finally:
            with self._stock_catalog_lock:
                self._stock_catalog_refreshing = False
        return catalog

    def _start_stock_catalog_warmup(self) -> None:
        with self._stock_catalog_lock:
            if self._stock_catalog_refreshing:
                return
            self._stock_catalog_refreshing = True
            self._stock_catalog_last_error = None
        Thread(
            target=self._refresh_stock_catalog_in_background,
            name="a-share-stock-catalog-warmup",
            daemon=True,
        ).start()

    def _refresh_stock_catalog_in_background(self) -> None:
        try:
            catalog = self._fetch_stock_catalog()
        except Exception as error:
            with self._stock_catalog_lock:
                self._stock_catalog_last_error = (
                    f"{type(error).__name__}: {str(error)[:160]}"
                )
        else:
            self._store_stock_catalog(catalog)
        finally:
            with self._stock_catalog_lock:
                self._stock_catalog_refreshing = False

    def _fetch_stock_catalog(self) -> list[StockIdentity]:
        try:
            frame = self._client.stock_codes()
        except Exception as error:
            raise MarketDataUnavailable(
                f"A股代码表暂时不可用（{type(error).__name__}）"
            ) from error
        if frame.empty or not {"code", "name"}.issubset(frame.columns):
            raise MarketDataUnavailable("A股代码表为空或字段不完整")
        catalog = [
            StockIdentity(code=str(row["code"]).zfill(6), name=str(row["name"]).strip())
            for _, row in frame.iterrows()
            if re.fullmatch(r"\d{1,6}", str(row["code"]).strip())
        ]
        if not catalog:
            raise MarketDataUnavailable("A股代码表没有可用记录")
        return catalog

    def _store_stock_catalog(self, catalog: list[StockIdentity]) -> None:
        with self._stock_catalog_lock:
            self._stock_catalog = catalog
            self._stock_catalog_deadline = monotonic() + max(
                self._cache_ttl_seconds, 3600
            )
            self._stock_catalog_last_error = None
        self._persist_stock_catalog(catalog)

    def _load_persisted_stock_catalog(self) -> None:
        path = self._stock_catalog_cache_path
        if path is None or not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("stocks", [])
            catalog = [
                StockIdentity(code=str(row["code"]).zfill(6), name=str(row["name"]))
                for row in rows
                if re.fullmatch(r"\d{1,6}", str(row.get("code", "")).strip())
                and str(row.get("name", "")).strip()
            ]
        except (OSError, TypeError, ValueError, KeyError):
            return
        if catalog:
            self._stock_catalog = catalog

    def _persist_stock_catalog(self, catalog: list[StockIdentity]) -> None:
        path = self._stock_catalog_cache_path
        if path is None:
            return
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        payload = {
            "updated_at": self._clock().astimezone(SHANGHAI_TZ).isoformat(),
            "stocks": [
                {"code": stock.code, "name": stock.name}
                for stock in catalog
            ],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)

    def _fetch_payload(self) -> RawMarketPayload:
        now = self._clock().astimezone(SHANGHAI_TZ)
        try:
            breadth = self._client.market_breadth()
        except Exception as error:
            raise MarketDataUnavailable(
                f"市场上涨/下跌家数公开数据暂时不可用（{type(error).__name__}）"
            ) from error
        trade_date = self._trade_date_from_breadth(breadth, now)
        jobs = {
            "industries": self._client.industry_summary,
            "limit_up": lambda: self._client.limit_up_pool(trade_date),
            "broken": lambda: self._client.broken_board_pool(trade_date),
            "limit_down": lambda: self._client.limit_down_pool(trade_date),
            "previous": lambda: self._client.previous_limit_up_pool(trade_date),
            "etfs": self._client.etf_spot,
        }
        optional_jobs: set[str] = set()
        turnover_job = getattr(self._client, "market_turnover_history", None)
        if callable(turnover_job):
            jobs["market_turnover"] = lambda: turnover_job(trade_date)
            optional_jobs.add("market_turnover")
        frames: dict[str, pd.DataFrame] = {
            "breadth": breadth,
            "market_turnover": pd.DataFrame(),
            "stocks": pd.DataFrame(
                [
                    {"code": stock.code, "name": stock.name}
                    for stock in (self._stock_catalog or [])
                ],
                columns=["code", "name"],
            ),
        }
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            futures = {executor.submit(job): name for name, job in jobs.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    frames[name] = future.result()
                except Exception as error:  # upstream libraries expose heterogeneous errors
                    if name not in optional_jobs:
                        errors.append(f"{name}: {type(error).__name__}")

        if errors:
            raise MarketDataUnavailable(
                "公开行情源暂时不可用，请稍后刷新（" + "；".join(sorted(errors)) + "）"
            )
        if frames["industries"].empty:
            raise MarketDataUnavailable("公开行情源返回了空的行业行情快照")

        _, etf_at = self._freshness(frames["etfs"], now)
        breadth_at = self._breadth_updated_at(frames["breadth"], etf_at)
        latest_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        latest_at = breadth_at
        metrics, market_factors = self._market_metrics(frames)
        sectors = self._sectors(frames)
        if not sectors:
            raise MarketDataUnavailable("公开行情数据不足，无法生成热点板块")

        sources = [
            SourceReference(
                name=frames["industries"].attrs.get(
                    "source_name", "AKShare·行业资金与行情"
                ),
                category="sector",
                updated_at=latest_at,
            ),
            SourceReference(
                name="AKShare·东方财富涨跌停股池",
                category="market",
                updated_at=latest_at,
            ),
            SourceReference(
                name="AKShare·乐咕乐股市场活跃度",
                category="market",
                updated_at=breadth_at,
            ),
            SourceReference(
                name="AKShare·同花顺ETF行情",
                category="etf",
                updated_at=etf_at,
            ),
        ]
        if not frames["market_turnover"].empty:
            sources.append(
                SourceReference(
                    name=frames["market_turnover"].attrs.get(
                        "source_name", "AKShare·沪深交易所成交概况"
                    ),
                    category="market",
                    updated_at=latest_at,
                )
            )

        return RawMarketPayload(
            as_of=latest_at,
            data_quality="live-public",
            market_status=_market_status(now, latest_date),
            market_factors=market_factors,
            metrics=metrics,
            sectors=sectors,
            sources=sources,
        )

    @staticmethod
    def _trade_date_from_breadth(breadth: pd.DataFrame, now: datetime) -> str:
        if {"item", "value"}.issubset(breadth.columns):
            rows = breadth.loc[
                breadth["item"].astype(str).str.strip() == "统计日期", "value"
            ]
            if not rows.empty:
                parsed = pd.to_datetime(rows.iloc[0], errors="coerce")
                if not pd.isna(parsed):
                    return parsed.strftime("%Y%m%d")
        fallback = now.date()
        while fallback.weekday() >= 5:
            fallback -= timedelta(days=1)
        return fallback.strftime("%Y%m%d")

    @staticmethod
    def _freshness(etfs: pd.DataFrame, now: datetime) -> tuple[str | None, str]:
        latest_date: str | None = None
        latest = now
        if "数据日期" in etfs:
            dates = etfs["数据日期"].dropna().astype(str)
            if not dates.empty:
                latest_date = max(dates)
        if "更新时间" in etfs:
            timestamps = pd.to_datetime(etfs["更新时间"], errors="coerce", utc=True).dropna()
            if not timestamps.empty:
                latest = timestamps.max().to_pydatetime().astimezone(SHANGHAI_TZ)
        return latest_date, latest.isoformat(timespec="seconds")

    @staticmethod
    def _breadth_updated_at(breadth: pd.DataFrame, fallback: str) -> str:
        if not {"item", "value"}.issubset(breadth.columns):
            return fallback
        rows = breadth.loc[breadth["item"].astype(str).str.strip() == "统计日期", "value"]
        if rows.empty:
            return fallback
        parsed = pd.to_datetime(rows.iloc[0], errors="coerce")
        if pd.isna(parsed):
            return fallback
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize(SHANGHAI_TZ)
        else:
            parsed = parsed.tz_convert(SHANGHAI_TZ)
        return parsed.isoformat(timespec="seconds")

    @staticmethod
    def _market_metrics(
        frames: dict[str, pd.DataFrame],
    ) -> tuple[MarketMetrics, MarketFactors]:
        industries = frames["industries"]
        breadth = frames["breadth"]
        limit_up = frames["limit_up"]
        broken = frames["broken"]
        limit_down = frames["limit_down"]
        previous = frames["previous"]

        if breadth.empty or not {"item", "value"}.issubset(breadth.columns):
            raise MarketDataUnavailable("市场上涨/下跌家数数据为空或字段不完整")
        breadth_items = {
            str(row["item"]).strip(): row["value"] for _, row in breadth.iterrows()
        }
        advancers_value = _optional_number(breadth_items.get("上涨"))
        decliners_value = _optional_number(breadth_items.get("下跌"))
        if advancers_value is None or decliners_value is None:
            raise MarketDataUnavailable("市场上涨/下跌家数数据缺失")
        advancers = int(advancers_value)
        decliners = int(decliners_value)
        limit_up_count = len(limit_up)
        limit_down_count = len(limit_down)
        broken_count = len(broken)
        max_board = (
            int(max((_number(value) for value in limit_up["连板数"]), default=0))
            if "连板数" in limit_up
            else 0
        )
        turnover = round(sum(_number(value) for value in industries["总成交额"]), 1)
        turnover_change_pct: float | None = None
        turnover_history = frames.get("market_turnover", pd.DataFrame())
        if {"date", "turnover_billion"}.issubset(turnover_history.columns):
            normalized_turnover = turnover_history.assign(
                date=pd.to_datetime(turnover_history["date"], errors="coerce"),
                turnover_billion=pd.to_numeric(
                    turnover_history["turnover_billion"], errors="coerce"
                ),
            ).dropna(subset=["date", "turnover_billion"])
            normalized_turnover = normalized_turnover.loc[
                normalized_turnover["turnover_billion"] > 0
            ].sort_values("date")
            if len(normalized_turnover) >= 2:
                previous_turnover = float(
                    normalized_turnover.iloc[-2]["turnover_billion"]
                )
                current_turnover = float(
                    normalized_turnover.iloc[-1]["turnover_billion"]
                )
                turnover = round(current_turnover, 1)
                turnover_change_pct = round(
                    (current_turnover / previous_turnover - 1) * 100,
                    1,
                )
        industry_counts = Counter(str(value) for value in limit_up.get("所属行业", []))
        concentrated = sum(count for _, count in industry_counts.most_common(3))
        concentration = _ratio(concentrated, limit_up_count)
        promotion_count = (
            sum(_number(value) >= 2 for value in limit_up["连板数"])
            if "连板数" in limit_up
            else 0
        )
        median_change = float(
            pd.to_numeric(industries["涨跌幅"], errors="coerce").dropna().median()
        )
        seal_rate = _ratio(limit_up_count, limit_up_count + broken_count)

        metrics = MarketMetrics(
            advancers=advancers,
            decliners=decliners,
            limit_up_count=limit_up_count,
            limit_down_count=limit_down_count,
            max_board_height=max_board,
            broken_board_rate=round(100 - seal_rate, 1),
            turnover_billion=turnover,
            turnover_change_pct=turnover_change_pct,
            hotspot_concentration=concentration,
            northbound_status="当前公开数据源未提供实时北向净流入",
        )
        factors = MarketFactors(
            breadth=_ratio(
                advancers,
                advancers + decliners,
            ),
            limit_balance=_ratio(
                limit_up_count, limit_up_count + limit_down_count, 50
            ),
            promotion_rate=_ratio(promotion_count, len(previous), 50),
            seal_rate=seal_rate,
            turnover_change=50,
            leader_strength=_clamp(max_board * 20),
            concentration=concentration,
            median_return=_clamp(50 + median_change * 10),
        )
        return metrics, factors

    def _sectors(self, frames: dict[str, pd.DataFrame]) -> list[SectorRecord]:
        industries = frames["industries"]
        limit_up = frames["limit_up"]
        etfs = frames["etfs"]
        stock_codes = {
            _normalized(row["name"]): str(row["code"]).zfill(6)
            for _, row in frames["stocks"].iterrows()
        }
        changes = pd.to_numeric(industries["涨跌幅"], errors="coerce")
        median_change = _number(changes.median())
        flow_values = [
            value
            for value in (
                _optional_number(item)
                for item in industries.get("净流入", pd.Series(dtype=float))
            )
            if value is not None
        ]
        max_abs_flow = max((abs(value) for value in flow_values), default=1)
        max_turnover = max(
            (_number(value) for value in industries["总成交额"]),
            default=1,
        )
        has_cross_source_mapping = "同花顺行业资金流" in str(
            industries.attrs.get("source_name", "")
        )

        records: list[SectorRecord] = []
        for _, row in industries.iterrows():
            name = str(row["板块"]).strip()
            classification = classify_sector(
                name,
                has_cross_source_mapping=has_cross_source_mapping,
            )
            change = _number(row["涨跌幅"])
            turnover = _number(row["总成交额"])
            capital_flow = _optional_number(row.get("净流入"))
            advancers = _optional_number(row.get("上涨家数"))
            decliners = _optional_number(row.get("下跌家数"))
            members = (advancers or 0) + (decliners or 0)
            sector_limit_up = limit_up[
                limit_up.get("所属行业", pd.Series(dtype=str)).map(
                    lambda value, industry_name=name: _same_industry(
                        value, industry_name
                    )
                )
            ]
            limit_count = len(sector_limit_up)
            leader_change = _number(row.get("领涨股-涨跌幅", 0))
            max_board = (
                max((_number(value) for value in sector_limit_up["连板数"]), default=0)
                if "连板数" in sector_limit_up
                else 0
            )
            factors = SectorFactors(
                breadth=_ratio(advancers or 0, members, 50),
                turnover_acceleration=_clamp(35 + turnover / max_turnover * 45),
                relative_strength=_clamp(50 + (change - median_change) * 12),
                limit_density=_clamp(limit_count / max(members, 1) * 500),
                leader_strength=_clamp(45 + leader_change * 2 + max_board * 8),
                capital_flow=(
                    _clamp(50 + capital_flow / max_abs_flow * 45)
                    if capital_flow is not None
                    else 50
                ),
                catalyst_strength=_clamp(40 + limit_count * 12),
                previous_heat=50,
            )
            records.append(
                SectorRecord(
                    id=self._sector_id(name),
                    name=name,
                    summary=self._summary(name, change, turnover, capital_flow),
                    core_direction=(
                        f"{name}行业及其领涨分支"
                        if change >= 0
                        else f"{name}相对抗跌观察（板块当日仍下跌）"
                    ),
                    change_pct=round(change, 2),
                    turnover_billion=round(turnover, 2),
                    capital_flow_billion=(
                        round(capital_flow, 2)
                        if capital_flow is not None
                        else None
                    ),
                    classification=classification,
                    factors=factors,
                    catalysts=[
                        f"公开行情显示领涨股为{str(row.get('领涨股', '暂无')).strip()}"
                    ],
                    risks=self._risks(change, factors.breadth),
                    stocks=self._stocks_for_sector(
                        name=name,
                        sector_change=change,
                        leader_name=str(row.get("领涨股", "")).strip(),
                        leader_change=leader_change,
                        limit_up=sector_limit_up,
                        stock_codes=stock_codes,
                    ),
                    etfs=self._etfs_for_sector(name, etfs),
                )
            )

        records = [record for record in records if record.name not in {"综合"}]
        positive = sorted(
            (record for record in records if record.change_pct >= 0),
            key=lambda record: (
                -calculate_sector_heat(record.factors).score,
                -record.change_pct,
                record.id,
            ),
        )
        defensive = sorted(
            (record for record in records if record.change_pct < 0),
            key=lambda record: (
                -record.change_pct,
                -calculate_sector_heat(record.factors).score,
                record.id,
            ),
        )
        return (positive + defensive)[:3]

    @staticmethod
    def _sector_id(name: str) -> str:
        return industry_sector_id(name)

    @staticmethod
    def _summary(
        name: str,
        change: float,
        turnover: float,
        flow: float | None,
    ) -> str:
        turnover_text = (
            f"成交额{turnover:.1f}亿元" if turnover > 0 else "成交额数据暂缺"
        )
        if flow is None:
            return (
                f"{name}今日涨跌幅{change:+.2f}%，{turnover_text}，"
                "资金净流入数据源暂缺。"
            )
        flow_word = "净流入" if flow >= 0 else "净流出"
        return (
            f"{name}今日涨跌幅{change:+.2f}%，{turnover_text}，"
            f"板块资金{flow_word}{abs(flow):.1f}亿元。"
        )

    @staticmethod
    def _risks(change: float, breadth: float) -> list[str]:
        if change >= 4:
            return ["短线涨幅较大，需观察次日分歧与成交承接"]
        if breadth < 45:
            return ["板块上涨家数不足，内部表现存在分化"]
        return ["热点轮动较快，需持续核对资金与板块宽度"]

    @staticmethod
    def _stocks_for_sector(
        name: str,
        sector_change: float,
        leader_name: str,
        leader_change: float,
        limit_up: pd.DataFrame,
        stock_codes: dict[str, str],
    ) -> list[StockRecord]:
        stocks: list[StockRecord] = []
        seen: set[str] = set()

        def add(
            code: str,
            stock_name: str,
            change: float,
            status: str,
            evidence: pd.Series | None = None,
        ) -> None:
            if not re.fullmatch(r"\d{6}", code) or code in seen:
                return
            seen.add(code)
            relative = "强于板块" if change > sector_change else "弱于板块"
            reason, risk, structure_status = (
                AkshareLiveMarketDataProvider._stock_explanation(
                    name=name,
                    change=change,
                    sector_change=sector_change,
                    evidence=evidence,
                )
            )
            stocks.append(
                StockRecord(
                    code=code,
                    name=stock_name,
                    direction=name,
                    change_pct=round(change, 2),
                    relative_performance=relative,
                    capital_status=structure_status or status,
                    reason=reason,
                    risk=risk,
                )
            )

        if not limit_up.empty:
            sorted_pool = limit_up.sort_values(
                by=["涨跌幅", "成交额"], ascending=False
            )
            for _, stock in sorted_pool.head(3).iterrows():
                add(
                    str(stock["代码"]).zfill(6),
                    str(stock["名称"]).strip(),
                    _number(stock["涨跌幅"]),
                    "涨停股池",
                    stock,
                )

        leader_code = stock_codes.get(_normalized(leader_name), "")
        add(leader_code, leader_name, leader_change, "板块领涨")
        return stocks[:3]

    @staticmethod
    def _stock_explanation(
        name: str,
        change: float,
        sector_change: float,
        evidence: pd.Series | None,
    ) -> tuple[str, str, str | None]:
        relative_gap = change - sector_change
        if evidence is None:
            return (
                f"{name}板块领涨代表，当日涨幅{change:+.2f}%，"
                f"较板块高{relative_gap:+.2f}个百分点",
                "当前仅有板块相对表现证据，个股催化与资金明细仍需核对",
                None,
            )

        board_count = max(1, int(_number(evidence.get("连板数"), 1)))
        board_label = "首板" if board_count == 1 else f"{board_count}连板"
        first_seal = str(evidence.get("首次封板时间", "")).strip().zfill(6)
        seal_text = ""
        if re.fullmatch(r"\d{6}", first_seal):
            seal_text = f"，首次封板{first_seal[:2]}:{first_seal[2:4]}"
        amount_billion = _number(evidence.get("成交额")) / 100_000_000
        turnover = _optional_number(evidence.get("换手率"))
        broken = max(0, int(_number(evidence.get("炸板次数"), 0)))
        reason = (
            f"{name}方向{board_label}{seal_text}，成交额{amount_billion:.1f}亿元；"
            f"当日涨幅较板块高{relative_gap:+.2f}个百分点"
        )
        if broken:
            risk = f"盘中炸板{broken}次，封板稳定性与次日承接仍需观察"
        elif turnover is not None and turnover >= 25:
            risk = f"换手率{turnover:.1f}%，短线分歧与波动可能放大"
        elif board_count >= 3:
            risk = f"已处于{board_label}高度，需观察高位分歧与成交承接"
        else:
            risk = "涨停结构只能说明当日强度，不能替代后续催化与成交验证"
        return reason, risk, board_label

    @staticmethod
    def _etfs_for_sector(name: str, etfs: pd.DataFrame) -> list[EtfCandidate]:
        aliases = ETF_ALIASES.get(name, (name,))
        reviewed_codes = set(ETF_REVIEWED_CODES.get(name, ()))
        candidates: list[tuple[bool, float, EtfCandidate]] = []
        for _, row in etfs.iterrows():
            etf_name = str(row.get("名称", "")).strip()
            normalized_name = _normalized(etf_name)
            if any(
                _normalized(marker) in normalized_name
                for marker in CROSS_BORDER_ETF_MARKERS
            ):
                continue
            matched = next(
                (alias for alias in aliases if _normalized(alias) in normalized_name),
                None,
            )
            if not matched:
                continue
            exact = _normalized(name) in _normalized(etf_name)
            code = str(row.get("代码", "")).zfill(6)
            if not re.fullmatch(r"\d{6}", code):
                continue
            reviewed = code in reviewed_codes
            candidates.append(
                (
                    not reviewed,
                    _number(row.get("成交额")),
                    EtfCandidate(
                        code=code,
                        name=etf_name,
                        coverage_direction=f"ETF名称与“{matched}”方向匹配",
                        tracking_index=TRACKING_INDEX_NOTICE,
                        constituent_overlap=0,
                        index_theme_match=95 if exact else 75,
                        chain_match=70 if exact else 55,
                        alias_match=100 if exact else 80,
                        freshness=100,
                        review_status=100 if reviewed else 40,
                    ),
                )
            )
        candidates.sort(key=lambda item: (item[0], -item[1], item[2].code))
        return [candidate for _, _, candidate in candidates[:2]]
