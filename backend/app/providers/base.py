from typing import Literal, Protocol

from pydantic import Field

from app.domain.contracts import FrozenModel, MarketFactors, SectorFactors
from app.domain.etf_mapping import EtfCandidate
from app.domain.sector_taxonomy import SectorClassification


class MarketDataUnavailable(RuntimeError):
    """Raised when public market sources cannot produce a trustworthy snapshot."""


class SourceReference(FrozenModel):
    name: str
    category: str
    updated_at: str


class MarketRefreshResult(FrozenModel):
    state: Literal["started", "already-running", "not-supported"]
    message: str
    as_of: str | None = None
    data_quality: str | None = None


class MarketMetrics(FrozenModel):
    advancers: int | None = Field(default=None, ge=0)
    decliners: int | None = Field(default=None, ge=0)
    limit_up_count: int = Field(ge=0)
    limit_down_count: int = Field(ge=0)
    max_board_height: int = Field(ge=0)
    broken_board_rate: float = Field(ge=0, le=100)
    turnover_billion: float = Field(ge=0)
    turnover_change_pct: float | None = None
    hotspot_concentration: float = Field(ge=0, le=100)
    northbound_status: str


class StockRecord(FrozenModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str
    direction: str
    change_pct: float
    relative_performance: str
    capital_status: str
    reason: str
    risk: str


class StockIdentity(FrozenModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str


class StockNewsRecord(FrozenModel):
    title: str
    summary: str
    published_at: str
    source: str
    url: str


class StockCandle(FrozenModel):
    date: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    amount: float = Field(ge=0)
    change_pct: float | None = None


class StockHistory(FrozenModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str
    period: Literal["daily", "weekly", "monthly"]
    adjust: Literal["", "qfq", "hfq"]
    as_of: str
    data_quality: str
    source: str
    candles: list[StockCandle]


class SectorPricePoint(FrozenModel):
    date: str
    close: float = Field(gt=0)
    change_pct: float | None = None
    turnover_billion: float | None = Field(default=None, ge=0)
    turnover_change_pct: float | None = None
    volume_change_pct: float | None = None
    relative_strength_pct: float | None = None


class SectorPriceSummary(FrozenModel):
    period_days: int = Field(ge=1)
    period_change_pct: float | None = None
    latest_turnover_billion: float | None = Field(default=None, ge=0)
    turnover_change_pct: float | None = None
    volume_change_pct: float | None = None
    trend_5d_pct: float | None = None
    trend_20d_pct: float | None = None
    relative_strength_pct: float | None = None
    benchmark_name: str = "上证指数"


class SectorPriceHistory(FrozenModel):
    state: Literal["available", "unavailable"]
    requested_name: str
    source_name: str | None = None
    source: str
    message: str
    summary: SectorPriceSummary | None = None
    points: list[SectorPricePoint]


class SectorRecord(FrozenModel):
    id: str
    name: str
    summary: str
    core_direction: str
    change_pct: float
    turnover_billion: float = Field(ge=0)
    capital_flow_billion: float | None
    classification: SectorClassification | None = None
    factors: SectorFactors
    catalysts: list[str]
    risks: list[str]
    stocks: list[StockRecord]
    etfs: list[EtfCandidate]


class RawMarketPayload(FrozenModel):
    as_of: str
    data_quality: str
    market_status: str = "演示"
    market_factors: MarketFactors
    metrics: MarketMetrics
    sectors: list[SectorRecord]
    sources: list[SourceReference]


class MarketDataProvider(Protocol):
    def get_market_payload(self) -> RawMarketPayload:
        """Return a normalized market snapshot."""

    def request_market_refresh(self) -> MarketRefreshResult:
        """Start a non-blocking refresh when the provider supports it."""

    def search_stocks(self, query: str, limit: int = 12) -> list[StockIdentity]:
        """Search the full A-share stock catalog."""

    def get_stock_news(self, code: str, limit: int = 5) -> list[StockNewsRecord]:
        """Return recent public news evidence for an individual stock."""

    def get_stock_history(
        self,
        code: str,
        period: Literal["daily", "weekly", "monthly"] = "daily",
        adjust: Literal["", "qfq", "hfq"] = "qfq",
        limit: int = 120,
    ) -> StockHistory:
        """Return normalized stock candles."""
