from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.contracts import FrozenModel, MarketSentiment, SectorFactors, SectorHeat
from app.domain.etf_mapping import EtfMappingResult, rank_etfs
from app.domain.scoring import calculate_market_sentiment, calculate_sector_heat
from app.domain.sector_taxonomy import SectorClassification, classify_sector, is_generic_sector
from app.domain.technical import TechnicalSignalStats, analyze_technical_signals
from app.providers.base import (
    MarketDataProvider,
    MarketMetrics,
    MarketRefreshResult,
    SectorPriceHistory,
    SourceReference,
    StockHistory,
    StockIdentity,
    StockNewsRecord,
    StockRecord,
)
from app.services.llm_analysis import LlmNotConfigured, generate_evidence_explanation
from app.services.llm_config import get_llm_runtime_configuration
from app.services.research_cache import (
    InMemoryResearchCacheStore,
    ResearchCacheStore,
)
from app.services.sector_history import (
    InMemorySectorSnapshotStore,
    SectorRotationPoint,
    SectorSnapshotStore,
)

RESEARCH_DISCLAIMER = "本产品仅提供市场研究信息，不构成任何投资建议或收益承诺。"


class SectorOverview(FrozenModel):
    id: str
    name: str
    summary: str
    core_direction: str
    change_pct: float
    turnover_billion: float = Field(ge=0)
    capital_flow_billion: float | None
    capital_flow_label: str = "行业资金净额（非主力净流入）"
    classification: SectorClassification
    heat: SectorHeat
    factors: SectorFactors
    catalysts: list[str]
    risks: list[str]
    stocks: list[StockRecord]
    etfs: list[EtfMappingResult]


class MarketOverview(FrozenModel):
    as_of: str
    data_quality: str
    market_status: str
    sentiment: MarketSentiment
    metrics: MarketMetrics
    hot_sectors: list[SectorOverview]
    sources: list[SourceReference]
    disclaimer: str = RESEARCH_DISCLAIMER


class DataFieldStatus(FrozenModel):
    field: str
    state: Literal["available", "unavailable"]
    message: str


class MarketDataStatus(FrozenModel):
    as_of: str
    data_quality: str
    sources: list[SourceReference]
    fields: list[DataFieldStatus]


class MarketSignalBucket(FrozenModel):
    id: Literal[
        "macd_golden_cross",
        "macd_death_cross",
        "kdj_golden_cross",
        "kdj_death_cross",
        "weekly_volume_anomaly",
    ]
    label: str
    count: int = Field(ge=0)


