import type { MarketOverview } from "@/lib/types";

import { MarketPageView } from "./radar-views";

export function Dashboard({ overview }: { overview: MarketOverview }) {
  return <MarketPageView overview={overview} />;
}
