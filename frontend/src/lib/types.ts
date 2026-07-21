export type MarketLevel = "强" | "中" | "弱";
export type SectorStage = "冷却" | "启动" | "上涨" | "高潮" | "分歧" | "退潮";

export interface MarketSentiment {
  score: number;
  level: MarketLevel;
}

export interface MarketMetrics {
  advancers: number | null;
  decliners: number | null;
  limit_up_count: number;
  limit_down_count: number;
  max_board_height: number;
  broken_board_rate: number;
  turnover_billion: number;
  turnover_change_pct: number | null;
  hotspot_concentration: number;
  northbound_status: string;
}

export interface SectorFactors {
  breadth: number;
  turnover_acceleration: number;
  relative_strength: number;
  limit_density: number;
  leader_strength: number;
  capital_flow: number;
  catalyst_strength: number;
  previous_heat: number;
}

export interface StockObservation {
  code: string;
  name: string;
  direction: string;
  change_pct: number;
  relative_performance: string;
  capital_status: string;
  reason: string;
  risk: string;
}

export interface EtfMapping {
  theme: string;
  code: string;
  name: string;
  coverage_direction: string;
  tracking_index: string;
  score: number;
  explanation: string;
  verification_state: "constituent-verified" | "reviewed-code" | "name-match-only";
  verification_note: string;
}

export interface EtfResearch {
  code: string;
  name: string;
  as_of: string;
  change_pct: number | null;
  price_history: {
    source: string;
    points: Array<{ date: string; close: number; change_pct: number | null }>;
  };
  sector_mappings: EtfMapping[];
  fund_profile: {
    state: "available" | "unavailable";
    full_name: string | null;
    benchmark: string | null;
    manager: string | null;
    share_scale: string | null;
    source: string;
    retrieved_at: string;
    message: string;
  } | null;
}

export interface SectorOverview {
  id: string;
  name: string;
  summary: string;
  core_direction: string;
  change_pct: number;
  turnover_billion: number;
  capital_flow_billion: number | null;
  capital_flow_label: string;
  classification: SectorClassification;
  heat: {
    score: number;
    stage: SectorStage;
  };
  factors: SectorFactors;
  catalysts: string[];
  risks: string[];
  stocks: StockObservation[];
  etfs: EtfMapping[];
}

export interface SectorClassification {
  canonical_name: string;
  taxonomy_version: string;
  source_name: string;
  status: "source-native" | "cross-source-mapped";
  note: string;
}

export interface SectorRotationPoint {
  sector_id: string;
  sector_name: string;
  as_of: string;
  rank: number | null;
  heat_score: number | null;
  change_pct: number;
  capital_flow_billion: number | null;
  classification: SectorClassification;
  basis: "source-price-history" | "live-snapshot";
  strength_score: number | null;
  relative_strength_pct: number | null;
  turnover_change_pct: number | null;
  volume_change_pct: number | null;
}

export interface SectorRotation {
  sector_id: string;
  sector_name: string;
  classification: SectorClassification;
  capital_flow_label: string;
  status: "collecting" | "ready";
  minimum_required_points: number;
  data_points: number;
  window_days: number;
  basis: "source-price-history" | "live-snapshot";
  source: string;
  basis_note: string;
  snapshot_data_points: number;
  points: SectorRotationPoint[];
}

export interface SectorPriceHistory {
  state: "available" | "unavailable";
  requested_name: string;
  source_name: string | null;
  source: string;
  message: string;
  summary?: {
    period_days: number;
    period_change_pct: number | null;
    latest_turnover_billion: number | null;
    turnover_change_pct: number | null;
    volume_change_pct: number | null;
    trend_5d_pct: number | null;
    trend_20d_pct: number | null;
    relative_strength_pct: number | null;
    benchmark_name: string;
  } | null;
  points: Array<{
    date: string;
    close: number;
    change_pct: number | null;
    turnover_billion?: number | null;
    turnover_change_pct?: number | null;
    volume_change_pct?: number | null;
    relative_strength_pct?: number | null;
  }>;
}

export interface SourceReference {
  name: string;
  category: string;
  updated_at: string;
}

export interface MarketRefreshResult {
  state: "started" | "already-running" | "not-supported";
  message: string;
  as_of: string | null;
  data_quality: string | null;
}

export interface MarketDataStatus {
  as_of: string;
  data_quality: string;
  sources: SourceReference[];
  fields: Array<{
    field: string;
    state: "available" | "unavailable";
    message: string;
  }>;
}

