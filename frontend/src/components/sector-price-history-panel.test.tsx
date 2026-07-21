import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SectorPriceHistoryPanel } from "@/components/sector-price-history-panel";

describe("SectorPriceHistoryPanel", () => {
  it("shows the backfilled 20-day strength, liquidity and benchmark metrics", () => {
    render(
      <SectorPriceHistoryPanel
        sectorId="industry-电力"
        initialHistory={{
          state: "available",
          requested_name: "电力",
          source_name: "电力",
          source: "AKShare/THS industry board history",
          message: "已回填最近20个交易日。",
          summary: {
            period_days: 20,
            period_change_pct: 18.8119,
            latest_turnover_billion: 21,
            turnover_change_pct: 5,
            volume_change_pct: 5,
            trend_5d_pct: 4.3478,
            trend_20d_pct: 18.8119,
            relative_strength_pct: 9.3591,
            benchmark_name: "上证指数",
          },
          points: Array.from({ length: 20 }, (_, index) => ({
            date: `2026-06-${String(index + 1).padStart(2, "0")}`,
            close: 101 + index,
            change_pct: index === 19 ? 0.8403 : 1,
            turnover_billion: 2 + index,
            turnover_change_pct: 5,
            volume_change_pct: 5,
            relative_strength_pct: (9.3591 / 19) * index,
          })),
        }}
      />,
    );

    expect(screen.getByText("20日板块强弱")).toBeInTheDocument();
    expect(screen.getByText("+18.81%")).toBeInTheDocument();
    expect(screen.getAllByText("成交额变化").length).toBeGreaterThan(0);
    expect(screen.getAllByText("量能变化").length).toBeGreaterThan(0);
    expect(screen.getByText("5日趋势")).toBeInTheDocument();
    expect(screen.getAllByText("相对强度").length).toBeGreaterThan(0);
    expect(screen.getByText("强于上证指数 +9.36%")).toBeInTheDocument();
    expect(screen.getByText("20个交易日明细")).toBeInTheDocument();
  });
});
