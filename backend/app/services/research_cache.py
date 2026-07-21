"""Small last-success cache contracts for research data.

The default implementation is process-local. A file-backed implementation is
added separately for restart recovery.
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

JsonObject = dict[str, Any]


class ResearchCacheStore(Protocol):
    def get_signal(self, code: str) -> tuple[JsonObject, str] | None: ...

    def put_signal(self, code: str, payload: JsonObject, cached_at: str) -> None: ...

    def get_news(self, code: str) -> tuple[list[JsonObject], str] | None: ...

    def put_news(
        self,
        code: str,
        payload: list[JsonObject],
        cached_at: str,
    ) -> None: ...


class InMemoryResearchCacheStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._signals: dict[str, tuple[JsonObject, str]] = {}
        self._news: dict[str, tuple[list[JsonObject], str]] = {}

    def get_signal(self, code: str) -> tuple[JsonObject, str] | None:
        with self._lock:
            entry = self._signals.get(code)
            return deepcopy(entry) if entry is not None else None

    def put_signal(self, code: str, payload: JsonObject, cached_at: str) -> None:
        with self._lock:
            self._signals[code] = (deepcopy(payload), cached_at)

    def get_news(self, code: str) -> tuple[list[JsonObject], str] | None:
        with self._lock:
            entry = self._news.get(code)
            return deepcopy(entry) if entry is not None else None

    def put_news(
        self,
        code: str,
        payload: list[JsonObject],
        cached_at: str,
    ) -> None:
        with self._lock:
            self._news[code] = (deepcopy(payload), cached_at)


class FileResearchCacheStore(InMemoryResearchCacheStore):
    """Atomic UTF-8 JSON cache that survives backend restarts."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._load()

    def put_signal(self, code: str, payload: JsonObject, cached_at: str) -> None:
        with self._lock:
            self._signals[code] = (deepcopy(payload), cached_at)
            self._save_locked()

    def put_news(
        self,
        code: str,
        payload: list[JsonObject],
        cached_at: str,
    ) -> None:
        with self._lock:
            self._news[code] = (deepcopy(payload), cached_at)
            self._save_locked()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                return
            signals = payload.get("signals", {})
            news = payload.get("news", {})
            if not isinstance(signals, dict) or not isinstance(news, dict):
                return
            for code, raw in signals.items():
                if (
                    isinstance(code, str)
                    and isinstance(raw, dict)
                    and isinstance(raw.get("payload"), dict)
                    and isinstance(raw.get("cached_at"), str)
                ):
                    self._signals[code] = (
                        deepcopy(raw["payload"]),
                        raw["cached_at"],
                    )
            for code, raw in news.items():
                if (
                    isinstance(code, str)
                    and isinstance(raw, dict)
                    and isinstance(raw.get("payload"), list)
                    and all(isinstance(item, dict) for item in raw["payload"])
                    and isinstance(raw.get("cached_at"), str)
                ):
                    self._news[code] = (
                        deepcopy(raw["payload"]),
                        raw["cached_at"],
                    )
        except (OSError, ValueError, json.JSONDecodeError):
            self._signals = {}
            self._news = {}

    def _save_locked(self) -> None:
        payload = {
            "schema_version": 1,
            "signals": {
                code: {"payload": item, "cached_at": cached_at}
                for code, (item, cached_at) in self._signals.items()
            },
            "news": {
                code: {"payload": items, "cached_at": cached_at}
                for code, (items, cached_at) in self._news.items()
            },
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, self._path)
        except OSError:
            # Cache persistence must never interrupt live public-data delivery.
            return
