"use client";

import { useEffect, useState } from "react";

import {
  fetchLlmAnalysisStatus,
  generateLlmMarketBrief,
  saveLlmConfiguration,
  testLlmConnection,
} from "@/lib/api";
import type {
  LlmAnalysisStatus,
  LlmConnectionTestResult,
  LlmMarketBrief,
} from "@/lib/types";

function readableAnalysis(analysis: string): string {
  return analysis
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/^\s*#{1,6}\s*/gm, "")
    .replace(/^\s*[-*]\s+/gm, "")
    .trim();
}

function analysisParagraphs(analysis: string): string[] {
  return readableAnalysis(analysis)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function LlmStatusPanel() {
  const [status, setStatus] = useState<LlmAnalysisStatus | null>(null);
  const [brief, setBrief] = useState<LlmMarketBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [connection, setConnection] = useState<LlmConnectionTestResult | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("deepseek-v4-flash");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchLlmAnalysisStatus().then(setStatus).catch(() => {
      setStatus({
        state: "not-configured",
        provider: "未连接",
        model: null,
        message: "LLM状态暂时不可用；当前仅展示规则化简报。",
      });
    });
  }, []);

  async function generate() {
    setLoading(true);
    setError("");
    try {
      setBrief(await generateLlmMarketBrief());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "LLM解释请求失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  async function saveConfiguration(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setConnection(null);
    try {
      setStatus(await saveLlmConfiguration({ apiKey, model, baseUrl }));
      const result = await testLlmConnection();
      setConnection(result);
      if (result.state === "connected") {
        setApiKey("");
        setConfigOpen(false);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "LLM 配置保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    setError("");
    setConnection(null);
    try {
      setConnection(await testLlmConnection());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "LLM连接检测失败，请稍后重试。");
    } finally {
      setTesting(false);
    }
  }

  function renderList(items: string[], emptyMessage: string) {
    if (!items.length) return <p>{emptyMessage}</p>;
    return (
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    );
  }

  return (
    <section className="llm-status panel">
      <h2>AI市场解读</h2>
      <div className="llm-status__actions">
        <button disabled={loading} onClick={generate} type="button">
          {loading ? "生成中" : "生成AI解读"}
        </button>
        <button onClick={() => setConfigOpen((open) => !open)} type="button">
          模型设置
        </button>
        {status?.state === "configured" ? (
          <button disabled={testing} onClick={testConnection} type="button">
            {testing ? "检测中" : "测试连接"}
          </button>
        ) : null}
      </div>
      {status?.state === "not-configured" && !configOpen ? (
        <small>尚未连接模型</small>
      ) : null}
      {configOpen ? (
        <form className="llm-config-form" onSubmit={saveConfiguration}>
          <label>
            API Key
            <input
              autoComplete="off"
              onChange={(event) => setApiKey(event.target.value)}
              required
              type="password"
              value={apiKey}
            />
          </label>
          <label>
            模型
            <input onChange={(event) => setModel(event.target.value)} required value={model} />
          </label>
          <label>
            API 地址
            <input onChange={(event) => setBaseUrl(event.target.value)} required value={baseUrl} />
          </label>
          <button disabled={saving} type="submit">
            {saving ? "检测中" : "保存并测试"}
          </button>
        </form>
      ) : null}
      {connection ? (
        <p
          className={`llm-connection-result llm-connection-result--${connection.state}`}
          role="status"
        >
          <span>{connection.message}</span>
          {connection.latency_ms !== null ? <small>{connection.latency_ms}ms</small> : null}
        </p>
      ) : null}
      {brief ? (
        <section className="llm-output">
          <span>AI 解读</span>
          {brief.sections ? (
            <div className="llm-output__structured">
              <article className="llm-output__conclusion">
                <h3>市场结论</h3>
                <p>{brief.sections.market_conclusion}</p>
              </article>
              <div className="llm-output__grid">
                <article>
                  <h3>核心证据</h3>
                  {renderList(brief.sections.evidence, "当前返回未列出核心证据。")}
                </article>
                <article>
                  <h3>风险</h3>
                  {renderList(brief.sections.risks, "当前返回未列出风险项。")}
                </article>
                <article>
                  <h3>数据缺口</h3>
                  {renderList(brief.sections.data_gaps, "当前返回未列出数据缺口。")}
                </article>
              </div>
            </div>
          ) : (
            <div className="llm-output__sections">
              {(brief.analysis ? analysisParagraphs(brief.analysis) : [brief.message]).map(
                (paragraph, index) => (
                  <p key={`${index}-${paragraph}`}>{paragraph}</p>
                ),
              )}
            </div>
          )}
        </section>
      ) : null}
      {error ? <p>{error}</p> : null}
    </section>
  );
}
