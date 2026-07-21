"""OpenAI-compatible LLM boundary for evidence-only market explanations."""

import json
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.llm_config import get_llm_runtime_configuration


class LlmNotConfigured(RuntimeError):
    pass


class LlmInvalidResponse(RuntimeError):
    pass


def _upstream_error_message(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    error_payload = payload.get("error")
    if isinstance(error_payload, dict) and isinstance(error_payload.get("message"), str):
        return error_payload["message"].strip()
    return ""


def _plain_text(value: str, *, limit: int) -> str:
    return (
        value.replace("**", "")
        .replace("`", "")
        .lstrip("#*- ")
        .strip()[:limit]
    )


def _parse_structured_explanation(content: str) -> dict[str, object]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise LlmInvalidResponse("LLM返回内容不是结构化JSON")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as error:
        raise LlmInvalidResponse("LLM返回的JSON无法解析") from error
    if not isinstance(payload, dict):
        raise LlmInvalidResponse("LLM返回的结构不是JSON对象")

    conclusion = payload.get("market_conclusion")
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise LlmInvalidResponse("LLM结果缺少市场结论")

    sections: dict[str, object] = {
        "market_conclusion": _plain_text(conclusion, limit=240),
    }
    for key in ("evidence", "risks", "data_gaps"):
        values = payload.get(key)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise LlmInvalidResponse(f"LLM结果中的{key}格式无效")
        sections[key] = [
            text for item in values[:6] if (text := _plain_text(item, limit=240))
        ]
    return sections


def check_llm_connection() -> dict[str, object]:
    configuration = get_llm_runtime_configuration()
    if not configuration.configured:
        return {
            "state": "not-configured",
            "code": "configuration-missing",
            "message": "请先填写API Key和模型名称。",
            "model": configuration.model or None,
            "latency_ms": None,
        }

    payload = json.dumps(
        {
            "model": configuration.model,
            "temperature": 0,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "仅回复OK"}],
        }
    ).encode("utf-8")
    request = Request(
        f"{configuration.base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {configuration.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started_at = perf_counter()
    try:
        with urlopen(request, timeout=12) as response:  # nosec B310 - configured endpoint
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        upstream_message = _upstream_error_message(error).casefold()
        if error.code == 401:
            code = "invalid-api-key"
            message = "API Key无效或已失效，请重新检查。"
        elif error.code in (400, 404) and "model" in upstream_message:
            code = "invalid-model"
            message = "模型名称不可用，请填写该服务商实际支持的模型ID。"
        elif error.code == 403:
            code = "access-denied"
            message = "API Key没有调用权限，或当前账号状态受限。"
        elif error.code == 404:
            code = "endpoint-not-found"
            message = "没有找到模型接口，请检查API地址是否正确。"
        elif error.code == 429:
            code = "rate-limited"
            message = "接口请求受限，请检查余额、额度或稍后重试。"
        else:
            code = "http-error"
            message = f"模型接口返回HTTP {error.code}。"
        return {
            "state": "failed",
            "code": code,
            "message": message,
            "model": configuration.model,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        }
    except URLError:
        return {
            "state": "failed",
            "code": "connection-error",
            "message": "无法连接模型服务，请检查API接口地址、网络或代理设置。",
            "model": configuration.model,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        }

    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices:
        return {
            "state": "failed",
            "code": "invalid-response",
            "message": "接口已响应，但返回格式不是兼容的Chat Completions。",
            "model": configuration.model,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        }
    return {
        "state": "connected",
        "code": "ok",
        "message": "连接成功，API Key、接口地址和模型均可用。",
        "model": configuration.model,
        "latency_ms": round((perf_counter() - started_at) * 1000),
    }


def generate_evidence_explanation(facts: dict[str, object]) -> dict[str, object]:
    configuration = get_llm_runtime_configuration()
    api_key = configuration.api_key
    model = configuration.model
    if not api_key or not model:
        raise LlmNotConfigured("LLM未配置")
    base_url = configuration.base_url
    prompt = (
        "你是A股市场研究信息整理助手。只根据以下冻结事实生成中文解释。\n"
        "仅输出一个合法JSON对象，不要输出Markdown、代码块或JSON之外的说明。"
        "对象必须包含market_conclusion、evidence、risks、data_gaps四个字段："
        "market_conclusion是字符串，用于概括市场结构；evidence是字符串数组，"
        "用于列出增强方向以及修复或降温方向的直接证据；risks是字符串数组，"
        "用于列出风险；data_gaps是字符串数组，用于列出证据边界与风险中的数据缺失。\n"
        "结论必须说明依据，证据标签只能使用[轮动]、[技术]、[新闻]、[缺失]。"
        "新闻只能表述为代表股公开新闻，不能扩大成板块整体催化。\n"
        "可以引用冻结事实中的原始数字、代码和百分比，但必须保持原值；"
        "不得自行计算新数字，不得补全缺失值，不得把行业资金净额称为主力资金。\n"
        "trading_amount_change_pct只表示成交额变化，不得把成交额变化解释为换手率。"
        "不得根据没有新闻推断‘无负面’或‘没有风险’，不得仅凭新闻标题断言事件驱动。\n"
        "不得提供买卖建议、收益承诺、目标价或涨停预测。"
        "如果证据冲突或不足，必须直接写明。总长度不超过700个中文字符。\n"
        "冻结事实："
        + json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
    )
    payload = json.dumps(
        {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": "仅做基于结构化证据的A股市场研究解释，不做投资建议。",
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=25) as response:  # nosec B310 - configured endpoint
        body = json.loads(response.read().decode("utf-8"))
    content = str(body["choices"][0]["message"]["content"]).strip()
    if not content:
        raise RuntimeError("LLM返回空内容")
    return _parse_structured_explanation(content)
