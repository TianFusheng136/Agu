import Link from "next/link";

import type {
  MarketOverview,
  SectorFactors,
  SectorOverview,
  SectorPriceHistory,
  SectorRotation,
  StockHistory,
  TechnicalSignalStats,
} from "@/lib/types";
import { marketQualityLabel } from "@/lib/market-quality";

import { KLineChart } from "./kline-chart";
import { LlmStatusPanel } from "./llm-status-panel";
import { MarketSignalPanel } from "./market-signal-panel";
import { RadarShell } from "./radar-shell";
import { SectorEvidencePanel } from "./sector-evidence-panel";
import { SectorPriceHistoryPanel } from "./sector-price-history-panel";
import { SectorRotationComparison } from "./sector-rotation-comparison";

const FACTOR_LABELS: Array<[keyof SectorFactors, string]> = [
  ["breadth", "市场宽度"],
  ["turnover_acceleration", "成交加速"],
  ["relative_strength", "相对强度"],
  ["limit_density", "涨停密度"],
  ["leader_strength", "龙头强度"],
  ["capital_flow", "资金强度"],
  ["catalyst_strength", "催化强度"],
  ["previous_heat", "昨日热度"],
];

function signed(value: number, digits = 2) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function movementClass(value: number) {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

function capitalFlowClass(value: number | null) {
  return value === null ? "neutral" : movementClass(value);
}

function capitalFlowText(value: number | null) {
  return value === null ? "数据源暂缺" : `${signed(value)} 亿`;
}

function directionEvidence(sector: SectorOverview | undefined) {
  if (!sector) return "公开行情尚未形成可验证的关注方向。";
  if (sector.capital_flow_billion === null) {
    return `公开行情显示 ${sector.name} 相对活跃，但资金净流入数据暂缺，不能据此确认主力净流入。`;
  }
  const direction = sector.capital_flow_billion >= 0 ? "净流入" : "净流出";
  return `${sector.name}板块资金${direction}${Math.abs(sector.capital_flow_billion).toFixed(1)}亿元，核心方向为${sector.core_direction}。`;
}

function stageFor(overview: MarketOverview) {
  if (overview.sentiment.score >= 75) return "情绪活跃 · 关注分歧";
  if (overview.sentiment.score >= 60) return "结构性上行 · 主线集中";
  if (overview.sentiment.score >= 45) return "震荡轮动 · 等待聚焦";
  return "情绪偏弱 · 观察修复";
}

function RotationCurve({ rotation }: { rotation?: SectorRotation | null }) {
  const points = rotation?.points ?? [];
  if (points.length < 2) {
    return (
      <div className="rotation-curve">
        <strong>{rotation?.basis === "source-price-history" ? "价格强弱曲线" : "热度曲线"}</strong>
        <p>当前仅有 {points.length} 个真实交易日样本，积累后显示连续曲线。</p>
      </div>
    );
  }
  const scores = points.map((point) => point.strength_score ?? point.heat_score ?? 0);
  const low = Math.min(...scores);
  const high = Math.max(...scores);
  const path = scores
    .map((score, index) => {
      const x = (index / (scores.length - 1)) * 100;
      const y = 86 - ((score - low) / Math.max(high - low, 1)) * 72;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <div className="rotation-curve">
      <strong>{rotation?.basis === "source-price-history" ? "价格强弱曲线" : "热度曲线"}</strong>
      <svg aria-label="板块热度轮动曲线" role="img" viewBox="0 0 100 100">
        <path className="rotation-curve__grid" d="M 0 86 L 100 86" />
        <path className="rotation-curve__line" d={path} />
      </svg>
    </div>
  );
}

function PageLead({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="page-lead">
      <span>{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

function MetricBoard({ overview }: { overview: MarketOverview }) {
  const metrics = overview.metrics;
  return (
    <div className="metric-board metric-ribbon panel">
      <div className="metric-cell">
        <span>上涨 / 下跌</span>
        <strong className={metrics.advancers === null ? "neutral" : "positive"}>
          {metrics.advancers ?? "暂缺"}
        </strong>
        <small>下跌 {metrics.decliners ?? "暂缺"}</small>
      </div>
      <div className="metric-cell">
        <span>涨停 / 跌停</span>
        <strong>
          <i className="positive">{metrics.limit_up_count}</i>
          <em>/</em>
          <i className="negative">{metrics.limit_down_count}</i>
        </strong>
        <small>连板高度 {metrics.max_board_height} 板</small>
      </div>
      <div className="metric-cell">
        <span>两市成交额</span>
        <strong>{metrics.turnover_billion.toFixed(1)}</strong>
        <small
          className={
            metrics.turnover_change_pct === null
              ? "neutral"
              : movementClass(metrics.turnover_change_pct)
          }
        >
          {metrics.turnover_change_pct === null
            ? "亿元 · 对比暂缺"
            : `亿元 · 较前一交易日 ${signed(metrics.turnover_change_pct, 1)}%`}
        </small>
      </div>
      <div className="metric-cell">
        <span>炸板率</span>
        <strong>{metrics.broken_board_rate.toFixed(1)}%</strong>
        <small>情绪分歧参考</small>
      </div>
      <div className="metric-cell">
        <span>热点集中度</span>
        <strong>{metrics.hotspot_concentration.toFixed(1)}%</strong>
        <small>前三方向聚焦程度</small>
      </div>
      <div className="metric-cell">
        <span>北向资金</span>
        <strong className="metric-status">数据状态</strong>
        <small>{metrics.northbound_status || "数据源暂缺"}</small>
      </div>
    </div>
  );
}

export function MarketPageView({ overview }: { overview: MarketOverview }) {
  const lead = overview.hot_sectors[0];
  const advancers = overview.metrics.advancers ?? 0;
  const decliners = overview.metrics.decliners ?? 0;
  const breadthTotal = advancers + decliners;
  const advanceShare = breadthTotal > 0 ? (advancers / breadthTotal) * 100 : 50;
  const riskState =
    overview.metrics.broken_board_rate >= 30 || overview.metrics.limit_down_count >= 30
      ? "分歧升温"
      : overview.sentiment.score >= 60
        ? "结构占优"
        : "谨慎观察";
  return (
    <RadarShell active="market" overview={overview}>
      <section className="market-command-hero panel">
        <div className="market-command-copy">
          <span className="section-eyebrow">LIVE MARKET MAP · 01</span>
          <h1>市场全景</h1>
          <h2>市场脉冲</h2>
          <p className="market-command-copy__stage">{stageFor(overview)}</p>
          <p className="market-command-copy__evidence">{directionEvidence(lead)}</p>
          <div className="market-command-tags" aria-label="当前热点方向">
            {overview.hot_sectors.map((sector) => (
              <Link href={`/sectors/${sector.id}`} key={sector.id}>
                <span>{sector.heat.stage}</span>
                {sector.name}
              </Link>
            ))}
          </div>
          <div className="market-command-meta">
            <span>{marketQualityLabel(overview.data_quality)}</span>
            <span>{overview.market_status}</span>
            <span>{riskState}</span>
          </div>
        </div>
        <aside className="market-pulse-card" aria-label="实时市场强度">
          <div
            className="market-pulse-orb"
            style={
              {
                "--pulse-score": `${overview.sentiment.score * 3.6}deg`,
              } as React.CSSProperties
            }
          >
            <div>
              <small>MARKET PULSE</small>
              <strong>{overview.sentiment.score.toFixed(1)}</strong>
              <span>{overview.sentiment.level}</span>
            </div>
          </div>
          <div className="market-breadth">
            <div>
              <span>上涨宽度</span>
              <strong>{overview.metrics.advancers ?? "暂缺"}</strong>
            </div>
            <div>
              <span>下跌宽度</span>
              <strong>{overview.metrics.decliners ?? "暂缺"}</strong>
            </div>
            <i style={{ "--advance-share": `${advanceShare}%` } as React.CSSProperties} />
          </div>
        </aside>
      </section>

      <MetricBoard overview={overview} />

      <section className="market-insight-row">
        <article className="market-insight-card panel">
          <span>资金关注方向</span>
          <strong>{lead?.name ?? "暂未形成"}</strong>
          <p>{lead?.core_direction ?? "等待公开行情形成可验证方向"}</p>
        </article>
        <article className="market-insight-card panel">
          <span>市场风险天气</span>
          <strong>{riskState}</strong>
          <p>
            炸板率 {overview.metrics.broken_board_rate.toFixed(1)}% · 跌停 {overview.metrics.limit_down_count} 家
          </p>
        </article>
        <article className="market-insight-card panel">
          <span>热点集中度</span>
          <strong>{overview.metrics.hotspot_concentration.toFixed(1)}%</strong>
          <p>仅描述前三方向聚焦程度，不代表后续收益。</p>
        </article>
      </section>

      <section className="market-direction-atlas" aria-label="资金方向地图">
        <div className="market-section-heading">
          <div>
            <span className="section-eyebrow">CAPITAL CONSTELLATION</span>
            <h2>资金方向地图</h2>
          </div>
          <Link className="text-link" href="/sectors">
            查看完整轮动证据 →
          </Link>
        </div>
        <div className="market-direction-grid">
          {overview.hot_sectors.map((sector, index) => (
            <Link
              className="market-direction-card panel"
              href={`/sectors/${sector.id}`}
              key={sector.id}
            >
              <div className="market-direction-card__top">
                <span>0{index + 1}</span>
                <i>{sector.heat.stage}</i>
              </div>
              <h3>{sector.name}</h3>
              <p>{sector.core_direction}</p>
              <div className="market-direction-card__score">
                <strong>{sector.heat.score.toFixed(0)}</strong>
                <span>HEAT</span>
                <i style={{ "--heat": `${sector.heat.score}%` } as React.CSSProperties} />
              </div>
              <dl>
                <div>
                  <dt>今日涨幅</dt>
                  <dd className={movementClass(sector.change_pct)}>
                    {signed(sector.change_pct)}%
                  </dd>
                </div>
                <div>
                  <dt>行业资金净额</dt>
                  <dd className={capitalFlowClass(sector.capital_flow_billion)}>
                    {capitalFlowText(sector.capital_flow_billion)}
                  </dd>
                </div>
                <div>
                  <dt>代表股票</dt>
                  <dd>{sector.stocks[0]?.name ?? "暂缺"}</dd>
                </div>
              </dl>
              <b>打开证据页 <span aria-hidden="true">↗</span></b>
            </Link>
          ))}
        </div>
      </section>
    </RadarShell>
  );
}

export function SectorsPageView({ overview }: { overview: MarketOverview }) {
  return (
    <RadarShell active="sectors" overview={overview}>
      <PageLead
        eyebrow="02 / CAPITAL FOCUS"
        title="热点板块"
        description="不再把多个板块塞进小卡片。每个板块占一整行，并可进入独立页面查看代表股票、轮动、催化与风险。"
      />
      <SectorRotationComparison
        sectors={overview.hot_sectors.map(({ id, name }) => ({ id, name }))}
      />
      <section className="sector-atlas" aria-label="热点板块图谱">
        <div className="market-section-heading">
          <div>
            <span className="section-eyebrow">SECTOR ATLAS</span>
            <h2>热点结构图谱</h2>
          </div>
          <p>从热度、涨幅、资金与代表股四个维度交叉查看，不把单一涨幅当作主线。</p>
        </div>
        <div className="sector-atlas__grid">
        {overview.hot_sectors.map((sector, index) => (
          <article className="sector-atlas-card panel" key={sector.id}>
            <div className="sector-atlas-card__header">
              <span className="sector-atlas-card__rank">0{index + 1}</span>
              <span className="stage-badge">{sector.heat.stage}</span>
            </div>
            <div className="sector-atlas-card__title">
              <div>
                <h2>{sector.name}</h2>
                <p>{sector.core_direction}</p>
              </div>
              <div
                className="sector-atlas-card__heat"
                style={{ "--heat": `${sector.heat.score}%` } as React.CSSProperties}
                aria-label={`板块热度 ${sector.heat.score.toFixed(1)}`}
              >
                <strong>{sector.heat.score.toFixed(0)}</strong>
                <span>HEAT</span>
              </div>
            </div>
            <p className="sector-atlas-card__summary">{sector.summary}</p>
            <dl>
                <div>
                  <dt>今日涨幅</dt>
                  <dd className={movementClass(sector.change_pct)}>
                    {signed(sector.change_pct)}%
                  </dd>
                </div>
                <div>
                  <dt>成交金额</dt>
                  <dd>
                    {sector.turnover_billion > 0
                      ? `${sector.turnover_billion.toFixed(1)} 亿`
                      : "数据暂缺"}
                  </dd>
                </div>
                <div>
                  <dt>资金流向</dt>
                  <dd className={capitalFlowClass(sector.capital_flow_billion)}>
                    {capitalFlowText(sector.capital_flow_billion)}
                  </dd>
                </div>
                <div>
                  <dt>代表股票</dt>
                  <dd>{sector.stocks[0]?.name ?? "数据暂缺"}</dd>
                </div>
            </dl>
            <div className="sector-atlas-card__footer">
              <span>{sector.risks[0] ?? "等待更多交易日验证持续性"}</span>
              <Link href={`/sectors/${sector.id}`} prefetch={false}>
                查看板块详情 →
              </Link>
            </div>
          </article>
        ))}
        </div>
      </section>
    </RadarShell>
  );
}

export function StocksPageView({ overview }: { overview: MarketOverview }) {
  const stocks = overview.hot_sectors.flatMap((sector) =>
    sector.stocks.map((stock) => ({ ...stock, sector: sector.name })),
  );
  return (
    <RadarShell active="stocks" overview={overview}>
      <PageLead
        eyebrow="03 / CORE OBSERVATION"
        title="核心股票观察"
        description="展示热点板块中的代表股票与相对表现。点击任意股票进入独立详情页查看 K 线和结构化风险。"
      />
      <MarketSignalPanel />
      <section className="stocks-page panel">
        <div className="stock-row stock-head">
          <span>股票</span>
          <span>所属方向</span>
          <span>相对表现</span>
          <span>结构状态</span>
          <span>涨跌幅</span>
        </div>
        {stocks.map((stock) => (
          <Link
            className="stock-observation stock-link-row"
            href={`/stocks/${stock.code}`}
            key={`${stock.sector}-${stock.code}`}
          >
            <div className="stock-row">
              <span>
                <strong>{stock.name}</strong>
                <small>{stock.code}</small>
              </span>
              <span>
                <strong>{stock.direction}</strong>
                <small>{stock.sector}</small>
              </span>
              <span>{stock.relative_performance}</span>
              <span>{stock.capital_status}</span>
              <span className={movementClass(stock.change_pct)}>
                {signed(stock.change_pct)}%
              </span>
            </div>
            <div className="stock-context">
              <p>
                <span>表现原因</span>
                {stock.reason}
              </p>
              <p>
                <span>风险因素</span>
                {stock.risk}
              </p>
            </div>
          </Link>
        ))}
      </section>
    </RadarShell>
  );
}

export function BriefPageView({ overview }: { overview: MarketOverview }) {
  const lead = overview.hot_sectors[0];
  const riskSummary = lead?.risks.join("；") || "暂无明确风险信息";
  return (
    <RadarShell active="brief" overview={overview}>
      <PageLead
        eyebrow="04 / AI DAILY BRIEF"
        title="今日 A 股短线观察"
        description="数字由规则与公开行情锁定，AI 只负责把资金方向、板块结构和风险翻译成易读结论。"
      />
      <section className="brief-command-grid" aria-label="结构化市场简报">
        <article className="brief-command-card brief-command-card--primary panel">
          <div className="brief-command-card__index">01</div>
          <span className="section-eyebrow">MARKET CORE</span>
          <h2>今日市场核心</h2>
          <strong>{stageFor(overview)}</strong>
          <p>当前市场情绪为{overview.sentiment.level}，情绪分数 {overview.sentiment.score.toFixed(1)}。</p>
          <div className="brief-pulse-line">
            <i style={{ "--brief-score": `${overview.sentiment.score}%` } as React.CSSProperties} />
          </div>
        </article>

        <article className="brief-command-card panel">
          <div className="brief-command-card__index">02</div>
          <span className="section-eyebrow">CAPITAL FOCUS</span>
          <h2>市场关注方向</h2>
          <strong>{lead?.name ?? "等待公开行情形成方向"}</strong>
          <p>{directionEvidence(lead)}</p>
        </article>

        <article className="brief-command-card panel">
          <div className="brief-command-card__index">03</div>
          <span className="section-eyebrow">HOT SECTORS</span>
          <h2>热点方向</h2>
          <div className="brief-sector-stack">
            {overview.hot_sectors.map((sector) => (
              <Link href={`/sectors/${sector.id}`} key={sector.id}>
                <span>{sector.name}</span>
                <strong>{sector.heat.score.toFixed(0)}</strong>
                <i style={{ "--heat": `${sector.heat.score}%` } as React.CSSProperties} />
              </Link>
            ))}
          </div>
        </article>

        <article className="brief-command-card brief-command-card--risk panel">
          <div className="brief-command-card__index">04</div>
          <span className="section-eyebrow">RISK CONTROL</span>
          <h2>风险提示</h2>
          <strong>{overview.metrics.broken_board_rate.toFixed(1)}% 炸板率</strong>
          <p>{riskSummary}。</p>
          <div className="brief-boundary">
            <i aria-hidden="true" />
            数字由规则与公开行情锁定，AI 只负责解释，不提供买卖建议
          </div>
        </article>
      </section>
      <LlmStatusPanel />
    </RadarShell>
  );
}

export function SectorDetailPageView({
  overview,
  sector,
  rotation,
  priceHistory,
}: {
  overview: MarketOverview;
  sector: SectorOverview;
  rotation?: SectorRotation | null;
  priceHistory?: SectorPriceHistory | null;
}) {
  return (
    <RadarShell active="sectors" overview={overview}>
      <PageLead
        eyebrow="SECTOR EVIDENCE"
        title={sector.name}
        description={`${sector.core_direction}。${sector.summary}`}
      />
      <section className="sector-detail-layout">
        <article className="sector-detail-score panel">
          <span>板块热度</span>
          <strong>{sector.heat.score.toFixed(1)}</strong>
          <b>{sector.heat.stage}</b>
          <dl>
            <div>
              <dt>今日涨幅</dt>
              <dd className={movementClass(sector.change_pct)}>
                {signed(sector.change_pct)}%
              </dd>
            </div>
            <div>
              <dt>成交金额</dt>
              <dd>
                {sector.turnover_billion > 0
                  ? `${sector.turnover_billion.toFixed(1)} 亿`
                  : "数据暂缺"}
              </dd>
            </div>
            <div>
              <dt>{sector.capital_flow_label}</dt>
              <dd className={capitalFlowClass(sector.capital_flow_billion)}>
                {capitalFlowText(sector.capital_flow_billion)}
              </dd>
            </div>
          </dl>
        </article>
        <article className="factor-detail panel">
          <div className="panel-heading">
            <div>
              <span className="section-eyebrow">RULE SCORE</span>
              <h2>热度构成</h2>
            </div>
          </div>
          <div className="factor-grid factor-grid--large">
            {FACTOR_LABELS.map(([key, label]) => (
              <div className="factor-item" key={key}>
                <div>
                  <span>{label}</span>
                  <strong>{sector.factors[key].toFixed(0)}</strong>
                </div>
                <i
                  style={
                    {
                      "--factor": `${sector.factors[key]}%`,
                    } as React.CSSProperties
                  }
                />
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="sector-data-foundation panel">
        <div>
          <span className="section-eyebrow">CLASSIFICATION & DATA</span>
          <h2>板块分类与数据边界</h2>
        </div>
        <dl>
          <div>
            <dt>板块分类口径</dt>
            <dd>{sector.classification.source_name}</dd>
            <small>{sector.classification.note}</small>
          </div>
          <div>
            <dt>资金字段</dt>
            <dd>{sector.capital_flow_label}</dd>
            <small>该字段仅描述公开行业资金流，不等同于主力净流入。</small>
          </div>
          <div>
            <dt>轮动历史</dt>
            <dd>
              {rotation?.status === "ready"
                ? rotation.basis === "source-price-history"
                  ? `已读取 ${rotation.data_points} 个真实交易日`
                  : `已积累 ${rotation.data_points} 个交易日`
                : `样本积累中 ${rotation?.data_points ?? 0} / ${
                    rotation?.minimum_required_points ?? 5
                  }`}
            </dd>
            <small>
              {rotation?.status === "ready"
                ? rotation.basis === "source-price-history"
                  ? `${rotation.basis_note} 综合快照已实际积累 ${rotation.snapshot_data_points} 日。`
                  : `展示最近 ${rotation.window_days} 个交易日的真实快照。`
                : "只保留实际记录，不为公开行情补造历史数据。"}
            </small>
          </div>
        </dl>
      </section>

      <section className="rotation-history panel">
        <div className="panel-heading">
          <div>
            <span className="section-eyebrow">SECTOR ROTATION</span>
            <h2>板块轮动历史</h2>
          </div>
          <span className="quality-tag">
            {rotation?.status === "ready"
              ? rotation.basis === "source-price-history"
                ? "真实价格历史"
                : "真实快照"
              : "样本积累中"}
          </span>
        </div>
        <RotationCurve rotation={rotation} />
        {rotation?.points.length ? (
          <div className="rotation-points" aria-label="板块轮动历史数据">
            {rotation.points.map((point) => (
              <div key={point.as_of}>
                <small>{point.as_of.slice(5, 10)}</small>
                <strong>{(point.strength_score ?? point.heat_score ?? 0).toFixed(1)}</strong>
                <span className={movementClass(point.change_pct)}>
                  {signed(point.change_pct)}%
                </span>
                <em>
                  {point.basis === "source-price-history"
                    ? `相对强度 ${
                        point.relative_strength_pct === null
                          ? "暂缺"
                          : `${point.relative_strength_pct >= 0 ? "+" : ""}${point.relative_strength_pct.toFixed(2)}%`
                      }`
                    : `热度排名 ${point.rank}`}
                </em>
              </div>
            ))}
          </div>
        ) : (
          <p className="rotation-empty">
            轮动记录将在每个交易日自动积累；当前不会使用演示历史替代真实数据。
          </p>
        )}
      </section>

      <SectorPriceHistoryPanel
        initialHistory={priceHistory}
        sectorId={sector.id}
      />

      <SectorEvidencePanel sectorId={sector.id} />

      <section className="detail-columns">
        <article className="panel detail-card">
          <span className="section-eyebrow">核心股票</span>
          <h2>板块代表观察</h2>
          <div className="detail-list">
            {sector.stocks.map((stock) => (
              <Link href={`/stocks/${stock.code}`} key={stock.code}>
                <div>
                  <strong>{stock.name}</strong>
                  <small>{stock.code} · {stock.relative_performance}</small>
                </div>
                <b className={movementClass(stock.change_pct)}>
                  {signed(stock.change_pct)}%
                </b>
              </Link>
            ))}
          </div>
        </article>
        <article className="panel detail-card">
          <span className="section-eyebrow">催化与风险</span>
          <h2>当前观察结论</h2>
          <ul className="signal-list catalyst-list">
            {sector.catalysts.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <ul className="signal-list risk-list">
            {sector.risks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>

      <details className="panel secondary-tools">
        <summary>相关 ETF 工具</summary>
        <div className="detail-list">
          {sector.etfs.length ? (
            sector.etfs.map((etf) => (
              <div key={etf.code}>
                <div>
                  <strong>{etf.name}</strong>
                  <small>{etf.coverage_direction}</small>
                  <small className="etf-verification">{etf.verification_note}</small>
                </div>
                <b>{etf.code}</b>
              </div>
            ))
          ) : (
            <p>暂无名称精确匹配的 ETF</p>
          )}
        </div>
      </details>
    </RadarShell>
  );
}

export function SectorDetailUnavailablePageView({
  overview,
}: {
  overview: MarketOverview;
}) {
  return (
    <RadarShell active="sectors" overview={overview}>
      <PageLead
        eyebrow="SECTOR DETAIL"
        title="板块详情暂时不可用"
        description="公开行情正在更新，请返回热点板块后重试。"
      />
      <section className="sector-unavailable panel">
        <span className="section-eyebrow">PUBLIC DATA REFRESHING</span>
        <h2>请从最新热点列表重新进入</h2>
        <p>系统不会用旧快照或演示数据替代当前公开行情。</p>
        <Link href="/sectors">返回热点板块</Link>
      </section>
    </RadarShell>
  );
}

export function StockDetailPageView({
  overview,
  history,
  technical,
}: {
  overview: MarketOverview;
  history: StockHistory;
  technical: TechnicalSignalStats;
}) {
  const observation = overview.hot_sectors
    .flatMap((sector) =>
      sector.stocks.map((stock) => ({ ...stock, sector: sector.name })),
    )
    .find((stock) => stock.code === history.code);
  const latest = history.candles.at(-1);
  return (
    <RadarShell active="stocks" overview={overview}>
      <PageLead
        eyebrow="STOCK RESEARCH"
        title={`${history.name} · ${history.code}`}
        description="K 线用于查看历史价格与成交结构；个股归因和风险只在有可验证板块映射时展示。"
      />
      <section className="stock-detail-summary panel">
        <div>
          <span>最新收盘</span>
          <strong>{latest?.close.toFixed(2) ?? "—"}</strong>
        </div>
        <div>
          <span>当日涨跌</span>
          <strong
            className={
              latest?.change_pct === undefined || latest.change_pct === null
                ? "neutral"
                : movementClass(latest.change_pct)
            }
          >
            {latest?.change_pct === undefined || latest.change_pct === null
              ? "数据暂缺"
              : `${signed(latest.change_pct)}%`}
          </strong>
        </div>
        <div>
          <span>所属方向</span>
          <strong>{observation?.direction ?? "热点映射暂缺"}</strong>
        </div>
        <div>
          <span>相对板块</span>
          <strong>{observation?.relative_performance ?? "数据暂缺"}</strong>
        </div>
      </section>
      <section className="technical-signals panel">
        <div className="panel-heading">
          <div>
            <span className="section-eyebrow">TECHNICAL STATISTICS</span>
            <h2>周K与技术信号统计</h2>
          </div>
          <span className="quality-tag">{technical.sample_size} 根日K</span>
        </div>
        <div className="technical-signals__grid">
          <article>
            <span>MACD</span>
            <strong>{technical.macd.state}</strong>
            <p>
              DIF {technical.macd.dif?.toFixed(4) ?? "暂缺"} / DEA{" "}
              {technical.macd.dea?.toFixed(4) ?? "暂缺"}
            </p>
          </article>
          <article>
            <span>KDJ</span>
            <strong>{technical.kdj.state}</strong>
            <p>
              K {technical.kdj.k?.toFixed(2) ?? "暂缺"} / D{" "}
              {technical.kdj.d?.toFixed(2) ?? "暂缺"} / J{" "}
              {technical.kdj.j?.toFixed(2) ?? "暂缺"}
            </p>
          </article>
          <article>
            <span>周K结构</span>
            <strong>{technical.weekly.state}</strong>
            <p>
              周涨跌 {technical.weekly.latest_change_pct === null ? "暂缺" : `${signed(technical.weekly.latest_change_pct)}%`}
              {" · "}量比 {technical.weekly.volume_ratio?.toFixed(2) ?? "暂缺"}
            </p>
          </article>
        </div>
        <p className="technical-signals__boundary">
          白话理解：MACD 看趋势变化，KDJ 看短期位置，周K看一周走势和成交量。
        </p>
        <p className="technical-signals__boundary">{technical.disclaimer}</p>
      </section>
      <KLineChart history={history} />
      <section className="stock-research-grid">
        <article className="panel detail-card">
          <span className="section-eyebrow">表现原因</span>
          <h2>{observation?.sector ?? "公开行情观察"}</h2>
          <p>{observation?.reason ?? "当前股票不在今日热点板块核心观察列表中。"}</p>
        </article>
        <article className="panel detail-card">
          <span className="section-eyebrow">风险因素</span>
          <h2>研究边界</h2>
          <p>{observation?.risk ?? "仅展示历史行情，不根据 K 线生成买卖结论。"}</p>
        </article>
      </section>
    </RadarShell>
  );
}
