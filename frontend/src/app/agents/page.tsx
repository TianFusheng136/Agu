import { TradingAgentsPanel } from "@/components/trading-agents-panel";
import { RadarShell } from "@/components/radar-shell";
import { fetchMarketOverview } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AgentsPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const [overview, query] = await Promise.all([fetchMarketOverview(), searchParams]);
  const initialCode = /^\d{6}$/.test(query.code ?? "") ? query.code ?? "" : "";
  return (
    <RadarShell active="agents" overview={overview}>
      <TradingAgentsPanel initialCode={initialCode} />
    </RadarShell>
  );
}
