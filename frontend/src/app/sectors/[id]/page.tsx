import {
  SectorDetailPageView,
  SectorDetailUnavailablePageView,
} from "@/components/radar-views";
import {
  fetchMarketOverview,
  fetchSectorDetail,
  fetchSectorRotation,
} from "@/lib/api";
import { normalizeSectorId, resolveSectorDetail } from "@/lib/sector-detail";

export const dynamic = "force-dynamic";

export default async function SectorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: routeId } = await params;
  const id = normalizeSectorId(routeId);
  const [overview, fetchedSector] = await Promise.all([
    fetchMarketOverview(),
    fetchSectorDetail(id).catch(() => null),
  ]);
  const sector = resolveSectorDetail(overview, id, fetchedSector);
  if (!sector) return <SectorDetailUnavailablePageView overview={overview} />;
  const rotation = await fetchSectorRotation(id).catch(() => null);
  return (
    <SectorDetailPageView
      overview={overview}
      rotation={rotation}
      sector={sector}
    />
  );
}
