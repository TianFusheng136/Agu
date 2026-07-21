"use client";

import { useMemo, useState } from "react";

import type { StockCandle, StockHistory } from "@/lib/types";

const WIDTH = 1120;
const HEIGHT = 560;
const PRICE_TOP = 38;
const PRICE_BOTTOM = 390;
const VOLUME_TOP = 430;
const VOLUME_BOTTOM = 525;
const LEFT = 58;
const RIGHT = 74;

function movingAverage(candles: StockCandle[], days: number) {
  return candles.map((_, index) => {
    if (index < days - 1) return null;
    const values = candles.slice(index - days + 1, index + 1);
    return values.reduce((sum, candle) => sum + candle.close, 0) / days;
  });
}

export function KLineChart({ history }: { history: StockHistory }) {
  const [range, setRange] = useState<20 | 60 | 120>(60);
  const candles = history.candles.slice(-range);
  const model = useMemo(() => {
    const lows = candles.map((item) => item.low);
    const highs = candles.map((item) => item.high);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const pricePadding = Math.max((max - min) * 0.08, max * 0.005);
    const low = min - pricePadding;
    const high = max + pricePadding;
    const maxVolume = Math.max(...candles.map((item) => item.volume), 1);
    const slot = (WIDTH - LEFT - RIGHT) / Math.max(candles.length, 1);
    const x = (index: number) => LEFT + slot * index + slot / 2;
    const y = (price: number) =>
      PRICE_TOP +
      ((high - price) / Math.max(high - low, 0.01)) *
        (PRICE_BOTTOM - PRICE_TOP);
    const volumeY = (volume: number) =>
      VOLUME_BOTTOM -
      (volume / maxVolume) * (VOLUME_BOTTOM - VOLUME_TOP);
    return { low, high, maxVolume, slot, x, y, volumeY };
  }, [candles]);

  const ma5 = movingAverage(candles, 5);
  const ma10 = movingAverage(candles, 10);
  const ma20 = movingAverage(candles, 20);
  const pathFor = (values: Array<number | null>) =>
    values
      .map((value, index) =>
        value === null
          ? ""
          : `${values.slice(0, index).every((item) => item === null) ? "M" : "L"} ${model.x(index).toFixed(2)} ${model.y(value).toFixed(2)}`,
      )
      .filter(Boolean)
      .join(" ");
  const latest = candles.at(-1);

  if (!candles.length) {
    return <div className="kline-empty">暂无可用 K 线数据</div>;
  }

  return (
    <section className="kline-panel panel">
      <header className="kline-toolbar">
        <div>
          <span className="section-eyebrow">PRICE ACTION / K-LINE</span>
          <h2>{history.name} K 线</h2>
          <p>
            {history.code} · 前复权 · 截至 {history.as_of}
          </p>
        </div>
        <div className="kline-ranges" aria-label="K线显示范围">
          {([20, 60, 120] as const).map((value) => (
            <button
              className={range === value ? "active" : undefined}
              key={value}
              onClick={() => setRange(value)}
              type="button"
            >
              {value}日
            </button>
          ))}
        </div>
      </header>

      <div className="kline-legend">
        <span>MA5</span>
        <span>MA10</span>
        <span>MA20</span>
        <strong className={latest && latest.close >= latest.open ? "positive" : "negative"}>
          最新 {latest?.close.toFixed(2)}
        </strong>
      </div>

      <div className="kline-canvas">
        <svg
          aria-label={`${history.name}最近${candles.length}个交易日K线图`}
          role="img"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        >
          {[0, 1, 2, 3, 4].map((index) => {
            const ratio = index / 4;
            const y = PRICE_TOP + ratio * (PRICE_BOTTOM - PRICE_TOP);
            const price = model.high - ratio * (model.high - model.low);
            return (
              <g key={index}>
                <line
                  className="chart-grid"
                  x1={LEFT}
                  x2={WIDTH - RIGHT}
                  y1={y}
                  y2={y}
                />
                <text className="price-label" x={WIDTH - RIGHT + 10} y={y + 4}>
                  {price.toFixed(2)}
                </text>
              </g>
            );
          })}
          <line
            className="chart-grid"
            x1={LEFT}
            x2={WIDTH - RIGHT}
            y1={VOLUME_TOP}
            y2={VOLUME_TOP}
          />
          {candles.map((candle, index) => {
            const x = model.x(index);
            const rising = candle.close >= candle.open;
            const bodyTop = model.y(Math.max(candle.open, candle.close));
            const bodyHeight = Math.max(
              1.5,
              Math.abs(model.y(candle.open) - model.y(candle.close)),
            );
            const bodyWidth = Math.max(2, Math.min(model.slot * 0.62, 12));
            const volumeY = model.volumeY(candle.volume);
            return (
              <g className={rising ? "candle rising" : "candle falling"} key={candle.date}>
                <line x1={x} x2={x} y1={model.y(candle.high)} y2={model.y(candle.low)} />
                <rect
                  height={bodyHeight}
                  width={bodyWidth}
                  x={x - bodyWidth / 2}
                  y={bodyTop}
                />
                <rect
                  className="volume-bar"
                  height={VOLUME_BOTTOM - volumeY}
                  width={bodyWidth}
                  x={x - bodyWidth / 2}
                  y={volumeY}
                />
              </g>
            );
          })}
          <path className="ma-line ma5" d={pathFor(ma5)} />
          <path className="ma-line ma10" d={pathFor(ma10)} />
          <path className="ma-line ma20" d={pathFor(ma20)} />
          {[0, Math.floor((candles.length - 1) / 2), candles.length - 1].map(
            (index) => (
              <text
                className="date-label"
                key={`${candles[index].date}-${index}`}
                textAnchor={index === 0 ? "start" : index === candles.length - 1 ? "end" : "middle"}
                x={
                  index === 0
                    ? LEFT
                    : index === candles.length - 1
                      ? WIDTH - RIGHT
                      : model.x(index)
                }
                y={548}
              >
                {candles[index].date.slice(5)}
              </text>
            ),
          )}
        </svg>
      </div>
      <footer className="kline-source">
        <span>{history.source}</span>
        <span>{history.data_quality === "demo" ? "演示数据" : "公开历史行情"}</span>
      </footer>
    </section>
  );
}
