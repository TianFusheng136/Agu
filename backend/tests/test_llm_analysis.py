import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

from app.services import llm_analysis


def test_llm_connection_check_reports_invalid_key_without_exposing_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_analysis,
        "get_llm_runtime_configuration",
        lambda: SimpleNamespace(
            api_key="secret-test-key",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            configured=True,
        ),
    )

    def reject_request(request, timeout):
        del request, timeout
        raise HTTPError(
            "https://api.deepseek.com/chat/completions",
            401,
            "Unauthorized",
            {},
            BytesIO(
                json.dumps(
                    {"error": {"message": "Authentication Fails, Your api key is invalid"}}
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr(llm_analysis, "urlopen", reject_request)

    result = llm_analysis.check_llm_connection()

    assert result["state"] == "failed"
    assert result["code"] == "invalid-api-key"
    assert "API Key" in result["message"]
    assert "secret-test-key" not in json.dumps(result, ensure_ascii=False)


def test_llm_connection_check_accepts_a_valid_chat_completion(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_analysis,
        "get_llm_runtime_configuration",
        lambda: SimpleNamespace(
            api_key="test-key",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            configured=True,
        ),
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "OK"}}]}
            ).encode("utf-8")

    monkeypatch.setattr(llm_analysis, "urlopen", lambda request, timeout: FakeResponse())

    result = llm_analysis.check_llm_connection()

    assert result["state"] == "connected"
    assert result["code"] == "ok"
    assert result["model"] == "deepseek-chat"


def test_llm_connection_check_identifies_an_invalid_model(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_analysis,
        "get_llm_runtime_configuration",
        lambda: SimpleNamespace(
            api_key="test-key",
            model="missing-model",
            base_url="https://api.deepseek.com",
            configured=True,
        ),
    )

    def reject_request(request, timeout):
        del request, timeout
        raise HTTPError(
            "https://api.deepseek.com/chat/completions",
            400,
            "Bad Request",
            {},
            BytesIO(
                json.dumps({"error": {"message": "Model Not Exist"}}).encode("utf-8")
            ),
        )

    monkeypatch.setattr(llm_analysis, "urlopen", reject_request)

    result = llm_analysis.check_llm_connection()

    assert result["code"] == "invalid-model"
    assert "模型名称" in result["message"]


def test_llm_connection_check_identifies_an_unreachable_api(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_analysis,
        "get_llm_runtime_configuration",
        lambda: SimpleNamespace(
            api_key="test-key",
            model="deepseek-chat",
            base_url="https://unreachable.test",
            configured=True,
        ),
    )
    monkeypatch.setattr(
        llm_analysis,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("Name resolution failed")),
    )

    result = llm_analysis.check_llm_connection()

    assert result["code"] == "connection-error"
    assert "接口地址" in result["message"]


def test_llm_prompt_requires_structured_evidence_and_exact_frozen_numbers(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_analysis,
        "get_llm_runtime_configuration",
        lambda: SimpleNamespace(
            api_key="test-key",
            model="test-model",
            base_url="https://example.test/v1",
        ),
    )
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "market_conclusion": "市场分化，情绪偏弱。",
                                        "evidence": ["[轮动] 电力近5日转强。"],
                                        "risks": ["[技术] 代表股信号分化。"],
                                        "data_gaps": ["[缺失] 北向资金暂缺。"],
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm_analysis, "urlopen", fake_urlopen)

    result = llm_analysis.generate_evidence_explanation(
        {
            "market_metrics": {"advancers": 1709, "decliners": 3415},
            "directions": [
                {
                    "name": "电力",
                    "rotation": {"trend_5d_pct": 8.04},
                    "news": [{"title": "公开新闻", "source": "公开来源"}],
                }
            ],
            "data_gaps": ["北向资金暂缺"],
        }
    )

    assert result == {
        "market_conclusion": "市场分化，情绪偏弱。",
        "evidence": ["[轮动] 电力近5日转强。"],
        "risks": ["[技术] 代表股信号分化。"],
        "data_gaps": ["[缺失] 北向资金暂缺。"],
    }
    payload = json.loads(captured["request"].data.decode("utf-8"))
    prompt = payload["messages"][1]["content"]
    assert "市场结构" in prompt
    assert "增强方向" in prompt
    assert "修复或降温方向" in prompt
    assert "证据边界与风险" in prompt
    assert "可以引用冻结事实中的原始数字" in prompt
    assert "不得自行计算新数字" in prompt
    assert "不得把成交额变化解释为换手率" in prompt
    assert "不得根据没有新闻推断" in prompt
    assert "[轮动]" in prompt
    assert "[技术]" in prompt
    assert "[新闻]" in prompt
    assert "market_conclusion" in prompt
    assert "仅输出一个合法JSON对象" in prompt
    assert '"trend_5d_pct":8.04' in prompt
