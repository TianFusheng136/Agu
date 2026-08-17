"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

import {
  fetchTradingAgentsRun,
  fetchTradingAgentsStatus,
  startTradingAgentsRun,
} from "@/lib/api";
import type {
  TradingAgentsRun,
  TradingAgentsRunResult,
  TradingAgentsStatus,
} from "@/lib/types";

const ANALYSTS = [
  ["01", "技术分析", "K 线、量价与技术指标"],
  ["02", "市场情绪", "新闻情绪与市场关注度"],
  ["03", "新闻研究", "公司新闻与宏观影响"],
  ["04", "基本面", "财务质量与潜在风险"],
] as const;

function Report({ title, content }: { title: string; content: string }) {
  return (
    <article>
      <h3>{title}</h3>
      <p>{content || "本轮未返回可展示内容。"}</p>
    </article>
  );
}

function ResultView({ result }: { result: TradingAgentsRunResult }) {
  const summary = result.direction_summary;
  const price = summary.price_context;
  return (
    <div className="agents-result">
      <section className="agents-direction-board">
        <article className={`agents-direction-card agents-direction-card--${summary.rating.toLowerCase()}`}>
          <span>最终方向</span>
          <strong>{summary.direction}</strong>
          <small>TradingAgents：{summary.rating}</small>
        </article>
        <article className="agents-weight-card">
          <div>
            <span>看多倾向</span>
            <strong>{summary.bullish_weight}%</strong>
          </div>
          <div className="agents-weight-bar" aria-label="多空倾向度">
            <i style={{ width: `${summary.bullish_weight}%` }} />
          </div>
          <div>
            <span>看空倾向</span>
            <strong>{summary.bearish_weight}%</strong>
          </div>
          <small>{summary.weight_note}</small>
        </article>
        <article className="agents-price-card">
          <span>价格位置</span>
          {price.state === "unavailable" ? (
            <p>{price.message}</p>
          ) : (
            <>
              <strong>{price.current_price?.toFixed(3)}</strong>
              <p>
                观察区间 {price.observation_zone_low?.toFixed(3)} – {price.observation_zone_high?.toFixed(3)}
              </p>
              <small>{price.message}</small>
            </>
          )}
        </article>
      </section>
      <section className="agents-result__final">
        <span>FINAL RESEARCH REVIEW</span>
        <h2>综合研判</h2>
        <p>{result.final_assessment || "本轮未形成综合结论。"}</p>
        <small>{result.disclaimer}</small>
      </section>
      <section className="agents-price-detail">
        <div>
          <span>20 日支撑观察</span>
          <strong>{price.support_20d?.toFixed(3) ?? "暂缺"}</strong>
        </div>
        <div>
          <span>20 日压力观察</span>
          <strong>{price.resistance_20d?.toFixed(3) ?? "暂缺"}</strong>
        </div>
        <div>
          <span>框架目标价</span>
          <strong>{summary.framework_price_target?.toFixed(3) ?? "未给出"}</strong>
          <small>{summary.framework_price_target_note}</small>
        </div>
        <p>{price.method ?? "观察区间暂不可用。"}</p>
      </section>
      <details open>
        <summary>四类分析报告</summary>
        <div className="agents-report-grid">
          <Report title="技术分析" content={result.analyst_reports.technical} />
          <Report title="市场情绪" content={result.analyst_reports.sentiment} />
          <Report title="新闻研究" content={result.analyst_reports.news} />
          <Report title="基本面" content={result.analyst_reports.fundamentals} />
        </div>
      </details>
      <details>
        <summary>多空研究辩论</summary>
        <div className="agents-report-grid agents-report-grid--three">
          <Report title="看多研究" content={result.research_debate.bull} />
          <Report title="看空研究" content={result.research_debate.bear} />
          <Report title="研究裁决" content={result.research_debate.judge} />
        </div>
      </details>
      <details>
        <summary>风险复核</summary>
        <div className="agents-report-grid agents-report-grid--three">
          <Report title="激进视角" content={result.risk_review.aggressive} />
          <Report title="中性视角" content={result.risk_review.neutral} />
          <Report title="保守视角" content={result.risk_review.conservative} />
        </div>
        <Report title="风险裁决" content={result.risk_review.judge} />
      </details>
      <section className="agents-result__boundary">
        <strong>数据口径</strong>
        <p>{result.source_note}</p>
      </section>
    </div>
  );
}

