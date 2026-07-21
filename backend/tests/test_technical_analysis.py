from datetime import date, timedelta

from app.providers.base import StockCandle


def candles_from_closes(closes: list[float]) -> list[StockCandle]:
    start = date(2026, 1, 2)
    return [
        StockCandle(
            date=(start + timedelta(days=index)).isoformat(),
            open=close - 0.1,
            high=close + 0.4,
            low=close - 0.5,
            close=close,
            volume=1_000_000 + index * 5_000,
            amount=close * (1_000_000 + index * 5_000),
        )
        for index, close in enumerate(closes)
    ]


def test_technical_analysis_returns_macd_kdj_and_weekly_statistics_without_trade_action() -> None:
    from app.domain.technical import analyze_technical_signals

    signal = analyze_technical_signals(
        candles_from_closes([10 + index * 0.3 for index in range(80)])
    )

    assert signal.macd.dif > signal.macd.dea
    assert signal.macd.state in {"DIF位于DEA上方", "MACD金叉"}
    assert signal.kdj.state == "KDJ高位区"
    assert signal.weekly.weeks_observed >= 5
    assert signal.weekly.close_vs_ma5_pct is not None
    assert "买入" not in signal.disclaimer
    assert "卖出" not in signal.disclaimer
