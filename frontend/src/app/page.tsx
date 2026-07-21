import { Dashboard } from "@/components/dashboard";
import { fetchMarketOverview } from "@/lib/api";

export const revalidate = 30;

export default async function Home() {
  const overview = await fetchMarketOverview();
  return <Dashboard overview={overview} />;
}
