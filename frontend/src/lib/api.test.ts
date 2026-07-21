import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL, fetchMarketOverview } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchMarketOverview", () => {
  it("uses the current API snapshot so a hot-sector link cannot outlive its list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data_quality: "live-public" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchMarketOverview();

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/market/overview`, {
      cache: "no-store",
    });
  });
});
