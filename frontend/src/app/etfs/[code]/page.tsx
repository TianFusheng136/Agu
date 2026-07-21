import { notFound } from "next/navigation";

import { EtfResearchPageView } from "@/components/etf-research-view";
import { fetchEtfResearch, fetchMarketOverview } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function EtfResearchPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  if (!/^\d{6}$/.test(code)) notFound();
  const [overview, research] = await Promise.all([
    fetchMarketOverview(),
    fetchEtfResearch(code).catch(() => null),
  ]);
  if (!research) notFound();
  return <EtfResearchPageView overview={overview} research={research} />;
}
