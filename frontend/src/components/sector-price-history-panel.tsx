"use client";

import { useEffect, useState } from "react";

import { fetchSectorPriceHistory } from "@/lib/api";
import type { SectorPriceHistory } from "@/lib/types";

function formatPct(value?: number | null) {
  if (value === null || value === undefined) return "暂缺";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function metricClass(value?: number | null) {
  if (value === null || value === undefined || value === 0) return "neutral";
  return value > 0 ? "up" : "down";
}

function relativeStrengthText(history: SectorPriceHistory) {
  const value = history.summary?.relative_strength_pct;
  const benchmark = history.summary?.benchmark_name ?? "市场基准";
  if (value === null || value === undefined) return `相对${benchmark}数据暂缺`;
  if (Math.abs(value) < 0.005) return `与${benchmark}基本持平`;
  return `${value > 0 ? "强于" : "弱于"}${benchmark} ${formatPct(value)}`;
}

function PriceHistoryCurve({
  history,
  label = "公开价格历史",
}: {
  history?: SectorPriceHistory | null;
  label?: string;
}) {
  const points = history?.points ?? [];
  if (!history || history.state === "unavailable") {
    return (
      <div className="rotation-curve">
        <strong>{label}</strong>
        <p>{history?.message ?? "正在读取公开板块历史行情…"}</p>
      </div>
    );
  }
  if (points.length < 2) {
    return (
      <div className="rotation-curve">
        <strong>{label}</strong>
        <p>已匹配公开板块，但可展示历史样本不足。</p>
      </div>
    );
  }
  const values = points.map((point) => point.close);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const path = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 86 - ((value - low) / Math.max(high - low, 1)) * 72;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  const change = ((values.at(-1)! / values[0] - 1) * 100).toFixed(2);
  return (
    <div className="rotation-curve">
      <strong>{label}</strong>
      <svg aria-label="板块公开价格历史曲线" role="img" viewBox="0 0 100 100">
        <path className="rotation-curve__grid" d="M 0 86 L 100 86" />
        <path className="rotation-curve__line" d={path} />
      </svg>
      <p>{`${points.length} 个交易日 · 区间 ${Number(change) >= 0 ? "+" : ""}${change}%`}</p>
    </div>
  );
}

export function SectorPriceHistoryPanel({
  sectorId,
  initialHistory = null,
}: {
  sectorId: string;
  initialHistory?: SectorPriceHistory | null;
}) {
  const [history, setHistory] = useState<SectorPriceHistory | null>(initialHistory);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialHistory) return;
    let active = true;
    fetchSectorPriceHistory(sectorId)
      .then((payload) => active && setHistory(payload))
      .catch((reason) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "历史行情接口暂时不可用。");
      });
    return () => {
      active = false;
    };
  }, [initialHistory, sectorId]);

  const stateLabel = history
    ? history.state === "available"
      ? "来源已匹配"
      : "暂不可用"
    : error
      ? "暂不可用"
      : "后台加载中";
  const summary = history?.summary;

  return (
    <section className="rotation-history panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">SOURCE-LABELED HISTORY</span>
          <h2>20日板块强弱</h2>
        </div>
        <span className="quality-tag">{stateLabel}</span>
      </div>
      <PriceHistoryCurve history={history} />
      {history?.state === "available" && summary ? (
        <div className="history-metrics">
          <div>
            <span>20日趋势</span>
            <strong className={metricClass(summary.trend_20d_pct)}>
              {formatPct(summary.trend_20d_pct)}
            </strong>
          </div>
          <div>
            <span>5日趋势</span>
            <strong className={metricClass(summary.trend_5d_pct)}>
              {formatPct(summary.trend_5d_pct)}
            </strong>
          </div>
          <div>
            <span>成交额变化</span>
            <strong className={metricClass(summary.turnover_change_pct)}>
              {formatPct(summary.turnover_change_pct)}
            </strong>
            <small>
              {summary.latest_turnover_billion === null
                ? "成交额暂缺"
                : `${summary.latest_turnover_billion.toFixed(2)} 亿元`}
            </small>
          </div>
          <div>
            <span>量能变化</span>
            <strong className={metricClass(summary.volume_change_pct)}>
              {formatPct(summary.volume_change_pct)}
            </strong>
          </div>
          <div>
            <span>相对强度</span>
            <strong className={metricClass(summary.relative_strength_pct)}>
              {relativeStrengthText(history)}
            </strong>
          </div>
        </div>
      ) : null}
      {history?.state === "available" && history.points.length ? (
        <details className="history-table">
          <summary>{history.points.length}个交易日明细</summary>
          <div>
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>涨跌幅</th>
                  <th>成交额</th>
                  <th>成交额变化</th>
                  <th>量能变化</th>
                  <th>相对强度</th>
                </tr>
              </thead>
              <tbody>
                {[...history.points].reverse().map((point) => (
                  <tr key={point.date}>
                    <td>{point.date}</td>
                    <td className={metricClass(point.change_pct)}>
                      {formatPct(point.change_pct)}
                    </td>
                    <td>
                      {point.turnover_billion === null ||
                      point.turnover_billion === undefined
                        ? "暂缺"
                        : `${point.turnover_billion.toFixed(2)}亿`}
                    </td>
                    <td className={metricClass(point.turnover_change_pct)}>
                      {formatPct(point.turnover_change_pct)}
                    </td>
                    <td className={metricClass(point.volume_change_pct)}>
                      {formatPct(point.volume_change_pct)}
                    </td>
                    <td className={metricClass(point.relative_strength_pct)}>
                      {formatPct(point.relative_strength_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
      <p className="rotation-empty">
        {history?.message ?? (error || "历史行情正在后台加载，不影响板块详情浏览。")}
      </p>
      {history?.source_name ? (
        <small className="history-source">
          {history.source} · {history.source_name}
        </small>
      ) : null}
    </section>
  );
}
