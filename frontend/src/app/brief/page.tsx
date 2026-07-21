import { BriefPageView } from "@/components/radar-views";
import { fetchMarketOverview } from "@/lib/api";

export const revalidate = 30;

export default async function BriefPage() {
  const overview = await fetchMarketOverview();
  return <BriefPageView overview={overview} />;
}
