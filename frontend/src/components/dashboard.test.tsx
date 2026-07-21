import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({
    href,
    prefetch,
    children,
    ...props
  }: {
    href: string;
    prefetch?: boolean;
    children: React.ReactNode;
  }) => (
    <a data-prefetch={String(prefetch)} href={href} {...props}>
      {children}
    </a>
  ),
}));

import type {
  MarketOverview,
  StockHistory,
  TechnicalSignalStats,
} from "@/lib/types";

import { Dashboard } from "./dashboard";
import {
  BriefPageView,
  MarketPageView,
  SectorDetailUnavailablePageView,
  SectorDetailPageView,
  SectorsPageView,
  StockDetailPageView,
  StocksPageView,
} from "./radar-views";

const overview: MarketOverview = {
  as_of: "2026-07-17T15:10:00+08:00",
  data_quality: "live-public",
  market_status: "已收盘",
  sentiment: { score: 68.9, level: "中" },
  metrics: {
    advancers: 3216,
    decliners: 1814,
    limit_up_count: 63,
    limit_down_count: 8,
    max_board_height: 5,
    broken_board_rate: 24.6,
    turnover_billion: 1286.4,
    turnover_change_pct: null,
    hotspot_concentration: 71.3,
    northbound_status: "演示数据未接入",
  },
  hot_sectors: [
    {
      id: "ai-server",
      name: "AI服务器",
      summary: "算力基础设施成交活跃。",
      core_direction: "服务器、光模块与液冷",
      change_pct: 4.82,
      turnover_billion: 136.5,
      capital_flow_billion: 18.7,
      capital_flow_label: "行业资金净额（非主力净流入）",
      classification: {
        canonical_name: "AI服务器",
        taxonomy_version: "cn-industry-v1",
        source_name: "同花顺行业资金流 + 新浪行业行情",
        status: "cross-source-mapped",
        note: "名称以同花顺行业资金流为主，并与新浪行业行情交叉匹配。",
      },
      heat: { score: 87.9, stage: "上涨" },
      factors: {
        breadth: 88,
        turnover_acceleration: 92,
        relative_strength: 91,
        limit_density: 82,
        leader_strength: 90,
        capital_flow: 87,
        catalyst_strength: 83,
        previous_heat: 74,
      },
      catalysts: ["云厂商资本开支预期"],
      risks: ["高位核心股可能出现分歧"],
      stocks: [
        {
          code: "000021",
          name: "深科技",
          direction: "AI硬件",
          change_pct: 5.31,
          relative_performance: "强于板块",
          capital_status: "成交放量",
          reason: "服务器产业链关注度提升",
          risk: "板块波动放大",
        },
      ],
      etfs: [
        {
          theme: "AI服务器",
          code: "515980",
          name: "人工智能ETF",
          coverage_direction: "AI算力与应用综合覆盖",
          tracking_index: "中证人工智能产业指数",
          score: 92,
          explanation: "仅描述指数与成分覆盖。",
        },
      ],
    },
  ],
  sources: [
    {
      name: "AKShare·同花顺行业行情",
      category: "sector",
      updated_at: "2026-07-17T15:10:00+08:00",
    },
  ],
  disclaimer: "本产品仅提供市场研究信息，不构成任何投资建议或收益承诺。",
};

const stockHistory: StockHistory = {
  code: "000021",
  name: "深科技",
  period: "daily",
  adjust: "qfq",
  as_of: "2026-07-17",
  data_quality: "live-public",
  source: "AKShare·东方财富A股历史行情",
  candles: [
    {
      date: "2026-07-16",
      open: 22.1,
      high: 23.4,
      low: 21.8,
      close: 23.0,
      volume: 123456,
      amount: 281234567,
      change_pct: 4.55,
    },
    {
      date: "2026-07-17",
      open: 23.0,
      high: 24.1,
      low: 22.7,
      close: 23.6,
      volume: 153456,
      amount: 341234567,
      change_pct: 2.61,
    },
  ],
};

