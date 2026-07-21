import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { EtfFundProfilePanel } from "./etf-fund-profile-panel";

afterEach(cleanup);

it("shows the public benchmark as a fact without treating it as holdings verification", () => {
  render(
    <EtfFundProfilePanel
      profile={{
        state: "available",
        full_name: "华富中证人工智能产业ETF",
        benchmark: "中证人工智能产业指数收益率",
        manager: "华富基金管理有限公司",
        share_scale: "12.50亿份（2026-06-30）",
        source: "AKShare/THS fund profile",
        retrieved_at: "2026-07-20T10:30:00+08:00",
        message: "Public fund facts returned.",
      }}
    />,
  );

  expect(screen.getByText("PUBLIC FUND FACTS")).toBeInTheDocument();
  expect(screen.getByText("中证人工智能产业指数收益率")).toBeInTheDocument();
  expect(screen.getByText(/不等同于成分股或覆盖校验/)).toBeInTheDocument();
});
