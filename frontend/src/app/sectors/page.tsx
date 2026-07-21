import { SectorsPageView } from "@/components/radar-views";
import { fetchMarketOverview } from "@/lib/api";

export const revalidate = 30;

export default async function SectorsPage() {
  const overview = await fetchMarketOverview();
  return <SectorsPageView overview={overview} />;
}