class MarketSignalItem(FrozenModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str
    sector: str
    change_pct: float
    as_of: str
    source: str
    sample_size: int = Field(ge=0)
    macd_state: str
    kdj_state: str
    weekly_state: str
    data_state: Literal["live", "cached"] = "live"
    cached_at: str | None = None


class MarketSignalScan(FrozenModel):
    state: Literal["available", "unavailable"]
    as_of: str
    scope: Literal["current-hot-sector-representatives"]
    scope_note: str
    scanned_count: int = Field(ge=0)
    cached_count: int = Field(default=0, ge=0)
    query_failures: list[str]
    buckets: list[MarketSignalBucket]
    items: list[MarketSignalItem]
    disclaimer: str = "Technical signals describe historical price and volume structures only."


class SectorRotation(FrozenModel):
    sector_id: str
    sector_name: str
    classification: SectorClassification
    capital_flow_label: str = "行业资金净额（非主力净流入）"
    status: Literal["collecting", "ready"]
    minimum_required_points: int = 5
    data_points: int
    window_days: int
    basis: Literal["source-price-history", "live-snapshot"] = "live-snapshot"
    source: str = "Local daily live snapshots"
    basis_note: str = "Comprehensive heat snapshots recorded on each real trading day."
    snapshot_data_points: int = 0
    points: list[SectorRotationPoint]


class RotationSnapshotCollection(FrozenModel):
    """Result of recording one real-provider sector rotation sample."""

    state: Literal["recorded"]
    as_of: str
    sectors_recorded: int
    message: str


class StockResearchSnapshot(FrozenModel):
    history: StockHistory
    technical: TechnicalSignalStats


class SectorNewsEvidence(FrozenModel):
    code: str
    name: str
    title: str
    summary: str
    published_at: str
    source: str
    url: str
    data_state: Literal["live", "cached"] = "live"
    cached_at: str | None = None


class SectorEvidence(FrozenModel):
    sector_id: str
    sector_name: str
    state: Literal["available", "unavailable"]
    message: str
    representative_stocks: list[StockIdentity]
    query_failures: list[str]
    cached_count: int = Field(default=0, ge=0)
    news: list[SectorNewsEvidence]


class LlmAnalysisStatus(FrozenModel):
    state: Literal["configured", "not-configured"]
    provider: str
    model: str | None
    message: str


class LlmBriefMarketMetrics(FrozenModel):
    advancers: int | None
    decliners: int | None
    limit_up_count: int
    limit_down_count: int
    broken_board_rate: float
    turnover_billion: float
    turnover_change_pct: float | None
    hotspot_concentration: float


class LlmBriefRotationFacts(FrozenModel):
    state: Literal["available", "unavailable"]
    source: str | None = None
    period_days: int = 0
    trend_5d_pct: float | None = None
    trend_20d_pct: float | None = None
    relative_strength_pct: float | None = None
    trading_amount_change_pct: float | None = None
    volume_change_pct: float | None = None
    benchmark_name: str | None = None


class LlmBriefNewsEvidence(FrozenModel):
    title: str
    published_at: str
    source: str
    linked_stock: str


class LlmBriefDirection(FrozenModel):
    name: str
    stage: str
    change_pct: float
    heat_score: float
    capital_flow_billion: float | None
    capital_flow_label: str = "行业资金净额（非主力净流入）"
    risks: list[str]
    representative_stock_available: bool
    representative_stocks: list[str]
    rotation: LlmBriefRotationFacts
    news: list[LlmBriefNewsEvidence]


class LlmBriefTechnicalSignals(FrozenModel):
    state: Literal["available", "unavailable"]
    scope_note: str
    scanned_count: int
    cached_count: int
    buckets: dict[str, int]
    highlights: list[str]
    query_failures: list[str]


class LlmBriefFacts(FrozenModel):
    """The exact structured facts made available to the LLM for this brief."""

    as_of: str
    market_status: str
    market_sentiment: str
    market_metrics: LlmBriefMarketMetrics
    directions: list[LlmBriefDirection]
    technical_signals: LlmBriefTechnicalSignals
    data_gaps: list[str]


class LlmBriefSections(FrozenModel):
    market_conclusion: str
    evidence: list[str]
    risks: list[str]
    data_gaps: list[str]


class LlmMarketBrief(FrozenModel):
    state: Literal["generated", "not-configured", "unavailable"]
    analysis: str | None
    message: str
    as_of: str | None
    sections: LlmBriefSections | None = None
    facts: LlmBriefFacts | None = None


class EtfPricePoint(FrozenModel):
    date: str
    close: float = Field(gt=0)
    change_pct: float | None = None


class EtfPriceHistory(FrozenModel):
    source: str
    points: list[EtfPricePoint]


class EtfFundProfile(FrozenModel):
    """Public fund facts. This is not a constituent or tracking-index assertion."""

    state: Literal["available", "unavailable"]
    full_name: str | None = None
    benchmark: str | None = None
    manager: str | None = None
    share_scale: str | None = None
    source: str
    retrieved_at: str
    message: str


class EtfResearch(FrozenModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str
    as_of: str
    change_pct: float | None = None
    price_history: EtfPriceHistory
    sector_mappings: list[EtfMappingResult]
    fund_profile: EtfFundProfile | None = None


class MarketRadarService:
    def __init__(
        self,
        provider: MarketDataProvider,
        history_store: SectorSnapshotStore | None = None,
        research_cache: ResearchCacheStore | None = None,
    ) -> None:
        self._provider = provider
        self._history_store = history_store or InMemorySectorSnapshotStore()
        self._research_cache = research_cache or InMemoryResearchCacheStore()
        self._last_sectors_by_id: dict[str, SectorOverview] = {}

    def get_overview(self) -> MarketOverview:
        payload = self._provider.get_market_payload()
        sectors = [
            SectorOverview(
                id=sector.id,
                name=sector.name,
                summary=sector.summary,
                core_direction=sector.core_direction,
                change_pct=sector.change_pct,
                turnover_billion=sector.turnover_billion,
                capital_flow_billion=sector.capital_flow_billion,
                classification=sector.classification
                or classify_sector(
                    sector.name,
                    has_cross_source_mapping=sector.capital_flow_billion is not None,
                ),
                heat=calculate_sector_heat(sector.factors),
                factors=sector.factors,
                catalysts=sector.catalysts,
                risks=sector.risks,
                stocks=sector.stocks,
                etfs=rank_etfs(sector.name, sector.etfs),
            )
            for sector in payload.sectors
            if not is_generic_sector(sector.name)
        ]
        sectors.sort(key=lambda sector: (-sector.heat.score, sector.id))
        overview = MarketOverview(
            as_of=payload.as_of,
            data_quality=payload.data_quality,
            market_status=payload.market_status,
            sentiment=calculate_market_sentiment(payload.market_factors),
            metrics=payload.metrics,
            hot_sectors=sectors,
            sources=payload.sources,
        )
        # Keep recently rendered sectors addressable when an upstream refresh
        # changes the top-three ranking between a user's click and detail load.
        self._last_sectors_by_id.update(
            {sector.id: sector for sector in overview.hot_sectors}
        )
        self._record_snapshot(overview)
        return overview

    def request_market_refresh(self) -> MarketRefreshResult:
        return self._provider.request_market_refresh()

    def get_data_status(self) -> MarketDataStatus:
        overview = self.get_overview()
        metrics = overview.metrics
        northbound_unavailable = any(
            marker in metrics.northbound_status.casefold()
            for marker in ("unavailable", "not available", "暂", "未")
        )
        field_values = [
            (
                "advancers_decliners",
                metrics.advancers is not None and metrics.decliners is not None,
            ),
            ("turnover_change", metrics.turnover_change_pct is not None),
            ("northbound", not northbound_unavailable),
            (
                "sector_capital_flow",
                any(item.capital_flow_billion is not None for item in overview.hot_sectors),
            ),
        ]
        return MarketDataStatus(
            as_of=overview.as_of,
            data_quality=overview.data_quality,
            sources=overview.sources,
            fields=[
                DataFieldStatus(
                    field=field,
                    state="available" if available else "unavailable",
                    message=(
                        "Present in the current public-market snapshot."
                        if available
                        else "Not supplied by the current public-market source."
                    ),
                )
                for field, available in field_values
            ],
        )

    def get_market_signals(self) -> MarketSignalScan:
        """Aggregate deterministic signals for current hot-sector representatives.

        The scan deliberately covers a small, visible scope (at most two
        representatives from each current top sector), rather than claiming
        to be a full-market screener.
        """

        overview = self.get_overview()
        candidates: list[tuple[StockRecord, str]] = []
        seen_codes: set[str] = set()
        for sector in overview.hot_sectors[:3]:
            for stock in sector.stocks[:2]:
                if stock.code not in seen_codes:
                    candidates.append((stock, sector.name))
                    seen_codes.add(stock.code)
        if not candidates:
            return MarketSignalScan(
                state="unavailable",
                as_of=overview.as_of,
                scope="current-hot-sector-representatives",
                scope_note=(
                    "No representative stocks are available in the current "
                    "hot-sector snapshot."
                ),
                scanned_count=0,
                cached_count=0,
                query_failures=[],
                buckets=self._signal_buckets([]),
                items=[],
            )

        items_by_code: dict[str, MarketSignalItem] = {}
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=min(len(candidates), 4)) as executor:
            futures = {
                executor.submit(
                    self._load_signal_item,
                    stock,
                    sector_name,
                ): (stock, sector_name)
                for stock, sector_name in candidates
            }
            for future in as_completed(futures):
                stock, sector_name = futures[future]
                try:
                    item, failure = future.result()
                except Exception as error:
                    failures.append(f"{stock.code}:{type(error).__name__}")
                    continue
                if failure:
                    failures.append(failure)
                if item is not None:
                    items_by_code[stock.code] = item
        items = [
            items_by_code[stock.code]
            for stock, _ in candidates
            if stock.code in items_by_code
        ]
        return MarketSignalScan(
            state="available" if items else "unavailable",
            as_of=overview.as_of,
            scope="current-hot-sector-representatives",
            scope_note=(
                "Up to two representative stocks from each of the current top "
                "three hot sectors; not a full-market screen."
            ),
            scanned_count=len(items),
            cached_count=sum(item.data_state == "cached" for item in items),
            query_failures=failures,
            buckets=self._signal_buckets(items),
            items=items,
        )

    def _load_signal_item(
        self,
        stock: StockRecord,
        sector_name: str,
    ) -> tuple[MarketSignalItem | None, str | None]:
        """Retry once, then explicitly reuse the last successful result."""

        last_error: Exception | None = None
        for _ in range(2):
            try:
                history = self._provider.get_stock_history(
                    stock.code,
                    "daily",
                    "qfq",
                    250,
                )
                technical = analyze_technical_signals(history.candles)
                item = MarketSignalItem(
                    code=stock.code,
                    name=stock.name,
                    sector=sector_name,
                    change_pct=stock.change_pct,
                    as_of=history.as_of,
                    source=history.source,
                    sample_size=technical.sample_size,
                    macd_state=technical.macd.state,
                    kdj_state=technical.kdj.state,
                    weekly_state=technical.weekly.state,
                )
            except Exception as error:
                last_error = error
                continue

            cached_at = datetime.now().astimezone().isoformat(timespec="seconds")
            self._research_cache.put_signal(
                stock.code,
                item.model_dump(mode="json"),
                cached_at,
            )
            return item, None

        failure = f"{stock.code}:{type(last_error).__name__}"
        cached = self._research_cache.get_signal(stock.code)
        if cached is None:
            return None, failure

        raw_item, cached_at = cached
        try:
            cached_item = MarketSignalItem.model_validate(raw_item)
        except ValueError:
            return None, failure
        return (
            cached_item.model_copy(
                update={
                    "name": stock.name,
                    "sector": sector_name,
                    "change_pct": stock.change_pct,
                    "data_state": "cached",
                    "cached_at": cached_at,
                }
            ),
            failure,
        )

    @staticmethod
    def _signal_buckets(items: list[MarketSignalItem]) -> list[MarketSignalBucket]:
        checks = [
            ("macd_golden_cross", "MACD golden cross", "macd_state", "MACD金叉"),
            ("macd_death_cross", "MACD death cross", "macd_state", "MACD死叉"),
            ("kdj_golden_cross", "KDJ golden cross", "kdj_state", "KDJ金叉"),
            ("kdj_death_cross", "KDJ death cross", "kdj_state", "KDJ死叉"),
            ("weekly_volume_anomaly", "Weekly volume anomaly", "weekly_state", "周线放量异动"),
        ]
        return [
            MarketSignalBucket(
                id=bucket_id,
                label=label,
                count=sum(getattr(item, field_name) == expected for item in items),
            )
            for bucket_id, label, field_name, expected in checks
        ]

    def collect_rotation_snapshot(self) -> RotationSnapshotCollection:
        """Persist one daily snapshot from the provider without manufacturing history.

        The store de-duplicates by sector and trading date, therefore repeated
        scheduled calls only replace that day's live-derived sample.
        """

        overview = self.get_overview()
        return RotationSnapshotCollection(
            state="recorded",
            as_of=overview.as_of,
            sectors_recorded=len(overview.hot_sectors),
            message="已记录本次公开行情板块样本；同一交易日会覆盖为最新一次真实样本。",
        )

    def get_sector_detail(self, sector_id: str) -> SectorOverview | None:
        overview = self.get_overview()
        sector = next((item for item in overview.hot_sectors if item.id == sector_id), None)
        return sector or self._last_sectors_by_id.get(sector_id)

    def get_sector_rotation(self, sector_id: str, days: int = 20) -> SectorRotation | None:
        overview = self.get_overview()
        sector = next((item for item in overview.hot_sectors if item.id == sector_id), None)
        sector = sector or self._last_sectors_by_id.get(sector_id)
        if sector is None:
            return None
        snapshot_points = self._history_store.list_sector(sector_id, days)
        history = self.get_sector_price_history(sector_id, days)
        if history is not None and history.state == "available" and len(history.points) >= 5:
            closes = [point.close for point in history.points]
            low = min(closes)
            high = max(closes)
            spread = high - low
            points = [
                SectorRotationPoint(
                    sector_id=sector.id,
                    sector_name=sector.name,
                    as_of=point.date,
                    rank=None,
                    heat_score=None,
                    change_pct=point.change_pct or 0.0,
                    capital_flow_billion=None,
                    classification=sector.classification,
                    basis="source-price-history",
                    strength_score=(
                        50.0 if spread == 0 else round((point.close - low) / spread * 100, 2)
                    ),
                    relative_strength_pct=point.relative_strength_pct,
                    turnover_change_pct=point.turnover_change_pct,
                    volume_change_pct=point.volume_change_pct,
                )
                for point in history.points
            ]
            return SectorRotation(
                sector_id=sector.id,
                sector_name=sector.name,
                classification=sector.classification,
                status="ready",
                data_points=len(points),
                window_days=days,
                basis="source-price-history",
                source=history.source,
                basis_note=(
                    "价格强弱分数仅按该板块20日收盘价区间归一化；"
                    "不补造历史综合热度、排名或资金流。"
                ),
                snapshot_data_points=len(snapshot_points),
                points=points,
            )
        return SectorRotation(
            sector_id=sector.id,
            sector_name=sector.name,
            classification=sector.classification,
            status="ready" if len(snapshot_points) >= 5 else "collecting",
            data_points=len(snapshot_points),
            window_days=days,
            basis="live-snapshot",
            source="Local daily live snapshots",
            basis_note="只包含系统在真实交易日实际记录的综合热度快照。",
            snapshot_data_points=len(snapshot_points),
            points=snapshot_points,
        )

    def get_sector_price_history(
        self, sector_id: str, days: int = 20
    ) -> SectorPriceHistory | None:
        sector = self.get_sector_detail(sector_id)
        if sector is None:
            return None
        getter = getattr(self._provider, "get_sector_price_history", None)
        if not callable(getter):
            return SectorPriceHistory(
                state="unavailable",
                requested_name=sector.name,
                source_name=None,
                source="unavailable",
                message="The active provider does not expose source-labeled sector history.",
                points=[],
            )
        return SectorPriceHistory.model_validate(getter(sector.name, days))

    def get_etf_research(self, code: str, days: int = 120) -> EtfResearch | None:
        getter = getattr(self._provider, "get_etf_research", None)
        if not callable(getter):
            return None
        raw = getter(code, days)
        price_history = EtfPriceHistory.model_validate(
            {"source": raw["source"], "points": raw["points"]}
        )
        overview = self.get_overview()
        mappings = [
            etf
            for sector in overview.hot_sectors
            for etf in sector.etfs
            if etf.code == code
        ]
        return EtfResearch(
            code=raw["code"],
            name=raw["name"],
            as_of=raw["as_of"],
            change_pct=raw.get("change_pct"),
            price_history=price_history,
            sector_mappings=mappings,
            fund_profile=(
                EtfFundProfile.model_validate(raw["fund_profile"])
                if raw.get("fund_profile")
                else None
            ),
        )

    def get_sector_evidence(self, sector_id: str) -> SectorEvidence | None:
        sector = self.get_sector_detail(sector_id)
        if sector is None:
            return None
        representatives = sector.stocks[:3]
        if not representatives:
            return SectorEvidence(
                sector_id=sector.id,
                sector_name=sector.name,
                state="unavailable",
                message="No representative stocks are available for public-news evidence.",
                representative_stocks=[],
                query_failures=[],
                cached_count=0,
                news=[],
            )
        news: list[SectorNewsEvidence] = []
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=len(representatives)) as executor:
            futures = {
                executor.submit(self._load_stock_news, stock): stock
                for stock in representatives
            }
            for future in as_completed(futures):
                stock = futures[future]
                try:
                    items, failure = future.result()
                except Exception as error:
                    failures.append(f"{stock.code}:{type(error).__name__}")
                    continue
                if failure:
                    failures.append(failure)
                news.extend(items)
        unique_news = {item.url: item for item in news if item.url}
        news = sorted(
            unique_news.values(),
            key=lambda item: (item.published_at, item.code, item.url),
            reverse=True,
        )[:6]
        return SectorEvidence(
            sector_id=sector.id,
            sector_name=sector.name,
            state="available" if news else "unavailable",
            message=(
                (
                    (
                        "本次公开新闻刷新失败，已保留上次成功记录；"
                        if any(item.data_state == "cached" for item in news)
                        else ""
                    )
                    + "新闻仅关联最多三只代表股，不代表整个板块催化已经成立。"
                )
                if news
                else (
                    "Representative-stock news returned no displayable records"
                    + (f" ({', '.join(failures)})." if failures else ".")
                )
            ),
            representative_stocks=[
                StockIdentity(code=stock.code, name=stock.name)
                for stock in representatives
            ],
            query_failures=failures,
            cached_count=sum(item.data_state == "cached" for item in news),
            news=news,
        )

    def _load_stock_news(
        self,
        stock: StockRecord,
    ) -> tuple[list[SectorNewsEvidence], str | None]:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                records = self._provider.get_stock_news(stock.code, 3)
            except Exception as error:
                last_error = error
                continue

            cached_at = datetime.now().astimezone().isoformat(timespec="seconds")
            if records:
                self._research_cache.put_news(
                    stock.code,
                    [record.model_dump(mode="json") for record in records],
                    cached_at,
                )
            return (
                [
                    SectorNewsEvidence(
                        code=stock.code,
                        name=stock.name,
                        **record.model_dump(),
                    )
                    for record in records
                ],
                None,
            )

        failure = f"{stock.code}:{type(last_error).__name__}"
        cached = self._research_cache.get_news(stock.code)
        if cached is None:
            return [], failure
        raw_records, cached_at = cached
        try:
            records = [StockNewsRecord.model_validate(item) for item in raw_records]
        except ValueError:
            return [], failure
        return (
            [
                SectorNewsEvidence(
                    code=stock.code,
                    name=stock.name,
                    **record.model_dump(),
                    data_state="cached",
                    cached_at=cached_at,
                )
                for record in records
            ],
            failure,
        )

    @staticmethod
    def get_llm_analysis_status() -> LlmAnalysisStatus:
        configuration = get_llm_runtime_configuration()
        model = configuration.model or None
        configured = configuration.configured
        return LlmAnalysisStatus(
            state="configured" if configured else "not-configured",
            provider="OpenAI-compatible API",
            model=model,
            message=(
                "模型已配置；只接收冻结后的结构化事实，不能改写行情数字。"
                if configured
                else "尚未配置 LLM_API_KEY 与 LLM_MODEL；AI简报当前仅使用规则化表达。"
            ),
        )

    def generate_llm_market_brief(self) -> LlmMarketBrief:
        status = self.get_llm_analysis_status()
        if status.state != "configured":
            return LlmMarketBrief(
                state="not-configured",
                analysis=None,
                message=status.message,
                as_of=None,
            )
        overview = self.get_overview()
        top_sectors = overview.hot_sectors[:3]
        histories: dict[str, SectorPriceHistory] = {}
        evidences: dict[str, SectorEvidence] = {}
        signal_scan: MarketSignalScan | None = None
        history_getter = getattr(self._provider, "get_sector_price_history", None)
        jobs: dict[object, tuple[str, str]] = {}
        with ThreadPoolExecutor(max_workers=max(2, len(top_sectors) * 2 + 1)) as executor:
            if callable(history_getter):
                for sector in top_sectors:
                    jobs[
                        executor.submit(history_getter, sector.name, 20)
                    ] = ("history", sector.id)
            for sector in top_sectors:
                jobs[executor.submit(self.get_sector_evidence, sector.id)] = (
                    "evidence",
                    sector.id,
                )
            jobs[executor.submit(self.get_market_signals)] = ("signals", "market")
            for future in as_completed(jobs):
                kind, item_id = jobs[future]
                try:
                    result = future.result()
                except Exception:
                    continue
                if kind == "history":
                    histories[item_id] = SectorPriceHistory.model_validate(result)
                elif kind == "evidence" and result is not None:
                    evidences[item_id] = result
                elif kind == "signals":
                    signal_scan = result

        data_gaps: list[str] = []
        metrics = overview.metrics
        if metrics.turnover_change_pct is None:
            data_gaps.append("两市成交额较上一交易日变化暂缺")
        if any(
            marker in metrics.northbound_status.casefold()
            for marker in ("unavailable", "not available", "暂", "未")
        ):
            data_gaps.append("北向资金暂缺")

        direction_facts: list[LlmBriefDirection] = []
        for sector in top_sectors:
            history = histories.get(sector.id)
            summary = history.summary if history is not None else None
            if history is None or history.state != "available" or summary is None:
                rotation = LlmBriefRotationFacts(state="unavailable")
                data_gaps.append(f"{sector.name}的20日轮动历史暂缺")
            else:
                rotation = LlmBriefRotationFacts(
                    state="available",
                    source=history.source,
                    period_days=summary.period_days,
                    trend_5d_pct=summary.trend_5d_pct,
                    trend_20d_pct=summary.trend_20d_pct,
                    relative_strength_pct=summary.relative_strength_pct,
                    trading_amount_change_pct=summary.turnover_change_pct,
                    volume_change_pct=summary.volume_change_pct,
                    benchmark_name=summary.benchmark_name,
                )
            evidence = evidences.get(sector.id)
            news = (
                [
                    LlmBriefNewsEvidence(
                        title=item.title,
                        published_at=item.published_at,
                        source=item.source,
                        linked_stock=f"{item.name}({item.code})",
                    )
                    for item in evidence.news[:2]
                ]
                if evidence is not None
                else []
            )
            if not news:
                data_gaps.append(f"{sector.name}的代表股新闻证据暂缺")
            direction_facts.append(
                LlmBriefDirection(
                    name=sector.name,
                    stage=sector.heat.stage,
                    change_pct=sector.change_pct,
                    heat_score=sector.heat.score,
                    capital_flow_billion=sector.capital_flow_billion,
                    capital_flow_label=sector.capital_flow_label,
                    risks=sector.risks[:2],
                    representative_stock_available=bool(sector.stocks),
                    representative_stocks=[
                        f"{stock.name}({stock.code})" for stock in sector.stocks[:2]
                    ],
                    rotation=rotation,
                    news=news,
                )
            )

        if signal_scan is None:
            technical_signals = LlmBriefTechnicalSignals(
                state="unavailable",
                scope_note="技术信号扫描暂不可用。",
                scanned_count=0,
                cached_count=0,
                buckets={},
                highlights=[],
                query_failures=[],
            )
            data_gaps.append("代表股技术信号暂缺")
        else:
            technical_signals = LlmBriefTechnicalSignals(
                state=signal_scan.state,
                scope_note=signal_scan.scope_note,
                scanned_count=signal_scan.scanned_count,
                cached_count=signal_scan.cached_count,
                buckets={item.id: item.count for item in signal_scan.buckets},
                highlights=[
                    (
                        f"{item.name}({item.code})/{item.sector}: "
                        f"{item.macd_state}; {item.kdj_state}; {item.weekly_state}"
                        + (
                            f"; 上次成功缓存于{item.cached_at}"
                            if item.data_state == "cached" and item.cached_at
                            else ""
                        )
                    )
                    for item in signal_scan.items[:6]
                ],
                query_failures=signal_scan.query_failures,
            )
            data_gaps.extend(
                f"技术信号查询失败：{item}" for item in signal_scan.query_failures
            )

        facts = LlmBriefFacts(
            as_of=overview.as_of,
            market_status=overview.market_status,
            market_sentiment=overview.sentiment.level,
            market_metrics=LlmBriefMarketMetrics(
                advancers=metrics.advancers,
                decliners=metrics.decliners,
                limit_up_count=metrics.limit_up_count,
                limit_down_count=metrics.limit_down_count,
                broken_board_rate=metrics.broken_board_rate,
                turnover_billion=metrics.turnover_billion,
                turnover_change_pct=metrics.turnover_change_pct,
                hotspot_concentration=metrics.hotspot_concentration,
            ),
            directions=direction_facts,
            technical_signals=technical_signals,
            data_gaps=list(dict.fromkeys(data_gaps)),
        )
        try:
            generated_sections = generate_evidence_explanation(
                {**facts.model_dump(), "boundary": overview.disclaimer}
            )
        except LlmNotConfigured:
            return LlmMarketBrief(
                state="not-configured",
                analysis=None,
                message="LLM配置在生成前发生变化。",
                as_of=overview.as_of,
                facts=facts,
            )
        except Exception as error:
            return LlmMarketBrief(
                state="unavailable",
                analysis=None,
                message=f"LLM暂时不可用（{type(error).__name__}）。",
                as_of=overview.as_of,
                facts=facts,
            )
        sections = LlmBriefSections.model_validate(generated_sections)
        analysis = "\n".join(
            [
                sections.market_conclusion,
                *sections.evidence,
                *sections.risks,
                *sections.data_gaps,
            ]
        )
        return LlmMarketBrief(
            state="generated",
            analysis=analysis,
            message="LLM仅基于冻结后的结构化事实生成解释。",
            as_of=overview.as_of,
            sections=sections,
            facts=facts,
        )

    def _record_snapshot(self, overview: MarketOverview) -> None:
        try:
            as_of = datetime.fromisoformat(overview.as_of)
        except ValueError:
            return
        for rank, sector in enumerate(overview.hot_sectors, start=1):
            self._history_store.record_sector(sector=sector, as_of=as_of, rank=rank)

    def search_stocks(self, query: str, limit: int = 12) -> list[StockIdentity]:
        return self._provider.search_stocks(query, limit)

    def get_stock_history(
        self,
        code: str,
        period: Literal["daily", "weekly", "monthly"] = "daily",
        adjust: Literal["", "qfq", "hfq"] = "qfq",
        limit: int = 120,
    ) -> StockHistory:
        return self._provider.get_stock_history(code, period, adjust, limit)

    def get_stock_technical_signals(self, code: str) -> TechnicalSignalStats:
        history = self.get_stock_history(code, period="daily", adjust="qfq", limit=250)
        return analyze_technical_signals(history.candles)

    def get_stock_research(self, code: str) -> StockResearchSnapshot:
        full_history = self.get_stock_history(code, period="daily", adjust="qfq", limit=250)
        return StockResearchSnapshot(
            history=full_history.model_copy(update={"candles": full_history.candles[-120:]}),
            technical=analyze_technical_signals(full_history.candles),
        )
