import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  classifyRotationStage,
  SectorRotationComparison,
} from "@/components/sector-rotation-comparison";
import type { SectorPriceHistory } from "@/lib/types";

function history(
  trend5: number,
  trend20: number,
  relativeStrength: number,
): SectorPriceHistory {
  return {
    state: "available",
    requested_name: "测试板块",
    source_name: "测试板块",
    source: "AKShare/THS industry board history",
    message: "真实历史",
    summary: {
      period_days: 20,
      period_change_pct: trend20,
      latest_turnover_billion: 100,
      turnover_change_pct: 12,
      volume_change_pct: 8,
      trend_5d_pct: trend5,
      trend_20d_pct: trend20,
      relative_strength_pct: relativeStrength,
      benchmark_name: "上证指数",
    },
    points: [],
  };
}

describe("classifyRotationStage", () => {
  it("uses transparent 5-day and 20-day rules", () => {
    expect(classifyRotationStage(history(8, 4, 3))).toBe("持续走强");
    expect(classifyRotationStage(history(6, -4, 2))).toBe("短线修复");
    expect(classifyRotationStage(history(-3, 5, 1))).toBe("高位降温");
    expect(classifyRotationStage(history(-2, -6, -3))).toBe("持续偏弱");
  });
});

describe("SectorRotationComparison", () => {
  it("ranks current hot sectors by relative strength and explains their stage", () => {
    render(
      <SectorRotationComparison
        sectors={[
          { id: "industry-power", name: "电力" },
          { id: "industry-coal", name: "煤炭" },
        ]}
        initialHistories={{
          "industry-power": history(8, 4, 3),
          "industry-coal": history(6, -4, 7),
        }}
      />,
    );

    expect(screen.getByText("热点板块20日轮动对比")).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByText("煤炭")).toBeInTheDocument();
    expect(within(rows[1]).getByText("短线修复")).toBeInTheDocument();
    expect(within(rows[2]).getByText("电力")).toBeInTheDocument();
    expect(within(rows[2]).getByText("持续走强")).toBeInTheDocument();
    expect(screen.getByText(/按相对上证指数强度排序/)).toBeInTheDocument();
  });
});
