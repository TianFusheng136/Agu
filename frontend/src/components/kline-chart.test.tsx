import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { StockHistory } from "@/lib/types";

import { KLineChart } from "./kline-chart";

const history: StockHistory = {
  code: "000021",
  name: "深科技",
  period: "daily",
  adjust: "qfq",
  as_of: "2026-07-17",
  data_quality: "live-public",
  source: "AKShare·东方财富A股历史行情",
  candles: Array.from({ length: 120 }, (_, index) => {
    const close = 18 + index * 0.03;
    return {
      date: new Date(2026, 2, index + 1).toISOString().slice(0, 10),
      open: close - 0.15,
      high: close + 0.4,
      low: close - 0.35,
      close,
      volume: 1_000_000 + index * 1000,
      amount: 20_000_000 + index * 10000,
      change_pct: 0.5,
    };
  }),
};

afterEach(cleanup);

describe("KLineChart", () => {
  it("renders candlesticks, moving averages and selectable time ranges", async () => {
    const user = userEvent.setup();
    render(<KLineChart history={history} />);

    expect(
      screen.getByRole("img", { name: "深科技最近60个交易日K线图" }),
    ).toBeInTheDocument();
    expect(screen.getByText("MA5")).toBeInTheDocument();
    expect(screen.getByText("MA10")).toBeInTheDocument();
    expect(screen.getByText("MA20")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "120日" }));
    expect(
      screen.getByRole("img", { name: "深科技最近120个交易日K线图" }),
    ).toBeInTheDocument();
  });
});
