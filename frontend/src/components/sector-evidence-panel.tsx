"use client";

import { useEffect, useState } from "react";

import { fetchSectorEvidence } from "@/lib/api";
import type { SectorEvidence } from "@/lib/types";

function formatCachedAt(value: string) {
  const match = value.match(/^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return match ? `${match[1]}/${match[2]} ${match[3]}:${match[4]}` : value;
}

export function SectorEvidencePanel({ sectorId }: { sectorId: string }) {
  const [evidence, setEvidence] = useState<SectorEvidence | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchSectorEvidence(sectorId)
      .then((payload) => active && setEvidence(payload))
      .catch((reason) => active && setError(reason instanceof Error ? reason.message : "新闻证据暂缺"));
    return () => {
      active = false;
    };
  }, [sectorId]);

  return (
    <section className="sector-evidence panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">PUBLIC NEWS EVIDENCE</span>
          <h2>新闻催化证据</h2>
        </div>
        <span className="quality-tag">
          {evidence?.state === "available"
            ? `公开新闻${evidence.cached_count ? ` · ${evidence.cached_count}缓存` : ""}`
            : "证据加载中"}
        </span>
      </div>
      {!evidence && !error ? <p>正在读取代表股票关联的公开新闻…</p> : null}
      {error ? <p>{error}</p> : null}
      {evidence ? (
        <>
          <p className="evidence-boundary">{evidence.message}</p>
          {evidence.representative_stocks.length ? (
            <small className="evidence-scope">
              CORE STOCK EVIDENCE · {evidence.representative_stocks.map((stock) => `${stock.name} ${stock.code}`).join(" / ")}
            </small>
          ) : null}
          {evidence.news.length ? (
            <div className="evidence-news-list">
              {evidence.news.map((item) => (
                <a href={item.url} key={item.url} rel="noreferrer" target="_blank">
                  <span>{item.source} · {item.published_at}</span>
                  {item.data_state === "cached" && item.cached_at ? (
                    <span>上次成功数据 · {formatCachedAt(item.cached_at)}</span>
                  ) : null}
                  <strong>{item.title}</strong>
                  <p>{item.summary}</p>
                  <small>{item.name} {item.code} · 打开原文 ↗</small>
                </a>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
