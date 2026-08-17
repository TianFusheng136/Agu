import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { TradingAgentsPanel } from "./trading-agents-panel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the research-only multi-agent flow and starts a background run", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          state: "ready",
          installed: true,
          configured: true,
          version: "0.3.1",
          model: "deepseek-chat",
          message: "多智能体研究链路已就绪。",
          analysts: ["技术", "情绪", "新闻", "基本面"],
          data_source: "TradingAgents / Yahoo Finance",
          execution_enabled: false,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "job-1",
          state: "queued",
          code: "600519",
          ticker: "600519.SS",
          analysis_date: "2026-08-09",
          depth: "quick",
          created_at: "2026-08-09T10:00:00+08:00",
          started_at: null,
          completed_at: null,
          message: "任务已进入队列。",
          result: null,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "job-1",
          state: "completed",
          code: "600519",
          ticker: "600519.SS",
          analysis_date: "2026-08-09",
          depth: "quick",
          created_at: "2026-08-09T10:00:00+08:00",
          started_at: "2026-08-09T10:00:01+08:00",
          completed_at: "2026-08-09T10:01:00+08:00",
          message: "多智能体研判已完成。",
          result: {
            analyst_reports: { technical: "技术报告", sentiment: "情绪报告", news: "新闻报告", fundamentals: "基本面报告" },
            research_debate: { bull: "看多", bear: "看空", judge: "裁决" },
            risk_review: { aggressive: "激进", neutral: "中性", conservative: "保守", judge: "风险裁决" },
            research_plan: "研究计划",
            strategy_hypothesis: "策略假设",
            final_assessment: "综合结论",
            direction_summary: {
              direction: "偏多",
              rating: "Overweight",
              bullish_weight: 65,
              bearish_weight: 35,
              weight_note: "这是倾向度，不是统计概率。",
              framework_price_target: 12.5,
              framework_price_target_note: "不是买入价。",
              price_context: {
                state: "above-zone",
                current_price: 11.2,
                observation_zone_low: 10.1,
                observation_zone_high: 10.5,
                support_20d: 9.8,
                resistance_20d: 11.5,
                message: "当前价格高于观察区间。",
                method: "均线观察区间，不是建议买入价。",
              },
            },
            source_note: "独立数据口径",
            disclaimer: "不构成投资建议",
          },
        }),
      }),
  );
  const user = userEvent.setup();
  render(<TradingAgentsPanel initialCode="600519" />);

  expect(await screen.findByText("研究链路已就绪")).toBeInTheDocument();
  expect(screen.getByText("技术分析")).toBeInTheDocument();
  expect(screen.getByText(/不连接券商/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "开始研判" }));

  expect(await screen.findByText("综合结论")).toBeInTheDocument();
  expect(screen.getByText("偏多")).toBeInTheDocument();
  expect(screen.getByText("65%")).toBeInTheDocument();
  expect(screen.getByText(/观察区间 10.100/)).toBeInTheDocument();
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
});
