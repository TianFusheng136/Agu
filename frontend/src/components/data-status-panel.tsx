"use client";

import { useEffect, useState } from "react";

import { fetchMarketDataStatus } from "@/lib/api";
import type { MarketDataStatus } from "@/lib/types";

const FIELD_LABELS: Record<string, string> = {
  advancers_decliners: "上涨 / 下跌家数",
  turnover_change: "成交额变化",
  northbound: "北向资金",
  sector_capital_flow: "行业资金数据",
};

const QUALITY_LABELS: Record<string, string> = {
  "live-public": "公开行情",
  "refreshing-live-public": "后台更新中",
  demo: "演示数据",
};

export function DataStatusPanel() {
  const [status, setStatus] = useState<MarketDataStatus | null>(null);

  useEffect(() => {
    fetchMarketDataStatus()
      .then((payload) => {
        setStatus(
          Array.isArray(payload.fields) && Array.isArray(payload.sources)
            ? payload
            : null,
        );
      })
      .catch(() => setStatus(null));
  }, []);

  return (
    <section className="data-status panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">DATA QUALITY MONITOR</span>
          <h2>数据来源与缺失状态</h2>
        </div>
        <span className="quality-tag">
          {status ? (QUALITY_LABELS[status.data_quality] ?? status.data_quality) : "读取中"}
        </span>
      </div>
      {status ? (
        <>
          <div className="data-status__fields">
            {status.fields.map((field) => (
              <div key={field.field}>
                <span>{FIELD_LABELS[field.field] ?? field.field}</span>
                <b className={field.state === "available" ? "up" : "down"}>
                  {field.state === "available" ? "已获取" : "暂缺"}
                </b>
              </div>
            ))}
          </div>
          <details className="data-status__sources">
            <summary><span>数据源 {status.sources.length} 个</span><span>查看来源明细</span></summary>
            <ul>
              {status.sources.map((source) => (
                <li key={`${source.category}-${source.name}`}>
                  <strong>{source.name}</strong>
                  <small>{source.updated_at}</small>
                </li>
              ))}
            </ul>
          </details>
        </>
      ) : (
        <p>数据状态暂时不可用；不以缓存或演示值替代。</p>
      )}
    </section>
  );
}
