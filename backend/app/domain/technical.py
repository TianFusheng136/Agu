"""Deterministic technical-indicator statistics for research display only."""

from collections import defaultdict
from datetime import date

from app.domain.contracts import FrozenModel
from app.providers.base import StockCandle

TECHNICAL_DISCLAIMER = "技术指标仅描述历史价格与成交结构，不构成买卖建议或收益承诺。"


class MacdStatistics(FrozenModel):
    dif: float | None
    dea: float | None
    histogram: float | None
    state: str


class KdjStatistics(FrozenModel):
    k: float | None
    d: float | None
    j: float | None
    state: str


class WeeklyStatistics(FrozenModel):
    weeks_observed: int
    latest_change_pct: float | None
    close_vs_ma5_pct: float | None
    volume_ratio: float | None
    state: str


class TechnicalSignalStats(FrozenModel):
    sample_size: int
    macd: MacdStatistics
    kdj: KdjStatistics
    weekly: WeeklyStatistics
    disclaimer: str = TECHNICAL_DISCLAIMER


def analyze_technical_signals(candles: list[StockCandle]) -> TechnicalSignalStats:
    ordered = sorted(candles, key=lambda candle: candle.date)
    closes = [candle.close for candle in ordered]
    return TechnicalSignalStats(
        sample_size=len(ordered),
        macd=_macd(closes),
        kdj=_kdj(ordered),
        weekly=_weekly(ordered),
    )


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * alpha + result[-1] * (1 - alpha))
    return result


def _macd(closes: list[float]) -> MacdStatistics:
    if len(closes) < 26:
        return MacdStatistics(dif=None, dea=None, histogram=None, state="样本不足")
    dif_series = [
        fast - slow
        for fast, slow in zip(_ema(closes, 12), _ema(closes, 26), strict=True)
    ]
    dea_series = _ema(dif_series, 9)
    dif = dif_series[-1]
    dea = dea_series[-1]
    previous_dif = dif_series[-2]
    previous_dea = dea_series[-2]
    if previous_dif <= previous_dea and dif > dea:
        state = "MACD金叉"
    elif previous_dif >= previous_dea and dif < dea:
        state = "MACD死叉"
    elif dif >= dea:
        state = "DIF位于DEA上方"
    else:
        state = "DIF位于DEA下方"
    return MacdStatistics(
        dif=round(dif, 4),
        dea=round(dea, 4),
        histogram=round((dif - dea) * 2, 4),
        state=state,
    )


def _kdj(candles: list[StockCandle]) -> KdjStatistics:
    if len(candles) < 9:
        return KdjStatistics(k=None, d=None, j=None, state="样本不足")
    k_values: list[float] = []
    d_values: list[float] = []
    k = 50.0
    d = 50.0
    for index, candle in enumerate(candles):
        window = candles[max(0, index - 8) : index + 1]
        high = max(item.high for item in window)
        low = min(item.low for item in window)
        rsv = 50.0 if high == low else (candle.close - low) / (high - low) * 100
        k = (2 * k + rsv) / 3
        d = (2 * d + k) / 3
        k_values.append(k)
        d_values.append(d)
    j = 3 * k - 2 * d
    previous_k = k_values[-2]
    previous_d = d_values[-2]
    if previous_k <= previous_d and k > d:
        state = "KDJ金叉"
    elif previous_k >= previous_d and k < d:
        state = "KDJ死叉"
    elif k >= 80 and d >= 80:
        state = "KDJ高位区"
    elif k <= 20 and d <= 20:
        state = "KDJ低位区"
    else:
        state = "KDJ中性区"
    return KdjStatistics(k=round(k, 2), d=round(d, 2), j=round(j, 2), state=state)


def _weekly(candles: list[StockCandle]) -> WeeklyStatistics:
    if not candles:
        return WeeklyStatistics(
            weeks_observed=0,
            latest_change_pct=None,
            close_vs_ma5_pct=None,
            volume_ratio=None,
            state="样本不足",
        )
    buckets: dict[tuple[int, int], list[StockCandle]] = defaultdict(list)
    for candle in candles:
        current = date.fromisoformat(candle.date)
        year, week, _ = current.isocalendar()
        buckets[(year, week)].append(candle)
    weeks = [buckets[key] for key in sorted(buckets)]
    closes = [week[-1].close for week in weeks]
    volumes = [sum(item.volume for item in week) for week in weeks]
    if len(weeks) < 2:
        return WeeklyStatistics(
            weeks_observed=len(weeks),
            latest_change_pct=None,
            close_vs_ma5_pct=None,
            volume_ratio=None,
            state="样本不足",
        )
    latest_change = (closes[-1] / closes[-2] - 1) * 100
    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
    close_vs_ma5 = (closes[-1] / ma5 - 1) * 100 if ma5 else None
    baseline = sum(volumes[-6:-1]) / min(5, len(volumes) - 1)
    volume_ratio = volumes[-1] / baseline if baseline else None
    if volume_ratio is not None and volume_ratio >= 1.8 and abs(latest_change) >= 3:
        state = "周线放量异动"
    elif close_vs_ma5 is not None and close_vs_ma5 >= 0:
        state = "周线位于5周均线之上"
    elif close_vs_ma5 is not None:
        state = "周线位于5周均线之下"
    else:
        state = "周线样本积累中"
    return WeeklyStatistics(
        weeks_observed=len(weeks),
        latest_change_pct=round(latest_change, 2),
        close_vs_ma5_pct=round(close_vs_ma5, 2) if close_vs_ma5 is not None else None,
        volume_ratio=round(volume_ratio, 2) if volume_ratio is not None else None,
        state=state,
    )
