import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { LlmStatusPanel } from "./llm-status-panel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("shows a readable generated explanation without exposing the raw audit payload", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          state: "configured",
          provider: "OpenAI-compatible API",
          model: "test-model",
          message: "Configured.",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          state: "generated",
          analysis: "### 不应展示的原始Markdown",
          message: "Generated from frozen facts.",
          as_of: "2026-07-20T13:30:00+08:00",
          sections: {
            market_conclusion: "市场分化，情绪偏弱。",
            evidence: ["[轮动] 电力近5日转强。"],
            risks: ["[技术] 代表股信号分化。"],
            data_gaps: ["[缺失] 北向资金暂缺。"],
          },
          facts: {
            as_of: "2026-07-20T13:30:00+08:00",
            market_status: "open",
            market_sentiment: "medium",
            directions: [
              {
                name: "AI server",
                stage: "rising",
                risks: ["crowding"],
                representative_stock_available: true,
              },
            ],
          },
        }),
      }),
  );
  const user = userEvent.setup();

  render(<LlmStatusPanel />);
  expect(screen.queryByText("LLM ANALYSIS LAYER")).not.toBeInTheDocument();
  expect(screen.queryByText(/模型已连接/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "配置 API Key" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "生成AI解读" }));

  expect(await screen.findByRole("heading", { name: "市场结论" })).toBeInTheDocument();
  expect(screen.getByText("市场分化，情绪偏弱。")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "核心证据" })).toBeInTheDocument();
  expect(screen.getByText("[轮动] 电力近5日转强。")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "风险" })).toBeInTheDocument();
  expect(screen.getByText("[技术] 代表股信号分化。")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "数据缺口" })).toBeInTheDocument();
  expect(screen.getByText("[缺失] 北向资金暂缺。")).toBeInTheDocument();
  expect(screen.queryByText(/不应展示的原始Markdown/)).not.toBeInTheDocument();
  expect(screen.queryByText("FROZEN FACTS")).not.toBeInTheDocument();
  expect(screen.queryByText("representative stock: available")).not.toBeInTheDocument();
  expect(screen.queryByText("模型分析状态")).not.toBeInTheDocument();
});

it("sends a typed API key to the local backend and clears it from the form", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        state: "not-configured",
        provider: "OpenAI-compatible API",
        model: null,
        message: "尚未配置。",
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        state: "configured",
        provider: "OpenAI-compatible API",
        model: "deepseek-v4-flash",
        message: "模型已配置。",
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        state: "connected",
        code: "ok",
        message: "连接成功，API Key、接口地址和模型均可用。",
        model: "deepseek-v4-flash",
        latency_ms: 88,
      }),
    });
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();

  render(<LlmStatusPanel />);
  await user.click(screen.getByRole("button", { name: "模型设置" }));
  await user.type(screen.getByLabelText("API Key"), "test-local-key");
  await user.click(screen.getByRole("button", { name: "保存并测试" }));

  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/analysis/configuration",
    expect.objectContaining({ method: "PUT" }),
  );
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/analysis/connection-test",
    expect.objectContaining({ method: "POST" }),
  );
  expect(await screen.findByRole("button", { name: "生成AI解读" })).toBeInTheDocument();
  expect(screen.getByText("连接成功，API Key、接口地址和模型均可用。"))
    .toBeInTheDocument();
  expect(screen.queryByText(/模型已连接/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
});

it("keeps the settings open and shows the exact model connection error", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          state: "not-configured",
          provider: "OpenAI-compatible API",
          model: null,
          message: "尚未配置。",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          state: "configured",
          provider: "OpenAI-compatible API",
          model: "wrong-model",
          message: "模型已配置。",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          state: "failed",
          code: "invalid-model",
          message: "模型名称不可用，请填写该服务商实际支持的模型ID。",
          model: "wrong-model",
          latency_ms: 71,
        }),
      }),
  );
  const user = userEvent.setup();

  render(<LlmStatusPanel />);
  await user.click(screen.getByRole("button", { name: "模型设置" }));
  await user.type(screen.getByLabelText("API Key"), "test-local-key");
  await user.clear(screen.getByLabelText("模型"));
  await user.type(screen.getByLabelText("模型"), "wrong-model");
  await user.click(screen.getByRole("button", { name: "保存并测试" }));

  expect(await screen.findByText("模型名称不可用，请填写该服务商实际支持的模型ID。"))
    .toBeInTheDocument();
  expect(screen.getByLabelText("API Key")).toBeInTheDocument();
});
