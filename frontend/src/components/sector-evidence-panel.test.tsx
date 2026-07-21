import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { SectorEvidencePanel } from "./sector-evidence-panel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("labels cached public news with its last-success time", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        sector_id: "industry-电力",
        sector_name: "电力",
        state: "available",
        message: "本次公开新闻刷新失败，已保留上次成功记录。",
        representative_stocks: [{ code: "600744", name: "华银电力" }],
        query_failures: ["600744:ConnectionError"],
        cached_count: 1,
        news: [
          {
            code: "600744",
            name: "华银电力",
            title: "公开新闻标题",
            summary: "公开新闻摘要",
            published_at: "2026-07-20 14:00:00",
            source: "公开新闻源",
            url: "https://example.test/news/600744",
            data_state: "cached",
            cached_at: "2026-07-21T09:42:00+08:00",
          },
        ],
      }),
    }),
  );

  render(<SectorEvidencePanel sectorId="industry-电力" />);

  expect(await screen.findByText("公开新闻标题")).toBeInTheDocument();
  expect(screen.getByText("公开新闻 · 1缓存")).toBeInTheDocument();
  expect(screen.getByText("上次成功数据 · 07/21 09:42")).toBeInTheDocument();
  expect(
    screen.getByText("本次公开新闻刷新失败，已保留上次成功记录。"),
  ).toBeInTheDocument();
});
