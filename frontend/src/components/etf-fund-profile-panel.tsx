type EtfFundProfile = {
  state: "available" | "unavailable";
  full_name: string | null;
  benchmark: string | null;
  manager: string | null;
  share_scale: string | null;
  source: string;
  retrieved_at: string;
  message: string;
};

export function EtfFundProfilePanel({ profile }: { profile: EtfFundProfile | null }) {
  return (
    <section className="etf-profile panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow">PUBLIC FUND FACTS</span>
          <h2>公开基金资料</h2>
        </div>
        <span className={`quality-tag ${profile?.state === "unavailable" ? "quality-tag--warning" : ""}`}>
          {profile?.state === "available" ? "已返回" : "暂缺"}
        </span>
      </div>
      {profile?.state === "available" ? (
        <div className="etf-profile__facts">
          <div><span>基金全称</span><strong>{profile.full_name ?? "数据暂缺"}</strong></div>
          <div><span>业绩比较基准</span><strong>{profile.benchmark ?? "数据暂缺"}</strong></div>
          <div><span>基金管理人</span><strong>{profile.manager ?? "数据暂缺"}</strong></div>
          <div><span>份额规模</span><strong>{profile.share_scale ?? "数据暂缺"}</strong></div>
        </div>
      ) : (
        <p className="inline-empty">公开基金资料暂不可用；行情与映射审核仍按各自的数据状态展示。</p>
      )}
      <p className="etf-profile__boundary">业绩比较基准仅作公开资料展示，不等同于成分股或覆盖校验。</p>
      {profile ? <small className="etf-profile__source">{profile.source} · {profile.retrieved_at}</small> : null}
    </section>
  );
}
