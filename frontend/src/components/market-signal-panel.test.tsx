import { StrictMode } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { MarketSignalPanel } from "./market-signal-panel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function signalPayload(overrides: Record<string, unknown> = {}) {
  return {
    state: "available",
    as_of: "2026-07-20T15:00:00+08:00",
    scope: "current-hot-sector-representatives",
    scope_note: "Up to two representatives per current top sector.",
    scanned_count: 1,
    cached_count: 0,
    query_failures: [],
    buckets: [
      { id: "macd_golden_cross", label: "MACD golden cross", count: 1 },
      { id: "macd_death_cross", label: "MACD death cross", count: 0 },
    ],
    items: [
      {
        code: "000021",
        name: "深科技",
        sector: "AI服务器",
        change_pct: 1.2,
        as_of: "2026-07-20",
        source: "public history",
        sample_size: 120,
        macd_state: "MACD金叉",
        kdj_state: "KDJ中性区",
        weekly_state: "周线位于5周均线之上",
        data_state: "live",
        cached_at: null,
      },
    ],
    ...overrides,
  };
}

it("renders a clearly scoped signal scan for current hot-sector representatives", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => signalPayload(),
  });
  vi.stubGlobal(
    "fetch",
    fetchMock,
  );

  render(<StrictMode><MarketSignalPanel /></StrictMode>);

  expect(await screen.findByText("MARKET SIGNAL SCAN")).toBeInTheDocument();
  expect(screen.getByText("深科技")).toBeInTheDocument();
  expect(screen.getByText("MACD金叉")).toBeInTheDocument();
  expect(screen.getByText(/仅扫描当前热点板块代表股/)).toBeInTheDocument();
  expect(
    screen.getByText(/MACD 看趋势变化，KDJ 看短期位置，周K看一周走势和成交量/),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("keeps the last successful scan visible when a manual refresh fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => signalPayload(),
    })
    .mockRejectedValueOnce(new Error("network unavailable"));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();

  render(<MarketSignalPanel />);

  expect(await screen.findByText("深科技")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "刷新信号" }));

  expect(
    await screen.findByText("本次刷新失败，继续显示上次成功结果。"),
  ).toBeInTheDocument();
  expect(screen.getByText("深科技")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("labels technical signals that came from the last successful cache", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () =>
      signalPayload({
        cached_count: 1,
        query_failures: ["000021:ConnectionError"],
        items: [
          {
            ...signalPayload().items[0],
            data_state: "cached",
            cached_at: "2026-07-21T09:42:00+08:00",
          },
        ],
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<MarketSignalPanel />);

  expect(await screen.findByText("深科技")).toBeInTheDocument();
  expect(screen.getByText("1 只 · 1 缓存")).toBeInTheDocument();
  expect(screen.getByText("上次成功数据 · 07/21 09:42")).toBeInTheDocument();
  expect(
    screen.getByText("1 只代表股本次刷新失败，已明确保留上次成功的技术结构。"),
  ).toBeInTheDocument();
});
