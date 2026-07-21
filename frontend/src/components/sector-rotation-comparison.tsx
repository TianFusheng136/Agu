"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchSectorPriceHistory } from "@/lib/api";
import type { SectorPriceHistory } from "@/lib/types";

type SectorIdentity = { id: string; name: string };

function formatPct(value?: number | null) {
  if (value === null || value === undefined) return "暂缺";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function metricClass(value?: number | null) {
  if (value === null || value === undefined || value === 0) return "neutral";
  return value > 0 ? "up" : "down";
}

export function classifyRotationStage(history?: SectorPriceHistory | null) {
  const trend5 = history?.summary?.trend_5d_pct;
  const trend20 = history?.summary?.trend_20d_pct;
  if (trend5 === null || trend5 === undefined || trend20 === null || trend20 === undefined) {
    return "数据不足";
  }
  if (trend5 >= 0 && trend20 >= 0) return "持续走强";
  if (trend5 >= 0 && trend20 < 0) return "短线修复";
  if (trend5 < 0 && trend20 >= 0) return "高位降温";
  return "持续偏弱";
}

function stageExplanation(stage: string) {
  if (stage === "持续走强") return "5日与20日趋势均为正";
  if (stage === "短线修复") return "5日转强，但20日仍为负";
  if (stage === "高位降温") return "20日仍强，但近5日回落";
  if (stage === "持续偏弱") return "5日与20日趋势均为负";
  return "历史样本尚未完整返回";
}

export function SectorRotationComparison({
  sectors,
  initialHistories,
}: {
  sectors: SectorIdentity[];
  initialHistories?: Record<string, SectorPriceHistory>;
}) {
  const [histories, setHistories] = useState<Record<string, SectorPriceHistory>>(
    initialHistories ?? {},
  );
  const [loading, setLoading] = useState(
    sectors.some((sector) => !initialHistories?.[sector.id]),
  );

  useEffect(() => {
    const missing = sectors.filter((sector) => !initialHistories?.[sector.id]);
    if (!missing.length) return;
    let active = true;
    Promise.allSettled(
      missing.map(async (sector) => ({
        id: sector.id,
        history: await fetchSectorPriceHistory(sector.id, 20),
      })),
    ).then((results) => {
      if (!active) return;
      setHistories((current) => {
        const next = { ...current };
        for (const result of results) {
          if (result.status === "fulfilled") {
            next[result.value.id] = result.value.history;
          }
        }
        return next;
      });
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [initialHistories, sectors]);

  const rows = useMemo(
    () =>
      sectors
        .map((sector) => ({ ...sector, history: histories[sector.id] }))
        .sort(
          (left, right) =>
            (right.history?.summary?.relative_strength_pct ?? -Infinity) -
            (left.history?.summary?.relative_strength_pct ?? -Infinity),
        ),
    [histories, sectors],
  );

  return (
    <section className="panel sector-rotation-comparison">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">20-DAY ROTATION MAP</span>
          <h2>热点板块20日轮动对比</h2>
        </div>
        <span className="quality-tag">
          {loading ? "后台读取中" : "真实历史"}
        </span>
      </div>
      <p className="rotation-rule-note">
        按相对上证指数强度排序；阶段只由5日与20日涨跌方向判定，不使用预测。
      </p>
      <div className="rotation-comparison-table">
        <table>
          <thead>
            <tr>
              <th>板块</th>
              <th>轮动阶段</th>
              <th>5日趋势</th>
              <th>20日趋势</th>
              <th>相对强度</th>
              <th>成交额变化</th>
              <th>量能变化</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ id, name, history }) => {
              const summary = history?.summary;
              const stage = classifyRotationStage(history);
              return (
                <tr key={id}>
                  <td>
                    <strong>{name}</strong>
                  </td>
                  <td>
                    <b className={`rotation-stage rotation-stage--${stage}`}>
                      {stage}
                    </b>
                    <small>{stageExplanation(stage)}</small>
                  </td>
                  <td className={metricClass(summary?.trend_5d_pct)}>
                    {formatPct(summary?.trend_5d_pct)}
                  </td>
                  <td className={metricClass(summary?.trend_20d_pct)}>
                    {formatPct(summary?.trend_20d_pct)}
                  </td>
                  <td className={metricClass(summary?.relative_strength_pct)}>
                    {formatPct(summary?.relative_strength_pct)}
                  </td>
                  <td className={metricClass(summary?.turnover_change_pct)}>
                    {formatPct(summary?.turnover_change_pct)}
                  </td>
                  <td className={metricClass(summary?.volume_change_pct)}>
                    {formatPct(summary?.volume_change_pct)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
