import { describe, expect, it } from "vitest";

import type { MarketOverview, SectorOverview } from "./types";
import { normalizeSectorId, resolveSectorDetail } from "./sector-detail";

const sector = { id: "industry-power", name: "电力" } as SectorOverview;
const overview = { hot_sectors: [sector] } as MarketOverview;

describe("resolveSectorDetail", () => {
  it("uses the already-rendered live sector when the follow-up detail request is transiently unavailable", () => {
    expect(resolveSectorDetail(overview, "industry-power", null)).toBe(sector);
  });

  it("decodes the percent-encoded route segment before API lookup", () => {
    expect(normalizeSectorId("industry-%E7%94%B5%E5%8A%9B")).toBe(
      "industry-\u7535\u529b",
    );
  });
});
