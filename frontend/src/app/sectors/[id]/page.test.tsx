import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MarketOverview, SectorOverview } from "@/lib/types";

const api = vi.hoisted(() => ({
  fetchMarketOverview: vi.fn(),
  fetchSectorDetail: vi.fn(),
  fetchSectorPriceHistory: vi.fn(),
  fetchSectorRotation: vi.fn(),
}));

vi.mock("@/lib/api", () => api);

vi.mock("@/components/radar-views", () => ({
  SectorDetailPageView: () => null,
  SectorDetailUnavailablePageView: () => null,
}));

import SectorDetailPage from "./page";

const sector = {
  id: "industry-\u7535\u529b",
  name: "\u7535\u529b",
} as SectorOverview;

const overview = {
  hot_sectors: [sector],
} as MarketOverview;

describe("SectorDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchMarketOverview.mockResolvedValue(overview);
    api.fetchSectorDetail.mockResolvedValue(sector);
    api.fetchSectorRotation.mockResolvedValue(null);
    api.fetchSectorPriceHistory.mockResolvedValue(null);
  });

  it("does not block the detail page on optional public price history", async () => {
    await SectorDetailPage({
      params: Promise.resolve({ id: "industry-%E7%94%B5%E5%8A%9B" }),
    });

    expect(api.fetchSectorDetail).toHaveBeenCalledWith("industry-\u7535\u529b");
    expect(api.fetchSectorRotation).toHaveBeenCalledWith("industry-\u7535\u529b");
    expect(api.fetchSectorPriceHistory).not.toHaveBeenCalled();
  });
});