export interface MarketSignalScan {
  state: "available" | "unavailable";
  as_of: string;
  scope: "current-hot-sector-representatives";
  scope_note: string;
  scanned_count: number;
  cached_count: number;
  query_failures: string[];
  buckets: Array<{
    id: "macd_golden_cross" | "macd_death_cross" | "kdj_golden_cross" | "kdj_death_cross" | "weekly_volume_anomaly";
    label: string;
    count: number;
  }>;
  items: Array<{
    code: string;
    name: string;
    sector: string;
    change_pct: number;
    as_of: string;
    source: string;
    sample_size: number;
    macd_state: string;
    kdj_state: string;
    weekly_state: string;
    data_state: "live" | "cached";
    cached_at: string | null;
  }>;
  disclaimer: string;
}

export interface SectorEvidence {
  sector_id: string;
  sector_name: string;
  state: "available" | "unavailable";
  message: string;
  representative_stocks: Array<{ code: string; name: string }>;
  query_failures: string[];
  cached_count: number;
  news: Array<{
    code: string;
    name: string;
    title: string;
    summary: string;
    published_at: string;
    source: string;
    url: string;
    data_state: "live" | "cached";
    cached_at: string | null;
  }>;
}

export interface LlmAnalysisStatus {
  state: "configured" | "not-configured";
  provider: string;
  model: string | null;
  message: string;
}

export interface LlmConnectionTestResult {
  state: "connected" | "failed" | "not-configured";
  code: string;
  message: string;
  model: string | null;
  latency_ms: number | null;
}

export interface LlmBriefSections {
  market_conclusion: string;
  evidence: string[];
  risks: string[];
  data_gaps: string[];
}

export interface LlmMarketBrief {
  state: "generated" | "not-configured" | "unavailable";
  analysis: string | null;
  message: string;
  as_of: string | null;
  sections: LlmBriefSections | null;
  facts: {
    as_of: string;
    market_status: string;
    market_sentiment: string;
    market_metrics: {
      advancers: number | null;
      decliners: number | null;
      limit_up_count: number;
      limit_down_count: number;
      broken_board_rate: number;
      turnover_billion: number;
      turnover_change_pct: number | null;
      hotspot_concentration: number;
    };
    directions: Array<{
      name: string;
      stage: string;
      change_pct: number;
      heat_score: number;
      capital_flow_billion: number | null;
      capital_flow_label: string;
      risks: string[];
      representative_stock_available: boolean;
      representative_stocks: string[];
      rotation: {
        state: "available" | "unavailable";
        source: string | null;
        period_days: number;
        trend_5d_pct: number | null;
        trend_20d_pct: number | null;
        relative_strength_pct: number | null;
        trading_amount_change_pct: number | null;
        volume_change_pct: number | null;
        benchmark_name: string | null;
      };
      news: Array<{
        title: string;
        published_at: string;
        source: string;
        linked_stock: string;
      }>;
    }>;
    technical_signals: {
      state: "available" | "unavailable";
      scope_note: string;
      scanned_count: number;
      buckets: Record<string, number>;
      highlights: string[];
      query_failures: string[];
    };
    data_gaps: string[];
  } | null;
}

export interface MarketOverview {
  as_of: string;
  data_quality: string;
  market_status: string;
  sentiment: MarketSentiment;
  metrics: MarketMetrics;
  hot_sectors: SectorOverview[];
  sources: SourceReference[];
  disclaimer: string;
}

export interface SearchResult {
  kind: "sector" | "stock" | "etf";
  id: string;
  name: string;
  subtitle: string;
}

export interface StockCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  change_pct: number | null;
}

export interface StockHistory {
  code: string;
  name: string;
  period: "daily" | "weekly" | "monthly";
  adjust: "" | "qfq" | "hfq";
  as_of: string;
  data_quality: string;
  source: string;
  candles: StockCandle[];
}

export interface TechnicalSignalStats {
  sample_size: number;
  macd: {
    dif: number | null;
    dea: number | null;
    histogram: number | null;
    state: string;
  };
  kdj: {
    k: number | null;
    d: number | null;
    j: number | null;
    state: string;
  };
  weekly: {
    weeks_observed: number;
    latest_change_pct: number | null;
    close_vs_ma5_pct: number | null;
    volume_ratio: number | null;
    state: string;
  };
  disclaimer: string;
}

export interface StockResearchSnapshot {
  history: StockHistory;
  technical: TechnicalSignalStats;
}
