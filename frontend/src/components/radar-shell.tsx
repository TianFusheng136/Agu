"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { API_BASE_URL, requestMarketRefresh } from "@/lib/api";
import { marketQualityLabel } from "@/lib/market-quality";
import type { MarketOverview, SearchResult } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/", label: "市场全景", short: "市场" },
  { href: "/sectors", label: "热点板块", short: "板块" },
  { href: "/stocks", label: "核心观察", short: "股票" },
  { href: "/brief", label: "AI 简报", short: "简报" },
] as const;

const KIND_LABELS: Record<SearchResult["kind"], string> = {
  sector: "板块",
  stock: "股票",
  etf: "ETF",
};

function formatAsOf(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function resultHref(result: SearchResult) {
  if (result.kind === "stock") return `/stocks/${result.id}`;
  if (result.kind === "sector") return `/sectors/${result.id}`;
  return `/etfs/${result.id}`;
}

function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [message, setMessage] = useState("");
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKeydown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
      if (event.key === "Escape") {
        setResults([]);
        setMessage("");
      }
    }
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, []);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized) {
      setResults([]);
      setMessage("请输入股票代码、名称、板块或 ETF");
      return;
    }
    setSearching(true);
    setMessage("");
    try {
      const response = await fetch(
        `${API_BASE_URL}/search?q=${encodeURIComponent(normalized)}`,
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(payload?.detail || `搜索接口返回 ${response.status}`);
      }
      const items = (await response.json()) as SearchResult[];
      setResults(items);
      setMessage(items.length ? "" : `没有找到“${normalized}”`);
    } catch (error) {
      setResults([]);
      if (
        error instanceof Error &&
        error.message.includes("代码表正在后台加载")
      ) {
        setMessage("股票目录正在初始化，请几秒后重试");
      } else {
        setMessage(
          error instanceof Error
            ? `搜索失败：${error.message}`
            : "搜索服务暂时不可用",
        );
      }
    } finally {
      setSearching(false);
    }
  }

  const open = results.length > 0 || Boolean(message);
  return (
    <section className="global-search" aria-label="全市场搜索">
      <form role="search" onSubmit={search}>
        <span aria-hidden="true">⌕</span>
        <input
          ref={inputRef}
          aria-label="搜索股票、板块或 ETF"
          placeholder="输入代码或名称，例如 000021 / 深科技"
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            if (!event.target.value) {
              setResults([]);
              setMessage("");
            }
          }}
        />
        <kbd>Ctrl K</kbd>
        <button disabled={searching} type="submit">
          {searching ? "查询中" : "搜索"}
        </button>
      </form>
      {open && (
        <div className="global-search__results" aria-live="polite">
          <div className="global-search__caption">
            <span>研究对象</span>
            <small>股票结果可进入 K 线详情页</small>
          </div>
          {message ? (
            <p>{message}</p>
          ) : (
            results.map((result) => (
              <Link href={resultHref(result)} key={`${result.kind}-${result.id}`}>
                <span>{KIND_LABELS[result.kind]}</span>
                <strong>{result.name}</strong>
                <small>{result.subtitle}</small>
                <i aria-hidden="true">→</i>
              </Link>
            ))
          )}
        </div>
      )}
    </section>
  );
}

function MarketRefreshControl() {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");

  async function refresh() {
    setRefreshing(true);
    setMessage("");
    try {
      const result = await requestMarketRefresh();
      if (result.state === "started") {
        setMessage("已发起后台刷新，正在读取公开行情…");
        window.setTimeout(() => router.refresh(), 3000);
      } else if (result.state === "already-running") {
        setMessage("公开行情正在后台刷新，请稍后读取最新快照。");
      } else {
        setMessage(result.message);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "行情刷新暂时不可用");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="market-refresh">
      <button disabled={refreshing} onClick={refresh} type="button">
        {refreshing ? "请求中" : "刷新行情"}
      </button>
      {message ? <span aria-live="polite">{message}</span> : null}
    </div>
  );
}

export function RadarShell({
  active,
  overview,
  children,
}: {
  active: "market" | "sectors" | "stocks" | "brief";
  overview: MarketOverview;
  children: React.ReactNode;
}) {
  const activeHref = {
    market: "/",
    sectors: "/sectors",
    stocks: "/stocks",
    brief: "/brief",
  }[active];

  return (
    <div className="terminal-shell radar-os" data-active-view={active}>
      <div className="radar-ambient" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <header className="topbar control-island">
        <Link className="brand" href="/" aria-label="AI 短线市场雷达首页">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            <strong>短线雷达</strong>
            <small>RADAR OS · FINAL</small>
          </span>
        </Link>
        <nav aria-label="主导航">
          {NAV_ITEMS.map((item) => (
            <Link
              className={activeHref === item.href ? "active" : undefined}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="market-clock">
          <span className="live-dot" aria-hidden="true" />
          <div>
            <strong>A 股 · {overview.market_status}</strong>
            <small>{formatAsOf(overview.as_of)} 更新</small>
          </div>
          <MarketRefreshControl />
        </div>
      </header>

      <div className="command-stage">
        <GlobalSearch />
      </div>
      <main className="radar-content">{children}</main>

      <footer className="site-footer">
        <div>
          <section>
            <strong>研究边界</strong>
            <p>{overview.disclaimer}</p>
          </section>
          <section>
            <strong>数据来源</strong>
            <p>
              {overview.sources.length
                ? overview.sources.map((source) => source.name).join(" / ")
                : "公开数据源暂不可用"}
            </p>
          </section>
          <section>
            <strong>数据状态</strong>
            <p>
              {marketQualityLabel(overview.data_quality)} · {overview.market_status} ·{" "}
              {formatAsOf(overview.as_of)}
            </p>
          </section>
        </div>
        <span>RADAR OS / A-SHARE / FINAL 1.0</span>
      </footer>

      <nav className="mobile-dock" aria-label="移动端快速导航">
        {NAV_ITEMS.map((item) => (
          <Link
            className={activeHref === item.href ? "active" : undefined}
            href={item.href}
            key={item.href}
          >
            {item.short}
          </Link>
        ))}
      </nav>
    </div>
  );
}
