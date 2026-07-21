import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { DataStatusPanel } from "./data-status-panel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("translates public-data availability and keeps source details collapsed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        as_of: "2026-07-20T15:00:00+08:00",
        data_quality: "refreshing-live-public",
        fields: [
          { field: "advancers_decliners", state: "available", message: "Present." },
          { field: "northbound", state: "unavailable", message: "Not supplied." },
        ],
        sources: [
          { name: "source one", category: "market", updated_at: "2026-07-20" },
          { name: "source two", category: "etf", updated_at: "2026-07-20" },
        ],
      }),
    }),
  );

  render(<DataStatusPanel />);

  expect(await screen.findByText("已获取")).toBeInTheDocument();
  expect(screen.getByText("暂缺")).toBeInTheDocument();
  expect(screen.getByText("数据源 2 个")).toBeInTheDocument();
  expect(screen.getByText("查看来源明细")).toBeInTheDocument();
});
