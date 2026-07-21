import type { MarketOverview, SectorOverview } from "./types";

export function normalizeSectorId(sectorId: string): string {
  try {
    return decodeURIComponent(sectorId);
  } catch {
    return sectorId;
  }
}

export function resolveSectorDetail(
  overview: MarketOverview,
  sectorId: string,
  detail: SectorOverview | null,
): SectorOverview | null {
  const normalizedSectorId = normalizeSectorId(sectorId);
  return (
    detail ??
    overview.hot_sectors.find((sector) => sector.id === normalizedSectorId) ??
    null
  );
}
