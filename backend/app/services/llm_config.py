"""Local-only configuration storage for the optional LLM connection."""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LlmRuntimeConfiguration:
    api_key: str
    model: str
    base_url: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)


def _config_path() -> Path:
    configured_path = os.getenv("LLM_CONFIG_PATH", "").strip()
    if configured_path:
        return Path(configured_path)
    project_root = Path(__file__).resolve().parents[3]
    return project_root / ".runtime" / "config" / "llm-config.json"


def _read_local_configuration() -> dict[str, str]:
    try:
        payload = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        key: value.strip()
        for key in ("api_key", "model", "base_url")
        if isinstance((value := payload.get(key)), str)
    }


def get_llm_runtime_configuration() -> LlmRuntimeConfiguration:
    stored = _read_local_configuration()
    return LlmRuntimeConfiguration(
        api_key=stored.get("api_key", "") or os.getenv("LLM_API_KEY", "").strip(),
        model=stored.get("model", "") or os.getenv("LLM_MODEL", "").strip(),
        base_url=(
            stored.get("base_url", "")
            or os.getenv("LLM_API_BASE_URL", "").strip()
            or "https://api.openai.com/v1"
        ).rstrip("/"),
    )


def save_local_llm_configuration(*, api_key: str, model: str, base_url: str) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_key": api_key.strip(),
        "model": model.strip(),
        "base_url": base_url.strip().rstrip("/"),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
