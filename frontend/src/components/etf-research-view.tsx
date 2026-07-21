import type { EtfResearch, MarketOverview } from "@/lib/types";

import { RadarShell } from "./radar-shell";
import { EtfFundProfilePanel } from "./etf-fund-profile-panel";

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function EtfPriceCurve({ research }: { research: EtfResearch }) {
  const points = research.price_history.points;
  const closes = points.map((point) => point.close);
  const low = Math.min(...closes);
  const high = Math.max(...closes);
  const path = closes
    .map((close, index) => {
      const x = (index / Math.max(closes.length - 1, 1)) * 100;
      const y = 86 - ((close - low) / Math.max(high - low, 1)) * 72;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  const rangeChange = closes.length > 1 ? (closes.at(-1)! / closes[0] - 1) * 100 : 0;
  return (
    <section className="rotation-history panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">PUBLIC ETF HISTORY</span>
          <h2>ETF 公开价格历史</h2>
        </div>
        <span className="quality-tag">{points.length} 个交易日</span>
      </div>
      <div className="rotation-curve">
        <strong>{research.price_history.source}</strong>
        <svg aria-label="ETF 公开价格历史曲线" role="img" viewBox="0 0 100 100">
          <path className="rotation-curve__grid" d="M 0 86 L 100 86" />
          <path className="rotation-curve__line" d={path} />
        </svg>
        <p>区间 {signed(rangeChange)}% · 最近收盘 {closes.at(-1)?.toFixed(3)}</p>
      </div>
    </section>
  );
}

export function EtfResearchPageView({
  overview,
  research,
}: {
  overview: MarketOverview;
  research: EtfResearch;
}) {
  return (
    <RadarShell active="sectors" overview={overview}>
      <header className="page-lead">
        <span>ETF RESEARCH / SOURCE-LABELED</span>
        <h1>{research.name}</h1>
        <p>代码 {research.code} · 公开行情用于研究核对，不构成买卖建议。</p>
      </header>
      <section className="sector-detail-layout">
        <article className="sector-detail-score panel">
          <span>当日涨跌幅</span>
          <strong className={research.change_pct !== null && research.change_pct < 0 ? "down" : "up"}>
            {research.change_pct === null ? "数据暂缺" : `${signed(research.change_pct)}%`}
          </strong>
          <b>{research.as_of}</b>
        </article>
        <article className="panel detail-card">
          <span className="section-eyebrow">SECTOR MAPPING AUDIT</span>
          <h2>板块关联与校验</h2>
          <div className="detail-list">
            {research.sector_mappings.length ? (
              research.sector_mappings.map((mapping) => (
                <div key={`${mapping.theme}-${mapping.code}`}>
                  <div>
                    <strong>{mapping.theme}</strong>
                    <small>{mapping.coverage_direction}</small>
                    <small className="etf-verification">{mapping.verification_note}</small>
                  </div>
                  <b>{mapping.verification_state}</b>
                </div>
              ))
            ) : (
              <p>当前热点板块中没有该 ETF 的精确映射记录。</p>
            )}
          </div>
        </article>
      </section>
      <EtfFundProfilePanel profile={research.fund_profile} />
      <EtfPriceCurve research={research} />
    </RadarShell>
  );
}