export function TradingAgentsPanel({ initialCode = "" }: { initialCode?: string }) {
  const [status, setStatus] = useState<TradingAgentsStatus | null>(null);
  const [run, setRun] = useState<TradingAgentsRun | null>(null);
  const [code, setCode] = useState(initialCode);
  const [depth, setDepth] = useState<"quick" | "standard">("quick");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchTradingAgentsStatus().then(setStatus).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "多智能体状态暂时不可用");
    });
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  async function poll(id: string) {
    try {
      const current = await fetchTradingAgentsRun(id);
      setRun(current);
      if (current.state === "queued" || current.state === "running") {
        timer.current = setTimeout(() => void poll(id), 2500);
      } else {
        setLoading(false);
      }
    } catch (reason) {
      setLoading(false);
      setError(reason instanceof Error ? reason.message : "读取研判结果失败");
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setRun(null);
    setLoading(true);
    try {
      const created = await startTradingAgentsRun({ code, depth });
      setRun(created);
      await poll(created.id);
    } catch (reason) {
      setLoading(false);
      setError(reason instanceof Error ? reason.message : "无法启动多智能体研判");
    }
  }

  const ready = status?.state === "ready";
  return (
    <div className="agents-page">
      <section className="agents-hero panel">
        <div>
          <span className="section-eyebrow">TRADINGAGENTS / MULTI-AGENT RESEARCH</span>
          <h1>多智能体研判台</h1>
          <p>让四类分析代理先独立研究，再进行多空辩论与风险复核。只展示研究过程，不连接券商。</p>
        </div>
        <a href="https://github.com/TauricResearch/TradingAgents" rel="noreferrer" target="_blank">
          开源项目 ↗
        </a>
      </section>

      <section className="agents-flow" aria-label="多智能体研究流程">
        {ANALYSTS.map(([index, title, description]) => (
          <article className="panel" key={title}>
            <span>{index}</span>
            <h2>{title}</h2>
            <p>{description}</p>
          </article>
        ))}
        <i aria-hidden="true">→</i>
        <article className="panel agents-flow__decision">
          <span>05</span>
          <h2>辩论与风险复核</h2>
          <p>看多、看空与风险角色交叉检查证据</p>
        </article>
      </section>

      <section className="agents-console panel">
        <div className="agents-console__status">
          <div>
            <span className="section-eyebrow">RUNTIME STATUS</span>
            <h2>{status?.state === "ready" ? "研究链路已就绪" : "研究链路待配置"}</h2>
            <p>{status?.message ?? "正在检查后台组件…"}</p>
          </div>
          <div>
            <b>{status?.version ? `TradingAgents ${status.version}` : "TradingAgents"}</b>
            <small>{status?.model ?? "模型未连接"}</small>
          </div>
        </div>
        {!ready && status?.state === "llm-not-configured" ? (
          <Link className="agents-setup-link" href="/brief">前往 AI 简报配置模型 →</Link>
        ) : null}
        {!ready && status?.state === "package-missing" ? (
          <p className="agents-install-note">先运行 scripts/install-trading-agents.ps1，刷新页面后即可使用。</p>
        ) : null}
        <form onSubmit={submit}>
          <label>
            A 股代码
            <input
              inputMode="numeric"
              maxLength={6}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
              placeholder="例如 600519 / 000021"
              required
              value={code}
            />
          </label>
          <label>
            研究深度
            <select onChange={(event) => setDepth(event.target.value as "quick" | "standard")} value={depth}>
              <option value="quick">快速 · 单轮辩论</option>
              <option value="standard">完整 · 双轮辩论</option>
            </select>
          </label>
          <button disabled={!ready || loading || code.length !== 6} type="submit">
            {loading ? "多智能体研判中…" : "开始研判"}
          </button>
        </form>
        {run ? (
          <div className={`agents-run-state agents-run-state--${run.state}`} role="status">
            <span>{run.ticker}</span>
            <strong>{run.message}</strong>
            <small>{run.analysis_date} · {run.depth === "quick" ? "快速模式" : "完整模式"}</small>
          </div>
        ) : null}
        {error ? <p className="agents-error" role="alert">{error}</p> : null}
      </section>

      {run?.state === "completed" && run.result ? <ResultView result={run.result} /> : null}

      <section className="agents-boundary panel">
        <strong>研究边界</strong>
        <p>TradingAgents 使用独立外部数据链，结果可能与站内实时行情存在时间和口径差异。系统不会自动下单，也不会把模型意见写回行情数字。</p>
      </section>
    </div>
  );
}
