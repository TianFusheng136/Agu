import { StocksPageView } from "@/components/radar-views";
import { fetchMarketOverview } from "@/lib/api";

export const revalidate = 30;

export default async function StocksPage() {
  const overview = await fetchMarketOverview();
  return <StocksPageView overview={overview} />;
}
