"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="error-state">
      <span>DATA CONNECTION LOST</span>
      <h1>首次市场快照加载失败</h1>
      <p>FastAPI 尚未取得第一份可验证行情。公开行情源短暂限流时，可稍后重新加载。</p>
      <small>系统不会自动回退到演示行情，也不会把过期数据伪装成今日数据。</small>
      <button type="button" onClick={reset}>
        重新连接
      </button>
    </main>
  );
}
