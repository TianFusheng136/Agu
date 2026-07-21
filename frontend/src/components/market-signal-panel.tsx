"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { fetchMarketSignals } from "@/lib/api";
import type { MarketSignalScan } from "@/lib/types";

const BUCKET_LABELS: Record<string, string> = {
  macd_golden_cross: "MACD 金叉",
  macd_death_cross: "MACD 死叉",
  kdj_golden_cross: "KDJ 金叉",
  kdj_death_cross: "KDJ 死叉",
  weekly_volume_anomaly: "周K放量异动",
};

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatCachedAt(value: string) {
  const match = value.match(/^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return match ? `${match[1]}/${match[2]} ${match[3]}:${match[4]}` : value;
}

export function MarketSignalPanel() {
  const [scan, setScan] = useState<MarketSignalScan | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshError, setRefreshError] = useState("");
  const initialRequestStarted = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setRefreshError("");
    try {
      const payload = await fetchMarketSignals();
      if (!Array.isArray(payload.items) || !Array.isArray(payload.buckets)) {
        throw new Error("invalid signal payload");
      }
      setScan(payload);
    } catch {
      setRefreshError("本次刷新失败，继续显示上次成功结果。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialRequestStarted.current) return;
    initialRequestStarted.current = true;
    fetchMarketSignals()
      .then((payload) => {
        setScan(Array.isArray(payload.items) && Array.isArray(payload.buckets) ? payload : null);
      })
      .catch(() => {
        setScan(null);
        setRefreshError("首次加载失败，当前没有可保留的上次成功结果。");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <section className="market-signals panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">MARKET SIGNAL SCAN</span>
          <h2>热点代表股异动统计</h2>
        </div>
        <div className="market-signals__actions">
          <span className="quality-tag">
            {loading
              ? "LOADING"
              : `${scan?.scanned_count ?? 0} 只${scan?.cached_count ? ` · ${scan.cached_count} 缓存` : ""}`}
          </span>
          <button disabled={loading} onClick={() => void load()} type="button">刷新信号</button>
        </div>
      </div>
      <p className="market-signals__boundary">仅扫描当前热点板块代表股（每个板块最多 2 只），不是全市场选股器；信号仅描述历史价格与成交结构。</p>
      <p className="market-signals__boundary">
        白话理解：MACD 看趋势变化，KDJ 看短期位置，周K看一周走势和成交量；这些统计不是买卖点。
      </p>
      {scan ? (
        <>
          <div className="market-signals__buckets">
            {scan.buckets.map((bucket) => (
              <div key={bucket.id}>
                <span>{BUCKET_LABELS[bucket.id] ?? bucket.label}</span>
                <strong>{bucket.count}</strong>
              </div>
            ))}
          </div>
          {scan.items.length ? (
            <div className="market-signals__list">
              {scan.items.map((item) => (
                <Link href={`/stocks/${item.code}`} key={item.code}>
                  <div>
                    <strong>{item.name}</strong>
                    <small>{item.code} · {item.sector} · {item.as_of}</small>
                    {item.data_state === "cached" && item.cached_at ? (
                      <small>上次成功数据 · {formatCachedAt(item.cached_at)}</small>
                    ) : null}
                  </div>
                  <span className={item.change_pct >= 0 ? "up" : "down"}>{signed(item.change_pct)}</span>
                  <em>{item.macd_state}</em>
                  <em>{item.kdj_state}</em>
                  <em>{item.weekly_state}</em>
                </Link>
              ))}
            </div>
          ) : (
            <p className="inline-empty">当前公开 K线数据未返回可计算的代表股信号。</p>
          )}
          {scan.query_failures.length ? (
            <p className="market-signals__failure">
              {scan.cached_count
                ? `${scan.query_failures.length} 只代表股本次刷新失败，已明确保留上次成功的技术结构。`
                : `${scan.query_failures.length} 只代表股公开 K线暂缺，没有可用的上次成功结果。`}
            </p>
          ) : null}
        </>
      ) : (
        <p className="inline-empty">信号扫描暂不可用；没有可保留的上次成功结果。</p>
      )}
      {refreshError ? <p className="market-signals__failure">{refreshError}</p> : null}
    </section>
  );
}
