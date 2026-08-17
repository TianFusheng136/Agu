"""Optional TradingAgents runtime adapter.

The adapter deliberately keeps the third-party framework behind an explicit,
research-only boundary.  Runs are queued in a single worker so provider API
keys never overlap between concurrent jobs and the HTTP request can return
immediately while the multi-agent graph is working.
"""

from __future__ import annotations

import importlib.util
import os
import re
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

from app.services.llm_config import LlmRuntimeConfiguration, get_llm_runtime_configuration

RunState = Literal["queued", "running", "completed", "failed"]

_RATING_WEIGHTS = {
    "buy": ("看多", 78, 22),
    "overweight": ("偏多", 65, 35),
    "hold": ("中性", 50, 50),
    "underweight": ("偏空", 35, 65),
    "sell": ("看空", 22, 78),
}


def normalize_a_share_ticker(code: str) -> str:
    """Map a six-digit Shanghai/Shenzhen code to TradingAgents' Yahoo symbol."""
    normalized = code.strip()
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError("请输入 6 位 A 股代码")
    if normalized.startswith(("60", "68")):
        return f"{normalized}.SS"
    if normalized.startswith(("00", "30")):
        return f"{normalized}.SZ"
    raise ValueError("当前多智能体研判仅支持沪市与深市股票代码")


def _provider_for(configuration: LlmRuntimeConfiguration) -> tuple[str, str]:
    host = (urlparse(configuration.base_url).hostname or "").casefold()
    if "deepseek" in host:
        return "deepseek", "DEEPSEEK_API_KEY"
    if host == "api.openai.com" or host.endswith(".openai.com"):
        return "openai", "OPENAI_API_KEY"
    if "dashscope.aliyuncs.com" in host:
        return "qwen-cn", "DASHSCOPE_CN_API_KEY"
    if "dashscope-intl.aliyuncs.com" in host:
        return "qwen", "DASHSCOPE_API_KEY"
    if "open.bigmodel.cn" in host:
        return "glm-cn", "ZHIPU_CN_API_KEY"
    if host == "api.z.ai" or host.endswith(".z.ai"):
        return "glm", "ZHIPU_API_KEY"
    if "openrouter.ai" in host:
        return "openrouter", "OPENROUTER_API_KEY"
    return "openai_compatible", "OPENAI_COMPATIBLE_API_KEY"


@contextmanager
def _temporary_environment(values: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def build_price_context(history: Any) -> dict[str, Any]:
    """Build a deterministic price observation band from daily candles."""
    candles = list(getattr(history, "candles", []) or [])
    if len(candles) < 20:
        return {
            "state": "unavailable",
            "message": "日 K 样本不足 20 根，暂不计算价格观察区间。",
        }
    closes = [float(candle.close) for candle in candles[-20:]]
    lows = [float(candle.low) for candle in candles[-20:]]
    highs = [float(candle.high) for candle in candles[-20:]]
    latest = candles[-1]
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes) / 20
    anchor = (ma10 + ma20) / 2
    zone_low = round(anchor * 0.98, 3)
    zone_high = round(anchor * 1.02, 3)
    current = round(float(latest.close), 3)
    if current > zone_high:
        state = "above-zone"
        message = "当前价格高于均线观察区间，追高风险相对更高。"
    elif current < zone_low:
        state = "below-zone"
        message = "当前价格低于均线观察区间，需要先确认是否出现趋势破坏。"
    else:
        state = "inside-zone"
        message = "当前价格处于均线观察区间，仍需结合量价与风险复核。"
    return {
        "state": state,
        "current_price": current,
        "observation_zone_low": zone_low,
        "observation_zone_high": zone_high,
        "ma10": round(ma10, 3),
        "ma20": round(ma20, 3),
        "support_20d": round(min(lows), 3),
        "resistance_20d": round(max(highs), 3),
        "as_of": str(latest.date),
        "message": message,
        "method": "前复权日 K 的 MA10/MA20 中枢上下 2%，仅作观察区间，不是建议买入价。",
    }


