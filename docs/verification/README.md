# MVP 验收记录

验收日期：2026-07-17

## 自动化验证

- 后端 Pytest：16 passed；
- 后端 Ruff：All checks passed；
- 前端 Vitest：3 passed；
- 前端 ESLint：通过；
- Next.js 生产构建：通过，首页为动态服务端渲染路由；
- `scripts/verify.ps1`：已在目标目录完整执行通过。

## 真实行情验证

数据 Provider 默认值为 `live`，没有设置 `MARKET_DATA_PROVIDER=demo`。

实际联网请求 `GET /api/v1/market/overview` 已确认：

- `data_quality=live-public`；
- `as_of=2026-07-17T16:12:02+08:00`；
- 市场状态为“已收盘”；
- 上涨 482 家、下跌 5001 家；
- 涨停 33 家、跌停 192 家；
- 最高连板 5 板、炸板率 23.3%；
- 热点板块为电力、银行、厨卫电器；
- 电力板块精确匹配到 `159611`、`562550`；
- 页面显示公开行情来源和数据时间；
- 缺少稳定来源的字段显示“数据源暂缺”，不会用演示值填充。

## 端到端验证

使用临时端口运行完整链路：

- Backend：`http://127.0.0.1:18000`
- Frontend：`http://127.0.0.1:13000`

启动脚本确认：

- `GET /api/v1/health` 返回 200；
- `GET /api/v1/market/overview` 返回 200；
- Next.js `GET /` 返回 200；
- 首页 HTML 包含“公开行情”和 `07/17`；
- API 首次成功请求后复用 60 秒缓存；
- 测试结束后临时服务自动停止。

仓库中的 `mvp-dashboard.png` 是早期演示 Provider 的历史 UI 截图，不再代表当前实时数据口径。