const technical: TechnicalSignalStats = {
  sample_size: 120,
  macd: { dif: 0.2212, dea: 0.1821, histogram: 0.0782, state: "MACD金叉" },
  kdj: { k: 72.2, d: 66.8, j: 83.0, state: "KDJ金叉" },
  weekly: {
    weeks_observed: 24,
    latest_change_pct: 3.21,
    close_vs_ma5_pct: 2.34,
    volume_ratio: 1.42,
    state: "周线位于5周均线之上",
  },
  disclaimer: "技术指标仅描述历史价格与成交结构，不构成买卖建议或收益承诺。",
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Dashboard", () => {
  it("uses four independent page routes in the primary navigation", () => {
    render(<Dashboard overview={overview} />);

    expect(screen.getByRole("link", { name: "市场全景" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: "热点板块" })).toHaveAttribute(
      "href",
      "/sectors",
    );
    expect(screen.getByRole("link", { name: "核心观察" })).toHaveAttribute(
      "href",
      "/stocks",
    );
    expect(screen.getByRole("link", { name: "AI 简报" })).toHaveAttribute(
      "href",
      "/brief",
    );
    expect(screen.getByText("RADAR OS / A-SHARE / FINAL 1.0")).toBeInTheDocument();
  });

  it("keeps the market page focused and links each theme to its detail page", () => {
    render(<Dashboard overview={overview} />);

  expect(
    screen.getByRole("heading", { level: 1, name: "市场全景" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "市场脉冲" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "资金方向地图" })).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/sectors/ai-server"),
    ).toBe(true);
    expect(screen.getAllByText("公开行情")).not.toHaveLength(0);
    expect(screen.getByText("AKShare·同花顺行业行情")).toBeInTheDocument();
    expect(screen.getByText(/不构成任何投资建议/)).toBeInTheDocument();
    expect(screen.queryByText("买入")).not.toBeInTheDocument();
    expect(screen.queryByText("卖出")).not.toBeInTheDocument();
  });

  it("keeps source diagnostics out of the investor-facing market page", () => {
    render(<Dashboard overview={overview} />);

    expect(screen.queryByText("DATA QUALITY MONITOR")).not.toBeInTheDocument();
  });

  it("shows the two-market turnover comparison when same-source data is available", () => {
    render(
      <MarketPageView
        overview={{
          ...overview,
          metrics: {
            ...overview.metrics,
            turnover_billion: 27039.8,
            turnover_change_pct: 1.7,
          },
        }}
      />,
    );

    expect(
      screen.getByText("亿元 · 较前一交易日 +1.7%"),
    ).toBeInTheDocument();
  });

  it("shows a plain retry message instead of calling a transient detail failure a list update", () => {
    render(<SectorDetailUnavailablePageView overview={overview} />);

    expect(screen.getByText("板块详情暂时不可用")).toBeInTheDocument();
    expect(screen.getByText("公开行情正在更新，请返回热点板块后重试。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回热点板块" })).toHaveAttribute(
      "href",
      "/sectors",
    );
  });

  it("marks a cached snapshot explicitly when the upstream refresh fails", () => {
    render(<Dashboard overview={{ ...overview, data_quality: "stale-public" }} />);

    expect(
      screen.getAllByText("缓存行情 · 上游刷新失败"),
    ).not.toHaveLength(0);
  });

  it("starts a non-blocking public-market refresh from the top bar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          state: "started",
          message: "已发起公开行情后台刷新。",
          as_of: overview.as_of,
          data_quality: "live-public",
        }),
      }),
    );
    const user = userEvent.setup();
    render(<Dashboard overview={overview} />);

    await user.click(screen.getByRole("button", { name: "刷新行情" }));

    expect(await screen.findByText(/已发起后台刷新/)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/market/refresh"),
      { method: "POST" },
    );
  });

  it("gives every hot sector a large row and an independent detail route", () => {
    render(<SectorsPageView overview={overview} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "热点板块" }),
    ).toBeInTheDocument();
    expect(screen.getByText("深科技")).toBeInTheDocument();
    expect(screen.queryByText("对应 ETF")).not.toBeInTheDocument();
    const link = screen.getByRole("link", { name: "查看板块详情 →" });
    expect(link).toHaveAttribute("href", "/sectors/ai-server");
    expect(link).toHaveAttribute("data-prefetch", "false");
  });

  it("does not turn missing sector turnover into a false zero on the atlas", () => {
    render(
      <SectorsPageView
        overview={{
          ...overview,
          hot_sectors: [
            { ...overview.hot_sectors[0], turnover_billion: 0 },
          ],
        }}
      />,
    );

    expect(screen.getByText("成交金额").parentElement).toHaveTextContent(
      "数据暂缺",
    );
    expect(screen.queryByText("0.0 亿")).not.toBeInTheDocument();
  });

  it("lets Next encode Chinese sector ids instead of pre-encoding the link", () => {
    const chineseSectorOverview: MarketOverview = {
      ...overview,
      hot_sectors: [
        {
          ...overview.hot_sectors[0],
          id: "industry-电力",
          name: "电力",
        },
      ],
    };

    render(<SectorsPageView overview={chineseSectorOverview} />);

    expect(screen.getByRole("link", { name: "查看板块详情 →" })).toHaveAttribute(
      "href",
      "/sectors/industry-电力",
    );
  });

  it("does not use ETF availability as a sector ranking metric", () => {
    const withoutEtf: MarketOverview = {
      ...overview,
      hot_sectors: [{ ...overview.hot_sectors[0], etfs: [] }],
    };

    render(<SectorsPageView overview={withoutEtf} />);

    expect(screen.getByText("深科技")).toBeInTheDocument();
    expect(screen.queryByText("暂无精确映射")).not.toBeInTheDocument();
  });

  it("keeps source-labeled sector price history separate from the rotation heat curve", () => {
    render(
      <SectorDetailPageView
        overview={overview}
        sector={overview.hot_sectors[0]}
        priceHistory={{
          state: "available",
          requested_name: "AI服务器",
          source_name: "AI服务器",
          source: "AKShare/Eastmoney industry board history",
          message: "Exact source-board match.",
          points: [
            { date: "2026-07-17", close: 100, change_pct: 1.2 },
            { date: "2026-07-20", close: 102, change_pct: 2 },
          ],
        }}
      />,
    );

    expect(screen.getByLabelText("板块公开价格历史曲线")).toBeInTheDocument();
    expect(
      screen.getByText("AKShare/Eastmoney industry board history · AI服务器"),
    ).toBeInTheDocument();
  });

  it("marks unavailable sector turnover instead of displaying a false zero", () => {
    const sector = { ...overview.hot_sectors[0], turnover_billion: 0 };

    render(<SectorDetailPageView overview={overview} sector={sector} />);

    expect(screen.getByText("成交金额").parentElement).toHaveTextContent(
      "数据暂缺",
    );
    expect(screen.queryByText("0.0 亿")).not.toBeInTheDocument();
  });

  it("labels sector flow and classification provenance without calling it main-force flow", () => {
    render(
      <SectorDetailPageView
        overview={overview}
        rotation={{
          sector_id: "ai-server",
          sector_name: "AI服务器",
          classification: overview.hot_sectors[0].classification,
          capital_flow_label: "行业资金净额（非主力净流入）",
          status: "collecting",
          minimum_required_points: 5,
          data_points: 1,
          window_days: 20,
          points: [],
        }}
        sector={overview.hot_sectors[0]}
      />,
    );

    expect(screen.getAllByText("行业资金净额（非主力净流入）")).not.toHaveLength(0);
    expect(screen.getByText("板块分类口径")).toBeInTheDocument();
    expect(screen.getByText("样本积累中 1 / 5")).toBeInTheDocument();
    expect(screen.getByText("热度曲线")).toBeInTheDocument();
  });

  it("links every core stock to the K-line detail page", () => {
    render(<StocksPageView overview={overview} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "核心股票观察" }),
    ).toBeInTheDocument();
    expect(screen.getByText("深科技").closest("a")).toHaveAttribute(
      "href",
      "/stocks/000021",
    );
  });

  it("shows weekly, MACD and KDJ as historical statistics rather than an action", () => {
    render(
      <StockDetailPageView
        history={stockHistory}
        overview={overview}
        technical={technical}
      />,
    );

    expect(screen.getByText("周K与技术信号统计")).toBeInTheDocument();
    expect(screen.getByText("MACD金叉")).toBeInTheDocument();
    expect(screen.getByText("KDJ金叉")).toBeInTheDocument();
    expect(
      screen.getByText(/MACD 看趋势变化，KDJ 看短期位置，周K看一周走势和成交量/),
    ).toBeInTheDocument();
    expect(screen.getByText(/不构成买卖建议/)).toBeInTheDocument();
  });

  it("renders the AI brief on its own page", () => {
    render(<BriefPageView overview={overview} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "今日 A 股短线观察" }),
    ).toBeInTheDocument();
    expect(screen.getByText("风险提示")).toBeInTheDocument();
    expect(screen.queryByText("对应 ETF")).not.toBeInTheDocument();
    expect(screen.queryByText(/515980/)).not.toBeInTheDocument();
  });

  it("keeps related ETF tools collapsed outside the sector evidence flow", () => {
    render(
      <SectorDetailPageView
        overview={overview}
        sector={overview.hot_sectors[0]}
      />,
    );

    const summary = screen.getByText("相关 ETF 工具");
    expect(summary.closest("details")).not.toHaveAttribute("open");
  });

  it("does not claim a confirmed fund-flow direction when sector flow is missing", () => {
    const withoutFlow: MarketOverview = {
      ...overview,
      hot_sectors: [
        {
          ...overview.hot_sectors[0],
          capital_flow_billion: null,
        },
      ],
    };

    const { unmount } = render(<MarketPageView overview={withoutFlow} />);
    expect(screen.getByText(/资金净流入数据暂缺/)).toBeInTheDocument();
    expect(screen.queryByText(/资金当前主要聚焦/)).not.toBeInTheDocument();
    unmount();

    render(<BriefPageView overview={withoutFlow} />);
    expect(screen.getByText(/不能据此确认主力净流入/)).toBeInTheDocument();
    expect(screen.queryByText(/资金聚焦/)).not.toBeInTheDocument();
  });

  it("focuses search with Ctrl+K and closes results with Escape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            kind: "stock",
            id: "000021",
            name: "深科技",
            subtitle: "000021 · AI硬件 · AI服务器",
          },
        ],
      }),
    );
    const user = userEvent.setup();
    render(<Dashboard overview={overview} />);
    const searchbox = screen.getByRole("searchbox");

    await user.keyboard("{Control>}k{/Control}");
    expect(searchbox).toHaveFocus();

    await user.type(searchbox, "深科技");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    expect(await screen.findByText("000021 · AI硬件 · AI服务器")).toBeInTheDocument();
    expect(screen.getByText("000021 · AI硬件 · AI服务器").closest("a")).toHaveAttribute(
      "href",
      "/stocks/000021",
    );

    await user.keyboard("{Escape}");
    expect(screen.queryByText("000021 · AI硬件 · AI服务器")).not.toBeInTheDocument();
  });

  it("shows the backend error detail instead of a vague unavailable message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "A股代码表暂时不可用" }),
      }),
    );
    const user = userEvent.setup();
    render(<Dashboard overview={overview} />);

    await user.type(screen.getByRole("searchbox"), "000021");
    await user.click(screen.getByRole("button", { name: "搜索" }));

    expect(
      await screen.findByText("搜索失败：A股代码表暂时不可用"),
    ).toBeInTheDocument();
  });

  it("explains a cold catalog warmup without presenting it as a broken search", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "A股代码表正在后台加载，请稍后重试" }),
      }),
    );
    const user = userEvent.setup();
    render(<Dashboard overview={overview} />);

    await user.type(screen.getByRole("searchbox"), "000021");
    await user.click(screen.getByRole("button", { name: "搜索" }));

    expect(
      await screen.findByText("股票目录正在初始化，请几秒后重试"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/搜索失败/)).not.toBeInTheDocument();
  });
});
