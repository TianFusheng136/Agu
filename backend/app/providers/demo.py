import math
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from app.providers.base import (
    MarketRefreshResult,
    RawMarketPayload,
    StockCandle,
    StockHistory,
    StockIdentity,
    StockNewsRecord,
)


class DemoMarketDataProvider:
    """Offline provider used to validate the product flow without live credentials."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or Path(__file__).with_name("demo_data.json")

    def get_market_payload(self) -> RawMarketPayload:
        return RawMarketPayload.model_validate_json(self._data_path.read_text(encoding="utf-8"))

    def request_market_refresh(self) -> MarketRefreshResult:
        return MarketRefreshResult(
            state="not-supported",
            message="演示数据不支持公开行情刷新。",
            data_quality="demo",
        )

    def search_stocks(self, query: str, limit: int = 12) -> list[StockIdentity]:
        normalized = query.strip().casefold()
        stocks: dict[str, StockIdentity] = {}
        for sector in self.get_market_payload().sectors:
            for stock in sector.stocks:
                stocks[stock.code] = StockIdentity(code=stock.code, name=stock.name)
        matches = [
            stock
            for stock in stocks.values()
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
        del code, limit
        return []

    def get_stock_history(
        self,
        code: str,
        period: Literal["daily", "weekly", "monthly"] = "daily",
        adjust: Literal["", "qfq", "hfq"] = "qfq",
        limit: int = 120,
    ) -> StockHistory:
        identity = next(
            (stock for stock in self.search_stocks(code) if stock.code == code),
            StockIdentity(code=code, name=f"A股 {code}"),
        )
        step = {"daily": 1, "weekly": 7, "monthly": 30}[period]
        end = date.fromisoformat(self.get_market_payload().as_of[:10])
        base = 12 + (sum(int(digit) for digit in code) % 18)
        candles: list[StockCandle] = []
        previous_close = float(base)
        for index in range(limit):
            current_date = end - timedelta(days=(limit - index - 1) * step)
            trend = index * 0.035
            wave = math.sin(index / 4.5) * 0.65
            close = max(1.0, base + trend + wave)
            open_price = max(1.0, previous_close + math.sin(index * 1.7) * 0.24)
            high = max(open_price, close) + 0.32 + abs(math.sin(index)) * 0.18
            low = max(0.1, min(open_price, close) - 0.28 - abs(math.cos(index)) * 0.16)
            change_pct = (close / previous_close - 1) * 100 if previous_close else None
            candles.append(
                StockCandle(
                    date=current_date.isoformat(),
                    open=round(open_price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=round(550_000 + index * 8_000 + abs(wave) * 300_000, 0),
                    amount=round(close * (550_000 + index * 8_000), 0),
                    change_pct=round(change_pct, 2) if change_pct is not None else None,
                )
            )
            previous_close = close
        return StockHistory(
            code=code,
            name=identity.name,
            period=period,
            adjust=adjust,
            as_of=candles[-1].date,
            data_quality="demo",
            source="演示K线",
            candles=candles,
        )
