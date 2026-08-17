# 多智能体研判功能

本功能把开源项目 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 作为**可选研究组件**接入 Agu。技术、情绪、新闻和基本面代理分别研究后，再进行多空辩论与风险复核。

## 能做什么

- 输入 6 位沪深 A 股代码，创建后台研究任务；
- 展示技术、情绪、新闻、基本面四类报告；
- 展示多空辩论、风险角色意见和最终研究裁决；
- 将框架评级转换为“看多 / 偏多 / 中性 / 偏空 / 看空”倾向；
- 基于站内前复权日 K 计算 MA10 / MA20 观察区间、20 日支撑和压力位置；
- 支持快速（单轮）和完整（双轮）两种研究深度。

页面入口：`http://127.0.0.1:3000/agents`

## 安装与配置

先完成 Agu 的常规依赖安装，然后安装可选组件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-trading-agents.ps1
```

安装脚本默认使用 TradingAgents `v0.3.1`，不会把第三方源码复制进 Agu 仓库。第三方软件及其依赖遵循各自许可证。

随后在 Agu 的“AI 简报”页面配置 OpenAI-compatible API Key、模型 ID 和 API 地址，再重启 Agu。API Key 只保存在本机 `.runtime/config/llm-config.json`，不会由状态接口返回，也不应提交到 Git。

## 数据和运行边界

- TradingAgents 使用自己的外部数据链；当前 A 股代码会映射为 Yahoo Finance 的 `.SS` / `.SZ` 标识；
- 外部数据与站内 AKShare 行情可能存在时间、复权和字段口径差异；
- 后台只启用一个研究 worker，避免多个任务同时修改模型环境变量；
- 任务状态保存在进程内存中，服务重启后不会恢复旧任务；
- 结果只用于研究展示，不写回行情数值，不接券商，不发送订单；
- “多空倾向度”来自五档评级映射，不是上涨或下跌的统计概率；
- 观察区间不是建议买入价，框架目标价也不会用于下单。

## API

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/trading-agents/status` | 检查组件、模型和研究边界状态 |
| POST | `/api/v1/trading-agents/runs` | 创建后台研究任务 |
| GET | `/api/v1/trading-agents/runs/{job_id}` | 轮询任务状态与结果 |

创建任务示例：

```json
{
  "code": "600519",
  "analysis_date": "2026-08-08",
  "depth": "quick"
}
```

## 安全说明

- 不要在 Issue、日志、截图或提交中粘贴 API Key；
- `.runtime/` 和 `.env*` 已由 `.gitignore` 排除；
- 异常信息返回前会对当前模型 Key 做脱敏；
- 若组件、模型或数据不可用，接口会明确失败，不使用演示结果冒充研究结论。
