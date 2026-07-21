import { notFound } from "next/navigation";

import { StockDetailPageView } from "@/components/radar-views";
import { fetchMarketOverview, fetchStockResearch } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function StockDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  if (!/^\d{6}$/.test(code)) notFound();
  const [overview, research] = await Promise.all([
    fetchMarketOverview(),
    fetchStockResearch(code),
  ]);
  return (
    <StockDetailPageView
      history={research.history}
      overview={overview}
      technical={research.technical}
    />
  );
}
