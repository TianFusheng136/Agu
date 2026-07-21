export function marketQualityLabel(value: string) {
  if (value === "demo") return "演示数据";
  if (value === "refreshing-live-public") return "公开行情 · 后台刷新中";
  if (value === "stale-public") return "缓存行情 · 上游刷新失败";
  return "公开行情";
}
