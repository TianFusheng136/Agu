import type {
  MarketOverview,
  MarketRefreshResult,
  MarketDataStatus,
  MarketSignalScan,
  LlmAnalysisStatus,
  LlmConnectionTestResult,
  LlmMarketBrief,
  SectorOverview,
  SectorRotation,
  SectorPriceHistory,
  StockHistory,
  StockResearchSnapshot,
  SectorEvidence,
  EtfResearch,
  TradingAgentsRun,
  TradingAgentsStatus,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001/api/v1";

export async function fetchMarketOverview(): Promise<MarketOverview> {
  const response = await fetch(`${API_BASE_URL}/market/overview`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`市场数据接口返回 ${response.status}`);
  }
  return response.json() as Promise<MarketOverview>;
}

export async function requestMarketRefresh(): Promise<MarketRefreshResult> {
  const response = await fetch(`${API_BASE_URL}/market/refresh`, {
    method: "POST",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(payload?.detail || `行情刷新接口返回 ${response.status}`);
  }
  return response.json() as Promise<MarketRefreshResult>;
}

export async function fetchMarketDataStatus(): Promise<MarketDataStatus> {
  const response = await fetch(`${API_BASE_URL}/market/data-status`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Market data status endpoint returned ${response.status}`);
  return response.json() as Promise<MarketDataStatus>;
}

export async function fetchMarketSignals(): Promise<MarketSignalScan> {
  const response = await fetch(`${API_BASE_URL}/market/signals`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Market signal endpoint returned ${response.status}`);
  return response.json() as Promise<MarketSignalScan>;
}

export async function fetchSectorEvidence(id: string): Promise<SectorEvidence> {
  const response = await fetch(
    `${API_BASE_URL}/sectors/${encodeURIComponent(id)}/evidence`,
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error(`新闻证据接口返回 ${response.status}`);
  return response.json() as Promise<SectorEvidence>;
}

export async function fetchEtfResearch(code: string): Promise<EtfResearch> {
  const response = await fetch(`${API_BASE_URL}/etfs/${encodeURIComponent(code)}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`ETF research endpoint returned ${response.status}`);
  return response.json() as Promise<EtfResearch>;
}

export async function fetchLlmAnalysisStatus(): Promise<LlmAnalysisStatus> {
  const response = await fetch(`${API_BASE_URL}/analysis/status`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`LLM状态接口返回 ${response.status}`);
  return response.json() as Promise<LlmAnalysisStatus>;
}

export async function saveLlmConfiguration(input: {
  apiKey: string;
  model: string;
  baseUrl: string;
}): Promise<LlmAnalysisStatus> {
  const response = await fetch(`${API_BASE_URL}/analysis/configuration`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: input.apiKey,
      model: input.model,
      base_url: input.baseUrl,
    }),
  });
  if (!response.ok) throw new Error(`LLM 配置接口返回 ${response.status}`);
  return response.json() as Promise<LlmAnalysisStatus>;
}

export async function testLlmConnection(): Promise<LlmConnectionTestResult> {
  const response = await fetch(`${API_BASE_URL}/analysis/connection-test`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`LLM连接检测接口返回 ${response.status}`);
  return response.json() as Promise<LlmConnectionTestResult>;
}

export async function generateLlmMarketBrief(): Promise<LlmMarketBrief> {
  const response = await fetch(`${API_BASE_URL}/analysis/market-brief`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`LLM简报接口返回 ${response.status}`);
  return response.json() as Promise<LlmMarketBrief>;
}

async function readApiError(response: Response, fallback: string): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as {
    detail?: string;
  } | null;
  return new Error(payload?.detail || fallback);
}

export async function fetchTradingAgentsStatus(): Promise<TradingAgentsStatus> {
  const response = await fetch(`${API_BASE_URL}/trading-agents/status`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw await readApiError(response, `多智能体状态接口返回 ${response.status}`);
  }
  return response.json() as Promise<TradingAgentsStatus>;
}

export async function startTradingAgentsRun(input: {
  code: string;
  depth: "quick" | "standard";
  analysisDate?: string;
}): Promise<TradingAgentsRun> {
  const response = await fetch(`${API_BASE_URL}/trading-agents/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code: input.code,
      depth: input.depth,
      analysis_date: input.analysisDate || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, `无法启动多智能体研判（${response.status}）`);
  }
  return response.json() as Promise<TradingAgentsRun>;
}

export async function fetchTradingAgentsRun(id: string): Promise<TradingAgentsRun> {
  const response = await fetch(
    `${API_BASE_URL}/trading-agents/runs/${encodeURIComponent(id)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw await readApiError(response, `读取研判任务失败（${response.status}）`);
  }
  return response.json() as Promise<TradingAgentsRun>;
}

export async function fetchSectorDetail(id: string): Promise<SectorOverview> {
  const response = await fetch(`${API_BASE_URL}/sectors/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`板块详情接口返回 ${response.status}`);
  }
  return response.json() as Promise<SectorOverview>;
}

export async function fetchSectorRotation(
  id: string,
  days = 20,
): Promise<SectorRotation> {
  const response = await fetch(
    `${API_BASE_URL}/sectors/${encodeURIComponent(id)}/rotation?days=${days}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`板块轮动接口返回 ${response.status}`);
  }
  return response.json() as Promise<SectorRotation>;
}

export async function fetchSectorPriceHistory(
  id: string,
  days = 20,
): Promise<SectorPriceHistory> {
  const response = await fetch(
    `${API_BASE_URL}/sectors/${encodeURIComponent(id)}/price-history?days=${days}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Sector price history endpoint returned ${response.status}`);
  }
  return response.json() as Promise<SectorPriceHistory>;
}

export async function fetchStockHistory(
  code: string,
  limit = 120,
): Promise<StockHistory> {
  const response = await fetch(
    `${API_BASE_URL}/stocks/${encodeURIComponent(code)}/candles?period=daily&adjust=qfq&limit=${limit}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(payload?.detail || `K线接口返回 ${response.status}`);
  }
  return response.json() as Promise<StockHistory>;
}

export async function fetchStockResearch(
  code: string,
): Promise<StockResearchSnapshot> {
  const response = await fetch(
    `${API_BASE_URL}/stocks/${encodeURIComponent(code)}/research`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(payload?.detail || `股票研究接口返回 ${response.status}`);
  }
  return response.json() as Promise<StockResearchSnapshot>;
}