def build_direction_summary(
    final_assessment: str,
    price_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Convert the framework's discrete rating into an explicit, non-probabilistic tilt."""
    rating_match = re.search(
        r"\*\*Rating\*\*\s*:\s*(Buy|Overweight|Hold|Underweight|Sell)",
        final_assessment,
        flags=re.IGNORECASE,
    )
    rating = rating_match.group(1) if rating_match else "Hold"
    label, bullish_weight, bearish_weight = _RATING_WEIGHTS[rating.casefold()]
    target_match = re.search(
        r"\*\*Price Target\*\*\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        final_assessment,
        flags=re.IGNORECASE,
    )
    return {
        "direction": label,
        "rating": rating,
        "bullish_weight": bullish_weight,
        "bearish_weight": bearish_weight,
        "weight_note": "由最终五档评级映射出的多空倾向度，不是上涨或下跌的统计概率。",
        "framework_price_target": float(target_match.group(1)) if target_match else None,
        "framework_price_target_note": "模型目标价不是合适买入价，也不作为订单依据。",
        "price_context": price_context
        or {"state": "unavailable", "message": "站内日 K 暂不可用，未计算观察区间。"},
    }


class TradingAgentsService:
    """Queue and expose research-only TradingAgents runs."""

    def __init__(self, runtime_root: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.runtime_root = runtime_root or project_root / ".runtime" / "trading-agents"
        self._jobs: dict[str, dict[str, Any]] = {}
        self._jobs_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trading-agents")

    @staticmethod
    def package_installed() -> bool:
        return importlib.util.find_spec("tradingagents") is not None

    def status(self) -> dict[str, Any]:
        installed = self.package_installed()
        configuration = get_llm_runtime_configuration()
        if not installed:
            state = "package-missing"
            message = "多智能体运行组件尚未安装，请先运行项目内的安装脚本。"
        elif not configuration.configured:
            state = "llm-not-configured"
            message = "运行组件已就绪，请先在 AI 简报中配置模型。"
        else:
            state = "ready"
            message = "多智能体研究链路已就绪。"
        version = None
        if installed:
            try:
                version = metadata.version("tradingagents")
            except metadata.PackageNotFoundError:
                version = "source"
        return {
            "state": state,
            "installed": installed,
            "configured": configuration.configured,
            "version": version,
            "model": configuration.model or None,
            "message": message,
            "analysts": ["技术", "情绪", "新闻", "基本面"],
            "data_source": "TradingAgents / Yahoo Finance（独立于站内 AKShare 行情）",
            "execution_enabled": False,
        }

    def start_run(
        self,
        *,
        code: str,
        analysis_date: date | None,
        depth: Literal["quick", "standard"],
        price_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_status = self.status()
        if current_status["state"] != "ready":
            raise RuntimeError(current_status["message"])
        ticker = normalize_a_share_ticker(code)
        requested_date = analysis_date or date.today()
        if requested_date > date.today():
            raise ValueError("研判日期不能晚于今天")
        job_id = uuid4().hex
        job = {
            "id": job_id,
            "state": "queued",
            "code": code.strip(),
            "ticker": ticker,
            "analysis_date": requested_date.isoformat(),
            "depth": depth,
            "created_at": datetime.now().astimezone().isoformat(),
            "started_at": None,
            "completed_at": None,
            "message": "任务已进入队列。完整研判通常需要数分钟。",
            "price_context": price_context,
            "result": None,
        }
        with self._jobs_lock:
            self._jobs[job_id] = job
        self._executor.submit(self._execute, job_id)
        return deepcopy(job)

    def get_run(self, job_id: str) -> dict[str, Any] | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._jobs_lock:
            self._jobs[job_id].update(changes)

    def _execute(self, job_id: str) -> None:
        job = self.get_run(job_id)
        if job is None:
            return
        self._update(
            job_id,
            state="running",
            started_at=datetime.now().astimezone().isoformat(),
            message="技术、情绪、新闻与基本面代理正在协作研判。",
        )
        configuration = get_llm_runtime_configuration()
        try:
            with self._run_lock:
                result = self._run_framework(job, configuration)
        except Exception as error:  # third-party runtime boundary
            message = str(error).replace(configuration.api_key, "***")
            self._update(
                job_id,
                state="failed",
                completed_at=datetime.now().astimezone().isoformat(),
                message=f"多智能体研判失败：{message[:500]}",
            )
            return
        self._update(
            job_id,
            state="completed",
            completed_at=datetime.now().astimezone().isoformat(),
            message="多智能体研判已完成。",
            result=result,
        )

    def _run_framework(
        self,
        job: dict[str, Any],
        configuration: LlmRuntimeConfiguration,
    ) -> dict[str, Any]:
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        provider, key_name = _provider_for(configuration)
        run_root = self.runtime_root / job["id"]
        config = deepcopy(DEFAULT_CONFIG)
        config.update(
            {
                "llm_provider": provider,
                "deep_think_llm": configuration.model,
                "quick_think_llm": configuration.model,
                "backend_url": configuration.base_url,
                "output_language": "Simplified Chinese",
                "max_debate_rounds": 1 if job["depth"] == "quick" else 2,
                "max_risk_discuss_rounds": 1 if job["depth"] == "quick" else 2,
                "checkpoint_enabled": True,
                "results_dir": str(run_root / "results"),
                "data_cache_dir": str(self.runtime_root / "cache"),
                "memory_log_path": str(self.runtime_root / "memory" / "research-memory.md"),
                "news_article_limit": 8,
                "global_news_article_limit": 4,
            }
        )
        environment = {
            key_name: configuration.api_key,
            "TRADINGAGENTS_OUTPUT_LANGUAGE": "Simplified Chinese",
        }
        with _temporary_environment(environment):
            graph = TradingAgentsGraph(
                selected_analysts=("market", "social", "news", "fundamentals"),
                debug=False,
                config=config,
            )
            final_state, _signal = graph.propagate(
                job["ticker"], job["analysis_date"], asset_type="stock"
            )
        investment_debate = final_state.get("investment_debate_state") or {}
        risk_debate = final_state.get("risk_debate_state") or {}
        final_assessment = _text(final_state.get("final_trade_decision"))
        return {
            "analyst_reports": {
                "technical": _text(final_state.get("market_report")),
                "sentiment": _text(final_state.get("sentiment_report")),
                "news": _text(final_state.get("news_report")),
                "fundamentals": _text(final_state.get("fundamentals_report")),
            },
            "research_debate": {
                "bull": _text(investment_debate.get("bull_history")),
                "bear": _text(investment_debate.get("bear_history")),
                "judge": _text(investment_debate.get("judge_decision")),
            },
            "risk_review": {
                "aggressive": _text(risk_debate.get("aggressive_history")),
                "neutral": _text(risk_debate.get("neutral_history")),
                "conservative": _text(risk_debate.get("conservative_history")),
                "judge": _text(risk_debate.get("judge_decision")),
            },
            "research_plan": _text(final_state.get("investment_plan")),
            "strategy_hypothesis": _text(final_state.get("trader_investment_plan")),
            "final_assessment": final_assessment,
            "direction_summary": build_direction_summary(
                final_assessment, job.get("price_context")
            ),
            "source_note": (
                "本页为 TradingAgents 独立研究结果；A 股外部数据经 Yahoo Finance 获取，"
                "可能与站内 AKShare 口径及更新时间不同。"
            ),
            "disclaimer": (
                "仅供多角度研究复核，不构成投资建议；未连接券商，不会发送或执行订单。"
            ),
        }
