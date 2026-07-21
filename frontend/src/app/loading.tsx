export default function Loading() {
  return (
    <main className="route-loading" aria-live="polite" aria-label="正在切换页面">
      <div className="route-loading__bar" />
      <section>
        <span>MARKET RADAR</span>
        <h1>正在切换研究页面</h1>
        <p>复用当前市场快照，实时行情在后台刷新。</p>
      </section>
    </main>
  );
}
